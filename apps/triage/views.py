from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.accounts.dashboard import staff_label
from apps.accounts.permissions import clinical_required
from apps.audit.models import AuditEntry
from apps.audit.services import log
from apps.history.models import Visit

from .assessment import RANK, assess
from .forms import TriageAmendForm, TriageForm, parse_blood_pressure, vitals_from
from .models import Triage, TriageAmendment


# --------------------------------------------------------------------------- the waiting list
def queue_rows(user):
    """Patients waiting for a pre-check, most urgent and longest-waiting first."""
    visits = Visit.objects.waiting().select_related("patient", "triage_by").order_by("-priority", "registered_at")
    return [{
        "visit": v, "wait": v.minutes_since(v.registered_at),
        "mine": v.triage_by_id in (None, user.pk), "handler": staff_label(v.triage_by) if v.triage_by else "",
    } for v in visits]


@clinical_required
def triage_queue(request):
    return render(request, "triage/queue.html", {"rows": queue_rows(request.user), "close_outcomes": Visit.CLOSE_OUTCOMES})


@clinical_required
def triage_queue_fragment(request):
    """Just the list, for the page to refresh itself every few seconds."""
    return render(request, "triage/_queue_list.html", {"rows": queue_rows(request.user), "close_outcomes": Visit.CLOSE_OUTCOMES})


@clinical_required
@require_POST
def triage_start(request, pk):
    with transaction.atomic():
        visit = get_object_or_404(Visit.objects.select_for_update(), pk=pk)
        if visit.status == Visit.Status.REGISTERED:
            visit.status = Visit.Status.IN_TRIAGE
            visit.triage_started_at = timezone.now()
            visit.triage_by = request.user
            visit.save(update_fields=["status", "triage_started_at", "triage_by"])
        elif visit.status == Visit.Status.IN_TRIAGE and visit.triage_by_id not in (None, request.user.pk):
            messages.warning(request, f"{staff_label(visit.triage_by)} is already doing this pre-check. Use “Take over” if they have handed it to you.")
            return redirect("triage_queue")
    return redirect("triage_form", pk=pk)


@clinical_required
@require_POST
def triage_takeover(request, pk):
    with transaction.atomic():
        visit = get_object_or_404(Visit.objects.select_for_update().select_related("patient", "triage_by"), pk=pk)
        if visit.status != Visit.Status.IN_TRIAGE:
            messages.info(request, "That pre-check is no longer in progress.")
            return redirect("triage_queue")
        previous = staff_label(visit.triage_by) if visit.triage_by else "nobody"
        visit.triage_by = request.user
        visit.save(update_fields=["triage_by"])
        log(request.user, AuditEntry.Kind.MODIFIED, f"took over the triage pre-check for {visit.patient.full_name} from {previous}", visit.patient)
    return redirect("triage_form", pk=pk)


# --------------------------------------------------------------------------- live hints
@clinical_required
@require_POST
def triage_assess(request, pk):
    """Reference hints and a suggested priority for the numbers typed so far. One source of truth: the server."""
    visit = get_object_or_404(Visit.objects.select_related("patient"), pk=pk)
    data = {}
    for key in ("temp", "pulse", "spo2", "resp", "pain", "weight", "height"):
        try:
            data[key] = float(request.POST.get(key, "").strip())
        except ValueError:
            data[key] = None  # empty or half-typed: just no hint for that box yet
    try:
        data["systolic"], data["diastolic"] = parse_blood_pressure(request.POST.get("bp", ""))
    except ValidationError:
        pass
    result = assess(data, visit.patient.date_of_birth)
    return JsonResponse({"hints": result["hints"], "suggested": result["suggested"], "reasons": result["reasons"]})


# --------------------------------------------------------------------------- the pre-check
def _draft_key(pk):
    return f"triage_draft_{pk}"


DRAFT_HOURS = 12


def _load_draft(session, key):
    draft = session.get(key)
    if not draft:
        return None
    if timezone.now().timestamp() - draft.get("_saved", 0) > DRAFT_HOURS * 3600:
        session.pop(key, None)
        return None
    return {k: v for k, v in draft.items() if k != "_saved"}


@clinical_required
def triage_form(request, pk):
    visit = get_object_or_404(Visit.objects.select_related("patient", "triage_by"), pk=pk)
    patient = visit.patient
    if visit.status != Visit.Status.IN_TRIAGE:
        if visit.status == Visit.Status.REGISTERED:
            messages.info(request, "Start the pre-check from the triage list first.")
        else:
            messages.info(request, "This pre-check has already been recorded.")
        return redirect("triage_queue")
    if visit.triage_by_id not in (None, request.user.pk):
        messages.warning(request, f"{staff_label(visit.triage_by)} is doing this pre-check. Use “Take over” on the list if it has been handed to you.")
        return redirect("triage_queue")

    key = _draft_key(pk)
    if request.method == "POST" and request.POST.get("action") == "draft":
        request.session[key] = {**{k: v for k, v in request.POST.items() if k not in ("csrfmiddlewaretoken", "action")},
                                "_saved": timezone.now().timestamp()}
        messages.success(request, "Progress saved. You can come back and finish this pre-check.")
        return redirect("triage_form", pk=pk)

    draft_loaded = False
    if request.method == "POST":
        form = TriageForm(request.POST, patient=patient)
        if form.is_valid():
            with transaction.atomic():
                visit = Visit.objects.select_for_update().get(pk=pk)
                if visit.status != Visit.Status.IN_TRIAGE:  # someone else saved it first
                    messages.info(request, "This pre-check has already been recorded.")
                    return redirect("triage_queue")
                triage = form.save(commit=False)
                triage.visit = visit
                triage.recorded_by = request.user
                triage.save()
                if "allergies" in form.cleaned_data:
                    patient.allergies = form.cleaned_data["allergies"].strip()
                    patient.save(update_fields=["allergies"])
                    log(request.user, AuditEntry.Kind.MODIFIED, f"recorded the allergies of {patient.full_name}", patient)
                visit.priority = form.cleaned_data["priority"]
                visit.status = Visit.Status.WITH_DOCTOR
                visit.consultation_started_at = timezone.now()
                visit.save(update_fields=["priority", "status", "consultation_started_at"])
                log(request.user, AuditEntry.Kind.MODIFIED, f"recorded vital pre-checks for {patient.full_name}", patient)
            request.session.pop(key, None)
            messages.success(request, f"Pre-check saved. {patient.full_name} is now with the doctor.")
            return redirect("dashboard")
    else:
        draft = _load_draft(request.session, key)
        draft_loaded = bool(draft)
        form = TriageForm(initial=draft or {"priority": visit.priority}, patient=patient)

    return render(request, "triage/form.html", {
        "form": form, "visit": visit, "patient": patient, "wait": visit.minutes_since(visit.registered_at), "draft_loaded": draft_loaded,
        "assess_url": f"/triage/{pk}/assess/",
    })


# --------------------------------------------------------------------------- corrections
AMEND_FIELDS = [
    ("temperature_c", "Temperature"), ("blood_pressure", "Blood pressure"), ("pulse", "Heart rate"), ("respiratory_rate", "Respiratory rate"),
    ("oxygen_sat", "Oxygen saturation"), ("pain_score", "Pain score"), ("weight_kg", "Weight"), ("height_cm", "Height"),
    ("chief_complaint", "Chief complaint"),
]


def _display(triage, name):
    if name == "blood_pressure":
        return f"{triage.systolic} / {triage.diastolic}"
    value = getattr(triage, name)
    return "" if value is None else str(value)


@clinical_required
def triage_amend(request, pk):
    """Correct a recorded vital. The old value is kept on file with who changed it and why."""
    visit = get_object_or_404(Visit.objects.select_related("patient"), pk=pk)
    triage = getattr(visit, "triage", None)
    if triage is None:
        messages.info(request, "There is no recorded pre-check to correct yet.")
        return redirect("patient_detail", pk=visit.patient_id)
    original = Triage.objects.get(pk=triage.pk)  # untouched copy: the form edits `triage` while validating
    form = TriageAmendForm(request.POST or None, instance=triage)
    if request.method == "POST" and form.is_valid():
        new = form.save(commit=False)
        changes = [
            TriageAmendment(triage=triage, field=name, label=label, old_value=_display(original, name)[:60], new_value=_display(new, name)[:60],
                            reason=form.cleaned_data["reason"], amended_by=request.user)
            for name, label in AMEND_FIELDS if _display(original, name) != _display(new, name)
        ]
        if not changes:
            form.add_error(None, "Nothing was changed. Edit a value, or go back.")
        else:
            with transaction.atomic():
                new.save()
                TriageAmendment.objects.bulk_create(changes)
                log(request.user, AuditEntry.Kind.MODIFIED,
                    f"corrected {', '.join(c.label.lower() for c in changes)} for {visit.patient.full_name}", visit.patient)
            suggestion = assess(vitals_from({**form.cleaned_data, "systolic": new.systolic, "diastolic": new.diastolic}), visit.patient.date_of_birth)
            if RANK[suggestion["suggested"]] > RANK[visit.priority]:
                messages.warning(request, f"The corrected vitals now suggest {suggestion['suggested'].title()} level. Please review the patient's priority.")
            messages.success(request, "Correction saved. The original values are kept in the record.")
            return redirect("patient_detail", pk=visit.patient_id)
    return render(request, "triage/amend.html", {"form": form, "visit": visit, "patient": visit.patient})
