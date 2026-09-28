"""Helpers for the signed-in dashboards."""
from django.db.models import Avg, DurationField, ExpressionWrapper, F
from django.utils import timezone

from .forms import CLINIC_STAFF, STUDENT

ADMINISTRATOR = "Administrator"

TITLES = {"physician": "Dr."}

def in_group(user, name):
    return user.groups.filter(name=name).exists()


def landing_for(user):
    """Which dashboard a user sees: 'admin', 'staff', 'student' or None."""
    if user.is_superuser or in_group(user, ADMINISTRATOR):
        return "admin"
    if in_group(user, CLINIC_STAFF):
        return "staff"
    if in_group(user, STUDENT):
        return "student"
    return None


def _profile(user):
    return getattr(user, "profile", None)


def shell_context(user):
    """Name, initials and role line for the sidebar."""
    profile = _profile(user)
    role = profile.role if profile else ""
    title = TITLES.get(role, "")
    full = user.get_full_name() or user.get_username()
    display = f"{title} {full}".strip()
    if profile and profile.role == "student":
        role_label = f"Student (ID: {profile.student_id})" if profile.student_id else "Student"
    elif profile:
        role_label = profile.get_role_display()
        if profile.department:
            role_label += f" · {profile.department}"
    elif user.is_superuser or in_group(user, ADMINISTRATOR):
        role_label = "System Administrator"
    else:
        role_label = "Staff"
    return {
        "role": role, "clinical": role in ("nurse", "physician"),
        "display_name": display,
        "initials": "".join(w[0] for w in display.split() if w[0].isalpha())[:3].upper(),
        "role_label": role_label,
    }


def greeting_for(user):
    hour = timezone.localtime().hour
    part = "Morning" if hour < 12 else "Afternoon" if hour < 17 else "Evening"
    profile = _profile(user)
    title = TITLES.get(profile.role, "") if profile else ""
    name = f"{title} {user.last_name}".strip() if title and user.last_name else (user.first_name or user.get_username())
    return f"Good {part}, {name}!"


def fmt_minutes(minutes):
    if minutes < 60:
        return f"{minutes}m"
    if minutes < 1440:
        return f"{minutes // 60}h {minutes % 60:02d}m"
    return f"{minutes // 1440}d {(minutes % 1440) // 60}h"


def _plural(n, word):
    return f"{n} {word}" + ("" if n == 1 else "s")


def _avg_wait_minutes(start, end):
    """Average minutes between registration and the start of the pre-check for visits in [start, end)."""
    from apps.history.models import Visit

    wait = ExpressionWrapper(F("triage_started_at") - F("registered_at"), output_field=DurationField())
    avg = (Visit.objects.filter(registered_at__gte=start, registered_at__lt=end, triage_started_at__isnull=False)
           .aggregate(a=Avg(wait))["a"])
    return None if avg is None else round(avg.total_seconds() / 60)


def staff_dashboard_context(user):
    """Live numbers, queue and the signed-in user's own recent activity."""
    from apps.audit.models import AuditEntry
    from apps.history.models import Visit

    now = timezone.now()
    day_start = timezone.localtime(now).replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday_start = day_start - timezone.timedelta(days=1)

    today = Visit.objects.filter(registered_at__gte=day_start).exclude(status=Visit.Status.CANCELLED)
    waiting = list(Visit.objects.waiting())
    waiting_now = len(waiting)
    avg_waiting = round(sum(v.minutes_since(v.registered_at) for v in waiting) / waiting_now) if waiting_now else 0
    completed = Visit.objects.filter(completed_at__gte=day_start).count()
    last_hour = today.filter(registered_at__gte=now - timezone.timedelta(hours=1)).count()

    today_avg = _avg_wait_minutes(day_start, now + timezone.timedelta(days=1))
    yesterday_avg = _avg_wait_minutes(yesterday_start, day_start)
    if today_avg is None:
        wait_value, wait_sub = "—", "No pre-checks started yet"
    else:
        wait_value = f"{today_avg} min"
        if yesterday_avg is None:
            wait_sub = "No data from yesterday"
        else:
            diff = today_avg - yesterday_avg
            wait_sub = "Same as yesterday" if diff == 0 else f"{diff:+d} min from yesterday"

    stat_cards = [
        {"label": "Patients Today", "value": today.count(), "sub": f"+{last_hour} registered last hour"},
        {"label": "In Queue", "value": waiting_now, "sub": f"Avg wait: {avg_waiting} mins"},
        {"label": "Avg Wait Time", "value": wait_value, "sub": wait_sub},
        {"label": "Completed", "value": completed, "sub": "Consultations finished today"},
    ]

    queue = []
    for v in Visit.objects.active().select_related("patient").order_by("-priority", "registered_at"):
        if v.status == Visit.Status.WITH_DOCTOR:
            label, tone = "With Doctor", "green"
            wait = f"{fmt_minutes(v.minutes_since(v.consultation_started_at or v.registered_at))} session"
        else:
            if v.priority == Visit.Priority.URGENT:
                label, tone = "Urgent", "red"
            elif v.priority == Visit.Priority.PRIORITY:
                label, tone = "Priority", "yellow"
            else:
                label, tone = ("In Triage", "yellow") if v.status == Visit.Status.IN_TRIAGE else ("Registered", "blue")
            wait = f"Waiting {fmt_minutes(v.minutes_since(v.registered_at))}"
        queue.append({
            "pk": v.patient_id, "name": v.patient.full_name, "initials": v.patient.initials, "pid": v.patient.code,
            "dob": v.patient.date_of_birth.strftime("%b %d, %Y"), "stage": v.stage,
            "status": label, "tone": tone, "wait": wait,
        })

    activity = []
    for e in AuditEntry.objects.filter(user=user).exclude(kind__in=[AuditEntry.Kind.SIGN_IN, AuditEntry.Kind.SIGN_IN_FAILED])[:4]:
        when = timezone.localtime(e.created_at)
        stamp = when.strftime("%I:%M %p") if when >= day_start else when.strftime("%b %d, %I:%M %p")
        activity.append({"time": stamp, "kind": e.kind, "text": f"You {e.text}"})

    stale_count = Visit.objects.active().filter(registered_at__lt=day_start).count()
    alerts = [
        {"id": f"u{v.pk}", "kind": "urgent", "text": f"Urgent patient waiting: {v.patient.full_name}"}
        for v in Visit.objects.waiting().filter(priority=Visit.Priority.URGENT).select_related("patient")
    ] + [
        {"id": f"r{v.pk}", "kind": "ready", "text": f"{v.patient.full_name} is ready for consultation"}
        for v in Visit.objects.filter(status=Visit.Status.WITH_DOCTOR).select_related("patient")
    ]

    return {
        "alerts": alerts, "stale_count": stale_count,
        "stat_cards": stat_cards, "queue": queue, "activity": activity,
        "queue_count": waiting_now, "waiting_label": _plural(waiting_now, "patient"), "completed_today": completed,
    }


def staff_label(user):
    """How a staff member is named on records: 'Dr. Henderson', 'Nurse Reyes', or their full name."""
    if user is None:
        return "—"
    profile = _profile(user)
    role = profile.role if profile else ""
    if role == "physician":
        return f"Dr. {user.last_name}".strip() if user.last_name else user.get_username()
    if role == "nurse":
        return f"Nurse {user.last_name}".strip() if user.last_name else user.get_username()
    return user.get_full_name() or user.get_username()


def doctor_name(user):
    """Full display name with title, e.g. 'Dr. Clara Henderson'."""
    if user is None:
        return ""
    profile = _profile(user)
    full = user.get_full_name() or user.get_username()
    return f"Dr. {full}" if profile and profile.role == "physician" else full


def is_physician(user):
    profile = _profile(user)
    return bool(profile and profile.role == "physician")


CLINICAL_ROLES = ("nurse", "physician")


def role_of(user):
    profile = _profile(user)
    return profile.role if profile else ""


# Which parts of the site each kind of account may use. Anything else goes to that person's own home page.
AREAS = {
    "admin": ("/manage/", "/admin/", "/account/"),
    "student": ("/portal/", "/history/files/", "/account/"),
    "staff": ("/dashboard/", "/patients/", "/history/", "/account/"),
}
CLINICAL_ONLY = ("/triage/",)


def safe_next(user, url):
    """The page to open after sign-in: `url` if this account may use it, otherwise their dashboard."""
    from urllib.parse import urlparse

    path = urlparse(url or "").path
    landing = landing_for(user)
    allowed = AREAS.get(landing, ())
    if landing == "staff" and role_of(user) in CLINICAL_ROLES:
        allowed += CLINICAL_ONLY
    return url if path and any(path.startswith(prefix) for prefix in allowed) else "/dashboard/"
