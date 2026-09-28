from django.contrib import messages
from django.db import transaction
from django.http import HttpResponseForbidden, JsonResponse
from django.urls import reverse
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from apps.accounts.dashboard import is_physician
from apps.accounts.dashboard import role_of
from apps.accounts.permissions import clinic_staff_required, clinical_required
from apps.audit.models import AuditEntry
from apps.audit.services import log

from . import attachments
from apps.patients.models import Patient

from .forms import ConsultationForm
from .models import Attachment, Consultation, Visit

DENIED = "Only physicians can write consultation notes."


def _editable_visit(request, pk):
    """The visit a physician may currently write notes for, or an error response."""
    visit = get_object_or_404(Visit.objects.select_related("patient"), pk=pk)
    if not is_physician(request.user):
        return None, HttpResponseForbidden(DENIED)
    if visit.status != Visit.Status.WITH_DOCTOR:
        return None, HttpResponseForbidden("This visit is not in consultation.")
    return visit, None


def _save_notes(request, visit, form):
    consult, _ = Consultation.objects.get_or_create(visit=visit, defaults={"doctor": request.user})
    for name in (*Consultation.SECTIONS, "patient_summary"):
        setattr(consult, name, form.cleaned_data[name].strip())
    consult.doctor = request.user
    consult.save()
    return consult


@clinic_staff_required
@require_POST
def consultation_save(request, pk):
    """Save Draft, or Save & Complete Visit."""
    visit, error = _editable_visit(request, pk)
    if error:
        return error
    back = redirect("patient_detail", pk=visit.patient_id)
    form = ConsultationForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Those notes could not be saved.")
        return back

    if request.POST.get("action") == "complete":
        missing = [n.title() for n in Consultation.SECTIONS if not form.cleaned_data[n].strip()]
        if missing:
            _save_notes(request, visit, form)
            messages.error(request, "Draft saved, but the visit can't be completed yet. Still empty: " + ", ".join(missing) + ".")
            return back
        with transaction.atomic():
            visit = Visit.objects.select_for_update().get(pk=pk)
            if visit.status != Visit.Status.WITH_DOCTOR:
                messages.info(request, "This visit was already completed.")
                return back
            consult = _save_notes(request, visit, form)
            now = timezone.now()
            consult.completed_at = now
            consult.save()
            visit.status = Visit.Status.COMPLETED
            visit.completed_at = now
            visit.save(update_fields=["status", "completed_at"])
            log(request.user, AuditEntry.Kind.MODIFIED, f"completed the consultation for {visit.patient.full_name}", visit.patient)
        messages.success(request, f"Visit completed. {visit.patient.full_name}'s notes are now part of the permanent record.")
        return redirect("dashboard")

    _save_notes(request, visit, form)
    messages.success(request, "Draft saved.")
    return back


@clinic_staff_required
@require_POST
def consultation_autosave(request, pk):
    """Silent draft save while typing. Returns the time saved."""
    visit, error = _editable_visit(request, pk)
    if error:
        return error
    form = ConsultationForm(request.POST)
    if not form.is_valid():
        return JsonResponse({"ok": False}, status=400)
    consult = _save_notes(request, visit, form)
    return JsonResponse({"ok": True, "saved_at": timezone.localtime(consult.updated_at).strftime("%I:%M %p")})


@clinic_staff_required
@require_POST
def visit_close(request, pk):
    """Close a visit that will not be seen: registered by mistake, or the patient left. Nothing is deleted."""
    with transaction.atomic():
        visit = get_object_or_404(Visit.objects.select_for_update().select_related("patient"), pk=pk)
        outcome = request.POST.get("outcome")
        reason = request.POST.get("reason", "").strip()
        back = request.POST.get("next") or "dashboard"
        if back != "dashboard" and not url_has_allowed_host_and_scheme(back, allowed_hosts={request.get_host()}):
            back = "dashboard"  # never redirect to another site
        if visit.status not in Visit.WAITING:
            messages.error(request, "Only patients still waiting can be closed this way. A visit with the doctor is completed in the notes.")
            return redirect(back)
        if outcome not in dict(Visit.CLOSE_OUTCOMES):
            messages.error(request, "Please choose what happened.")
            return redirect(back)
        if outcome == "cancelled" and not reason:
            messages.error(request, "Please give a reason for cancelling the visit.")
            return redirect(back)
        visit.status = Visit.Status(outcome)
        visit.closed_reason, visit.closed_by = reason[:255], request.user
        visit.save(update_fields=["status", "closed_reason", "closed_by"])
        name = visit.patient.full_name
        what = f"cancelled the visit of {name}" if outcome == "cancelled" else f"marked {name} as left without being seen"
        log(request.user, AuditEntry.Kind.MODIFIED, what + (f" ({reason})" if reason else ""), visit.patient)
    messages.success(request, f"{visit.patient.full_name}'s visit was closed.")
    return redirect(back)


# --------------------------------------------------------------------------- attachments (PDF files)
def _back_to_files(patient_pk):
    return redirect(f"{reverse('patient_detail', args=[patient_pk])}?tab=attachments")


@clinical_required
@require_POST
def attachment_upload(request, patient_pk):
    patient = get_object_or_404(Patient, pk=patient_pk)
    form = attachments.AttachmentForm(request.POST, request.FILES)
    if not form.is_valid():
        messages.error(request, " ".join(e for errs in form.errors.values() for e in errs))
        return _back_to_files(patient.pk)
    current = patient.visits.filter(status__in=Visit.ACTIVE).first()
    item = attachments.store(form, patient, request.user, source=Attachment.Source.CLINIC, visit=current)
    log(request.user, AuditEntry.Kind.CREATED, f"uploaded the {item.get_category_display().lower()} “{item.filename}” for {patient.full_name}", patient)
    messages.success(request, f"“{item.filename}” was added to the record.")
    return _back_to_files(patient.pk)


@clinical_required
@require_POST
def attachment_review(request, pk):
    """Accept or reject a file a patient sent in. Only accepted files become part of the record."""
    item = get_object_or_404(Attachment.objects.defer("content").select_related("patient"), pk=pk, withdrawn_at__isnull=True)
    accepted = request.POST.get("decision") == "accept"
    note = request.POST.get("note", "").strip()
    if item.source != Attachment.Source.PATIENT or item.review_status != Attachment.Review.PENDING:
        messages.info(request, "That file has already been reviewed.")
    elif not accepted and not note:
        messages.error(request, "Please tell the patient why the file was not accepted.")
    else:
        attachments.mark_reviewed(item, request.user, accepted, note)
        log(request.user, AuditEntry.Kind.MODIFIED, f"{'accepted' if accepted else 'declined'} the file “{item.filename}” sent by {item.patient.full_name}", item.patient)
        messages.success(request, "File accepted into the record." if accepted else "File declined. The patient will see your note.")
    return _back_to_files(item.patient_id)


@clinical_required
@require_POST
def attachment_withdraw(request, pk):
    """Hide a file that was added by mistake (for example, to the wrong patient). It is kept, not deleted."""
    item = get_object_or_404(Attachment.objects.defer("content").select_related("patient"), pk=pk, withdrawn_at__isnull=True)
    reason = request.POST.get("reason", "").strip()
    if not reason:
        messages.error(request, "Please say why you are withdrawing this file.")
    else:
        item.withdrawn_at, item.withdrawn_by, item.withdrawn_reason = timezone.now(), request.user, reason[:255]
        item.save(update_fields=["withdrawn_at", "withdrawn_by", "withdrawn_reason"])
        log(request.user, AuditEntry.Kind.MODIFIED, f"withdrew the file “{item.filename}” of {item.patient.full_name} ({reason[:80]})", item.patient)
        messages.success(request, "File withdrawn. It is hidden from the record and the patient.")
    return _back_to_files(item.patient_id)


def attachment_download(request, pk):
    """Open or download a file, only for people allowed to see it. Every access is logged."""
    if not request.user.is_authenticated:
        return redirect(f"{reverse('login')}?next={request.path}")
    item = get_object_or_404(Attachment.objects.select_related("patient"), pk=pk)
    if not attachments.can_view(request.user, item):
        return HttpResponseForbidden("You don't have access to this file.")
    log(request.user, AuditEntry.Kind.AUTHORIZED, f"opened the file “{item.filename}” of {item.patient.full_name}", item.patient)
    return attachments.serve(item, inline=request.GET.get("inline") == "1")
