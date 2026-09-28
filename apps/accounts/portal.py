"""The student portal: read-only views of a student's own record, plus sending documents to the clinic.

Every query here starts from the signed-in user's own linked record. There is no patient id in any URL,
so a student cannot ask for someone else's data by changing a number.
"""
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.audit.models import AuditEntry
from apps.audit.services import log
from apps.history import attachments as files
from apps.history.models import Attachment, LabResult, Prescription, Visit
from apps.patients.models import Patient
from apps.triage.assessment import assess
from apps.triage.models import Triage

from .dashboard import doctor_name, landing_for


def student_required(view):
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if landing_for(request.user) != "student":
            return HttpResponseForbidden("The student portal is for student accounts.")
        return view(request, *args, **kwargs)

    return login_required(wrapper)


def _record(user):
    return Patient.objects.filter(user=user).first()


def _log_view(user, patient):
    since = timezone.now() - timezone.timedelta(minutes=5)
    if not AuditEntry.objects.filter(user=user, patient=patient, text="viewed their own health record", created_at__gte=since).exists():
        log(user, AuditEntry.Kind.AUTHORIZED, "viewed their own health record", patient)


def _friendly(hint, ok_label):
    """Patient-facing wording: calm labels when fine, 'Discuss with clinic' (never alarming words) otherwise."""
    if not hint:
        return None
    label, tone = hint
    return (ok_label(label) if tone == "ok" else "Discuss with clinic", "ok" if tone == "ok" else "warn")


def _vital_tiles(patient):
    readings = list(Triage.objects.filter(visit__patient=patient).order_by("-recorded_at")[:2])
    if not readings:
        return []
    latest = readings[0]
    when = timezone.localtime(latest.recorded_at).strftime("%b %d, %Y")
    hints = assess({
        "temp": float(latest.temperature_c), "systolic": latest.systolic, "diastolic": latest.diastolic, "pulse": float(latest.pulse),
    }, patient.date_of_birth)["hints"]
    temp, bp, pulse = (_friendly(hints.get("temp"), lambda _: "Normal"), _friendly(hints.get("bp"), lambda l: "Optimal" if l == "Optimal" else "Normal"),
                       _friendly(hints.get("pulse"), lambda _: "Normal"))
    kg = float(latest.weight_kg)
    if len(readings) == 2:
        change = abs(kg - float(readings[1].weight_kg))
        weight = ("Stable", "info") if change <= 2 else ("Changed", "info")
    else:
        weight = ("Recorded", "info")
    celsius = float(latest.temperature_c)
    return [
        {"label": "Temperature", "value": f"{celsius:.1f}", "unit": "°C", "meta": f"{celsius * 9 / 5 + 32:.1f} °F · Last checked {when}", "badge": temp},
        {"label": "Blood pressure", "value": f"{latest.systolic}/{latest.diastolic}", "unit": "mmHg", "meta": f"Last checked {when}", "badge": bp},
        {"label": "Heart rate", "value": f"{latest.pulse}", "unit": "bpm", "meta": f"Last checked {when}", "badge": pulse},
        {"label": "Weight", "value": f"{kg:.0f}" if kg == int(kg) else f"{kg:.1f}", "unit": "kg", "meta": f"{kg * 2.20462:.0f} lbs · Last checked {when}", "badge": weight},
    ]


def _visit_summaries(patient, limit=3):
    visits = (Visit.objects.filter(patient=patient, status=Visit.Status.COMPLETED, consultation__completed_at__isnull=False)
              .select_related("consultation", "consultation__doctor").order_by("-registered_at")[:limit])
    return [{
        "date": timezone.localtime(v.registered_at).strftime("%b %d, %Y"), "doctor": doctor_name(v.consultation.doctor),
        "title": v.consultation.title,
        "text": v.consultation.patient_summary or "Your clinician didn't add a summary for this visit. Ask the student health clinic if you would like details.",
    } for v in visits]


@student_required
def portal_profile(request):
    patient = _record(request.user)
    profile = getattr(request.user, "profile", None)
    if patient is None:
        return render(request, "portal/profile.html", {"patient": None, "profile": profile, "active": "profile"})
    _log_view(request.user, patient)
    return render(request, "portal/profile.html", {
        "patient": patient, "profile": profile, "active": "profile", "tiles": _vital_tiles(patient), "summaries": _visit_summaries(patient),
    })


def _portal_files(patient):
    from django.db.models import Q

    return (Attachment.objects.filter(patient=patient, withdrawn_at__isnull=True).defer("content")
            .filter(Q(source=Attachment.Source.PATIENT) |
                    Q(source=Attachment.Source.CLINIC, visible_to_patient=True, review_status=Attachment.Review.ACCEPTED)))


@student_required
def portal_records(request):
    patient = _record(request.user)
    context = {"patient": patient, "active": "records"}
    if patient is not None:
        _log_view(request.user, patient)
        context.update(
            files=_portal_files(patient), upload_form=files.AttachmentForm(from_patient=True),
            lab_results=LabResult.objects.filter(patient=patient), prescriptions=Prescription.objects.filter(visit__patient=patient),
            pending=Attachment.objects.filter(patient=patient, source=Attachment.Source.PATIENT, review_status=Attachment.Review.PENDING,
                                              withdrawn_at__isnull=True).count(),
            max_pending=files.MAX_PENDING_PER_PATIENT,
        )
    return render(request, "portal/records.html", context)


@student_required
@require_POST
def portal_upload(request):
    patient = _record(request.user)
    if patient is None:
        messages.error(request, "Your account isn't linked to a clinic record yet, so documents can't be sent.")
        return redirect("portal_records")
    waiting = Attachment.objects.filter(patient=patient, source=Attachment.Source.PATIENT, review_status=Attachment.Review.PENDING,
                                        withdrawn_at__isnull=True).count()
    if waiting >= files.MAX_PENDING_PER_PATIENT:
        messages.error(request, f"You already have {waiting} documents waiting for review. Please wait until the clinic has looked at them.")
        return redirect("portal_records")
    form = files.AttachmentForm(request.POST, request.FILES, from_patient=True)
    if not form.is_valid():
        messages.error(request, " ".join(e for errors in form.errors.values() for e in errors))
        return redirect("portal_records")
    item = files.store(form, patient, request.user, source=Attachment.Source.PATIENT)
    log(request.user, AuditEntry.Kind.CREATED, f"sent the file “{item.filename}” to the clinic", patient)
    messages.success(request, "Thank you. The clinic will review your document before it is added to your record.")
    return redirect("portal_records")


@student_required
def portal_visits(request):
    patient = _record(request.user)
    context = {"patient": patient, "active": "visits"}
    if patient is not None:
        _log_view(request.user, patient)
        rows = []
        for v in Visit.objects.filter(patient=patient).select_related("consultation", "consultation__doctor"):
            consult = getattr(v, "consultation", None)
            rows.append({"visit": v, "when": timezone.localtime(v.registered_at),
                         "doctor": doctor_name(consult.doctor) if consult and consult.doctor else "",
                         "title": consult.title if consult and consult.is_completed else ""})
        context["rows"] = rows
    return render(request, "portal/visits.html", context)
