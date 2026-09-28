from urllib.parse import urlencode

from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import F, Max, Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme

from apps.accounts.dashboard import CLINICAL_ROLES, doctor_name, is_physician, role_of, staff_label
from apps.accounts.permissions import clinic_staff_required
from apps.audit.models import AuditEntry
from apps.audit.services import log
from apps.history import allergy
from apps.history.forms import ConsultationForm, LabResultForm, PrescriptionForm
from apps.history.attachments import AttachmentForm
from apps.history.models import Attachment, LabResult, Prescription, Visit

from .forms import PatientEditForm, PatientRegistrationForm
from .matching import possible_matches
from .models import Patient, PatientChange

PAGE_SIZE = 10
TABS = ("current", "past", "labs", "prescriptions", "attachments")
GRANT_KEY = "record_access"
GRANT_MINUTES = 30
DRAFT_KEY = "intake_draft"
DRAFT_HOURS = 12

ACCESS_REASONS = [
    ("scheduled", "Preparing for a scheduled or expected visit"),
    ("continuing", "Continuing care / follow-up of this patient"),
    ("requested", "The patient asked for their records"),
    ("emergency", "Emergency: the patient needs urgent care"),
    ("other", "Other (explain below)"),
]


# --------------------------------------------------------------------------- helpers
def _recent_audit(user, patient, kind, minutes=5):
    since = timezone.now() - timezone.timedelta(minutes=minutes)
    return AuditEntry.objects.filter(user=user, patient=patient, kind=kind, created_at__gte=since).exists()


def _has_grant(request, pk):
    granted = request.session.get(GRANT_KEY, {}).get(str(pk))
    return bool(granted) and timezone.now().timestamp() - granted < GRANT_MINUTES * 60


def _timeline_entry(visit):
    consult = getattr(visit, "consultation", None)
    triage = getattr(visit, "triage", None)
    if consult and consult.assessment.strip():
        title = consult.title
    elif triage:
        title = triage.chief_complaint.strip().splitlines()[0][:50]
    elif visit.status in (Visit.Status.CANCELLED, Visit.Status.LEFT):
        title = visit.get_status_display()
    else:
        title = "Awaiting pre-check"
    return {
        "visit": visit, "title": title, "date": timezone.localtime(visit.registered_at).strftime("%b %d, %Y"),
        "doctor": doctor_name(consult.doctor) if consult and consult.doctor else "",
        "current": visit.status in Visit.ACTIVE,
    }


def _triage_info(visit):
    triage = getattr(visit, "triage", None) if visit else None
    if not triage:
        return None
    return {"t": triage, "by": staff_label(triage.recorded_by), "at": timezone.localtime(triage.recorded_at).strftime("%I:%M %p"),
            "amendments": list(triage.amendments.select_related("amended_by"))}


# --------------------------------------------------------------------------- directory
@clinic_staff_required
def patient_list(request):
    """The patient directory: search, filter by status, page through everyone."""
    q = request.GET.get("q", "").strip()
    status = request.GET.get("status", "")
    patients = Patient.objects.annotate(last_visit=Max("visits__registered_at"))
    if q:
        patients = patients.filter(
            Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(code__icontains=q) | Q(phone__icontains=q)
        )
        recent = timezone.now() - timezone.timedelta(minutes=5)
        if not AuditEntry.objects.filter(user=request.user, text="searched the patient directory", created_at__gte=recent).exists():
            log(request.user, AuditEntry.Kind.AUTHORIZED, "searched the patient directory")
    if status in ("active", "inactive"):
        patients = patients.filter(is_active=(status == "active"))
    else:
        status = ""
    patients = patients.order_by(F("last_visit").desc(nulls_last=True), "last_name", "first_name")

    page = Paginator(patients, PAGE_SIZE).get_page(request.GET.get("page"))
    today = timezone.localdate()
    rows = []
    for p in page.object_list:
        if p.last_visit is None:
            last = "—"
        else:
            day = timezone.localtime(p.last_visit).date()
            last = "Today" if day == today else day.strftime("%b %d, %Y")
        rows.append({"patient": p, "last_visit": last})

    filters = {k: v for k, v in (("q", q), ("status", status)) if v}
    return render(request, "patients/list.html", {
        "rows": rows, "page": page, "q": q, "status": status,
        "total_patients": Patient.objects.count(), "qs": urlencode(filters),
    })


# --------------------------------------------------------------------------- the record
@clinic_staff_required
def patient_access(request, pk):
    """Asks for a reason before opening the record of a patient who isn't in today's queue, and logs it."""
    patient = get_object_or_404(Patient, pk=pk)
    error = ""
    if request.method == "POST":
        reason = request.POST.get("reason", "")
        note = request.POST.get("note", "").strip()
        labels = dict(ACCESS_REASONS)
        if reason not in labels:
            error = "Please choose a reason."
        elif reason == "other" and not note:
            error = "Please explain why you need this record."
        else:
            text = f"opened the record of {patient.full_name} — reason: {labels[reason]}" + (f" ({note})" if note else "")
            if reason == "emergency":
                text += " [EMERGENCY ACCESS]"
            log(request.user, AuditEntry.Kind.AUTHORIZED, text[:255], patient)
            grants = request.session.get(GRANT_KEY, {})
            grants[str(pk)] = timezone.now().timestamp()
            request.session[GRANT_KEY] = grants
            target = request.POST.get("next") or ""
            if not url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()}):
                target = reverse("patient_detail", args=[pk])
            return redirect(target)
    return render(request, "patients/access.html", {"patient": patient, "reasons": ACCESS_REASONS, "error": error,
                                                      "next": request.GET.get("next", ""), "chosen": request.POST.get("reason", "")})


@clinic_staff_required
def patient_detail(request, pk):
    """The patient's record. Nurses and physicians see the consultation suite; the front desk sees a limited view."""
    patient = get_object_or_404(Patient, pk=pk)
    role = role_of(request.user)
    visits = list(patient.visits.select_related("triage", "triage__recorded_by", "consultation", "consultation__doctor"))
    current = next((v for v in visits if v.status in Visit.ACTIVE), None)

    # "Minimum necessary": records of people who are not in today's queue need a stated reason.
    if current is None and not _has_grant(request, pk):
        return redirect(f"{reverse('patient_access', args=[pk])}?next={request.path}")
    if not _recent_audit(request.user, patient, AuditEntry.Kind.AUTHORIZED):
        log(request.user, AuditEntry.Kind.AUTHORIZED, f"opened the record of {patient.full_name}", patient)

    if role not in CLINICAL_ROLES:
        if request.method == "POST":
            return HttpResponseForbidden("Vitals, notes, prescriptions and lab results are for nurses and physicians only.")
        return render(request, "patients/detail_frontdesk.html", {
            "patient": patient, "current": current, "visits": visits, "close_outcomes": Visit.CLOSE_OUTCOMES,
        })

    tab = request.GET.get("tab", "current")
    if tab not in TABS:
        tab = "current"
    past = [v for v in visits if v.status == Visit.Status.COMPLETED]
    selected = next((v for v in past if str(v.pk) == request.GET.get("visit")), past[0] if past else None)
    if request.GET.get("visit") and selected and tab == "current":
        tab = "past"

    consult = getattr(current, "consultation", None) if current else None
    can_write = bool(current and current.status == Visit.Status.WITH_DOCTOR and is_physician(request.user))
    form = ConsultationForm(instance=consult) if can_write else None
    rx_form = lab_form = None
    allergy_warning = ""

    if request.method == "POST":
        which = request.POST.get("form")
        if which == "rx":
            if not can_write:
                return HttpResponseForbidden("Only the physician on a visit in consultation can prescribe.")
            rx_form = PrescriptionForm(request.POST)
            if rx_form.is_valid():
                med = rx_form.cleaned_data["medication"]
                allergy_warning = allergy.check(patient, med)
                if allergy_warning and not rx_form.cleaned_data["override_allergy"]:
                    rx_form.add_error(None, "Allergy check: " + allergy_warning + " Tick the box to confirm you have reviewed this.")
                else:
                    rx = rx_form.save(commit=False)
                    rx.visit, rx.prescribed_by, rx.allergy_warning = current, request.user, allergy_warning[:255]
                    rx.save()
                    log(request.user, AuditEntry.Kind.MODIFIED, f"prescribed {rx.medication} for {patient.full_name}"
                        + (" (allergy warning overridden)" if allergy_warning else ""), patient)
                    messages.success(request, f"Prescription added: {rx.medication} {rx.dose}.")
                    return redirect(f"{request.path}?tab=prescriptions")
            tab = "prescriptions"
        elif which == "lab":
            if role not in CLINICAL_ROLES:
                return HttpResponseForbidden("Only nurses and physicians can enter lab results.")
            lab_form = LabResultForm(request.POST)
            if lab_form.is_valid():
                result = lab_form.save(commit=False)
                result.patient, result.visit, result.entered_by = patient, current, request.user
                result.save()
                log(request.user, AuditEntry.Kind.MODIFIED, f"added the lab result {result.test_name} for {patient.full_name}", patient)
                messages.success(request, f"Lab result added: {result.test_name}.")
                return redirect(f"{request.path}?tab=labs")
            tab = "labs"

    if tab == "prescriptions" and can_write and rx_form is None:
        rx_form = PrescriptionForm()
    if tab == "labs" and lab_form is None:
        lab_form = LabResultForm()

    return render(request, "patients/detail.html", {
        "patient": patient, "tab": tab,
        "tabs": [("current", "Current Visit"), ("past", "Past Visits"), ("labs", "Lab Results"), ("prescriptions", "Prescriptions"),
                 ("attachments", "Attachments")],
        "files": patient.attachments.filter(withdrawn_at__isnull=True).defer("content").select_related("uploaded_by", "reviewed_by"),
        "attach_form": AttachmentForm(),
        "pending_files": patient.attachments.filter(withdrawn_at__isnull=True, review_status=Attachment.Review.PENDING).count(),
        "current": current, "consult": consult, "can_write": can_write, "form": form, "is_doctor": is_physician(request.user),
        "current_triage": _triage_info(current), "selected": selected, "selected_triage": _triage_info(selected),
        "selected_consult": getattr(selected, "consultation", None) if selected else None,
        "timeline": [_timeline_entry(v) for v in visits], "has_past": bool(past),
        "saved_at": timezone.localtime(consult.updated_at).strftime("%I:%M %p") if consult else "",
        "rx_form": rx_form, "lab_form": lab_form, "allergy_warning": allergy_warning,
        "prescriptions": Prescription.objects.filter(visit__patient=patient).select_related("visit", "prescribed_by"),
        "lab_results": LabResult.objects.filter(patient=patient).select_related("entered_by"),
        "close_outcomes": Visit.CLOSE_OUTCOMES,
    })


@clinic_staff_required
def patient_edit(request, pk):
    """Update contact details, allergies and the emergency contact. Every change is kept in the patient's history."""
    patient = get_object_or_404(Patient, pk=pk)
    form = PatientEditForm(request.POST or None, instance=Patient.objects.get(pk=pk))
    if request.method == "POST" and form.is_valid():
        reason = form.cleaned_data["reason"]
        changes = []
        for name in PatientEditForm.EDITABLE:
            old, new = str(getattr(patient, name) or ""), str(form.cleaned_data.get(name) or "")
            if old != new:
                label = form.fields[name].label
                changes.append(PatientChange(patient=patient, field=name, label=label, old_value=old[:255], new_value=new[:255],
                                             reason=reason, changed_by=request.user))
        if not changes:
            messages.info(request, "Nothing was changed.")
            return redirect("patient_detail", pk=pk)
        with transaction.atomic():
            form.save()
            PatientChange.objects.bulk_create(changes)
            log(request.user, AuditEntry.Kind.MODIFIED,
                f"updated {', '.join(c.label.lower() for c in changes)} for {patient.full_name}", patient)
        messages.success(request, "Details updated. The previous values are kept in the change history.")
        return redirect("patient_detail", pk=pk)
    return render(request, "patients/edit.html", {"patient": patient, "form": form, "history": patient.changes.select_related("changed_by")[:15]})


# --------------------------------------------------------------------------- intake
def _draft_fresh(session):
    draft = session.get(DRAFT_KEY)
    if not draft:
        return None
    if timezone.now().timestamp() - draft.get("_saved", 0) > DRAFT_HOURS * 3600:
        session.pop(DRAFT_KEY, None)  # unfinished drafts hold personal details: don't keep them around
        return None
    return {k: v for k, v in draft.items() if k != "_saved"}


def _queue_visit(request, patient, returning):
    """Add a visit for `patient` to today's queue and log it."""
    Visit.objects.create(patient=patient, created_by=request.user)
    log(request.user, AuditEntry.Kind.CREATED,
        f"checked in returning patient {patient.full_name}" if returning else f"registered new patient {patient.full_name}", patient)
    request.session.pop(DRAFT_KEY, None)
    messages.success(request, (f"Existing record opened for {patient.full_name} ({patient.code})." if returning
                               else f"{patient.full_name} was registered as {patient.code}.") + " Ready for triage pre-check.")


@clinic_staff_required
def patient_create(request):
    """Digital registration: register a patient (or reopen their record) and send them to triage."""
    session = request.session
    if request.method == "POST":
        action = request.POST.get("action", "register")
        if action == "discard":
            session.pop(DRAFT_KEY, None)
            messages.info(request, "Draft discarded.")
            return redirect("patient_create")
        if action == "draft":
            session[DRAFT_KEY] = {**{k: v for k, v in request.POST.items() if k not in ("csrfmiddlewaretoken", "action", "confirm_new", "use_patient")},
                                  "_saved": timezone.now().timestamp()}
            messages.success(request, "Draft saved. It will be here the next time you open New Intake.")
            return redirect("patient_create")

        # The person picked an existing record from the "possible matches" list.
        if request.POST.get("use_patient"):
            patient = get_object_or_404(Patient, pk=request.POST["use_patient"])
            if patient.visits.filter(status__in=Visit.ACTIVE).exists():
                messages.error(request, f"{patient.full_name} ({patient.code}) is already in today's queue.")
                return redirect("patient_create")
            _queue_visit(request, patient, returning=True)
            return redirect("triage_queue" if role_of(request.user) in CLINICAL_ROLES else "dashboard")

        form = PatientRegistrationForm(request.POST)
        matches = []
        if form.is_valid():
            cd = form.cleaned_data
            existing = Patient.objects.filter(
                first_name__iexact=cd["first_name"], last_name__iexact=cd["last_name"], date_of_birth=cd["date_of_birth"],
            ).first()
            if existing and existing.visits.filter(status__in=Visit.ACTIVE).exists():
                form.add_error(None, f"{existing.full_name} ({existing.code}) is already in today's queue.")
            elif existing is None and not request.POST.get("confirm_new") and (
                    matches := possible_matches(cd["first_name"], cd["last_name"], cd["date_of_birth"], cd["phone"])):
                pass  # show the possible matches and ask before creating a second record
            else:
                with transaction.atomic():
                    if existing:
                        patient, returning = existing, True
                    else:
                        patient = form.save(commit=False)
                        patient.created_by = request.user
                        patient.save()
                        returning = False
                    _queue_visit(request, patient, returning)
                return redirect("triage_queue" if role_of(request.user) in CLINICAL_ROLES else "dashboard")
        return render(request, "patients/form.html", {"form": form, "draft_loaded": False, "matches": matches})

    draft = _draft_fresh(session)
    return render(request, "patients/form.html", {"form": PatientRegistrationForm(initial=draft or None), "draft_loaded": bool(draft), "matches": []})


# --------------------------------------------------------------------------- student portal account
@clinic_staff_required
def patient_link_account(request, pk):
    """Connect a student's portal login to their clinic record, after staff have checked their ID."""
    from django.contrib.auth import get_user_model

    from apps.accounts.models import Profile

    patient = get_object_or_404(Patient, pk=pk)
    if request.method != "POST":
        return redirect("patient_edit", pk=pk)
    if patient.user_id:
        messages.error(request, "This record is already linked to a portal account.")
        return redirect("patient_edit", pk=pk)
    student_id = request.POST.get("student_id", "").strip()
    profile = Profile.objects.select_related("user").filter(role=Profile.Role.STUDENT, student_id__iexact=student_id).first() if student_id else None
    if profile is None:
        messages.error(request, "No student account was found with that student ID.")
    elif profile.date_of_birth != patient.date_of_birth:
        messages.error(request, "That student's registered date of birth does not match this patient. Check their ID before linking.")
    elif Patient.objects.filter(user=profile.user).exists():
        messages.error(request, "That student account is already linked to another record.")
    else:
        patient.user = profile.user
        patient.save(update_fields=["user"])
        log(request.user, AuditEntry.Kind.MODIFIED, f"linked the student portal account of {patient.full_name}", patient)
        messages.success(request, f"Portal account linked. {patient.first_name} can now see their own record at the student portal.")
    return redirect("patient_edit", pk=pk)


@clinic_staff_required
def patient_unlink_account(request, pk):
    patient = get_object_or_404(Patient, pk=pk)
    if request.method == "POST" and patient.user_id:
        patient.user = None
        patient.save(update_fields=["user"])
        log(request.user, AuditEntry.Kind.MODIFIED, f"unlinked the student portal account of {patient.full_name}", patient)
        messages.success(request, "Portal account unlinked. The student can no longer see this record.")
    return redirect("patient_edit", pk=pk)
