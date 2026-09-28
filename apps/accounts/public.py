"""Live but anonymous figures for the public landing page.

The landing page can be seen without signing in, so nothing here may identify a patient or a staff member:
only counts, stages, job roles and how long ago something happened.
"""
from django.core.cache import cache
from django.utils import timezone

from apps.audit.models import AuditEntry
from apps.history.models import Attachment, Consultation, Visit
from apps.patients.models import Patient

CACHE_SECONDS = 30
ROLE_WORDS = {"physician": "A physician", "nurse": "A nurse", "receptionist": "A receptionist", "administrator": "An administrator",
              "student": "A student"}


def _who(entry):
    if entry.user is None:
        return "The system"
    profile = getattr(entry.user, "profile", None)
    if profile and profile.role in ROLE_WORDS:
        return ROLE_WORDS[profile.role]
    return "An administrator" if entry.user.is_superuser else "A staff member"


def _describe(entry):
    """(badge, style, sentence) without names, patient details or free text."""
    has_patient = entry.patient_id is not None
    text = entry.text.lower()
    if entry.kind == AuditEntry.Kind.CREATED:
        return "CREATED", "green", "registered a patient" if has_patient else "created an account"
    if entry.kind == AuditEntry.Kind.AUTHORIZED:
        return "AUTHORIZED", "green", "opened a patient record" if has_patient else "searched the directory"
    if entry.kind == AuditEntry.Kind.MODIFIED:
        if "vital" in text:
            what = "recorded triage vitals"
        elif "consultation" in text or "medical records" in text:
            what = "updated consultation notes"
        elif "prescri" in text:
            what = "added a prescription"
        elif "lab result" in text:
            what = "added a lab result"
        elif "file" in text:
            what = "managed a patient document"
        else:
            what = "updated a record" if has_patient else "updated an account"
        return "MODIFIED", "blue", what
    return "SYSTEM", "gray", "ran a scheduled task"


def _ago(moment):
    seconds = int((timezone.now() - moment).total_seconds())
    if seconds < 60:
        return "just now"
    if seconds < 3600:
        return f"{seconds // 60} min ago"
    if seconds < 86400:
        return f"{seconds // 3600} h ago"
    return timezone.localtime(moment).strftime("%b %d")


def recent_activity(limit):
    entries = (AuditEntry.objects.exclude(kind__in=[AuditEntry.Kind.SIGN_IN, AuditEntry.Kind.SIGN_IN_FAILED])
               .select_related("user", "user__profile")[:limit])
    rows = []
    for e in entries:
        badge, style, what = _describe(e)
        rows.append({"who": _who(e), "what": what, "badge": badge, "style": style, "ago": _ago(e.created_at)})
    return rows


def snapshot():
    data = cache.get("public-snapshot")
    if data is not None:
        return data
    day_start = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
    active = Visit.objects.filter(status__in=Visit.ACTIVE)
    stages = {s: active.filter(status=s).count() for s in (Visit.Status.REGISTERED, Visit.Status.IN_TRIAGE, Visit.Status.WITH_DOCTOR)}
    data = {
        "updated": timezone.localtime().strftime("%I:%M %p"),
        "patients": Patient.objects.count(),
        "visits_today": Visit.objects.filter(registered_at__gte=day_start).exclude(status=Visit.Status.CANCELLED).count(),
        "consultations": Consultation.objects.filter(completed_at__isnull=False).count(),
        "documents": Attachment.objects.filter(withdrawn_at__isnull=True).count(),
        "active": active.count(),
        "registered": stages[Visit.Status.REGISTERED], "in_triage": stages[Visit.Status.IN_TRIAGE], "with_doctor": stages[Visit.Status.WITH_DOCTOR],
        "completed_today": Visit.objects.filter(completed_at__gte=day_start).count(),
        "audit_total": AuditEntry.objects.count(),
        "activity": recent_activity(4),
    }
    cache.set("public-snapshot", data, CACHE_SECONDS)
    return data
