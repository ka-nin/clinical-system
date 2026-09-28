"""System administration: accounts, access and the audit trail.

Administrators manage who can sign in and read what happened. They do not see patient records: that would go
against "minimum necessary" access, and they have no clinical role.
"""
import csv
from datetime import timedelta
from urllib.parse import urlencode

from axes.models import AccessAttempt
from axes.utils import reset as reset_lockout
from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import url_has_allowed_host_and_scheme, urlsafe_base64_encode
from django.views.decorators.http import require_POST

from apps.audit.models import AuditEntry
from apps.audit.services import log, verify_chain

from .dashboard import ADMINISTRATOR
from .forms import CLINIC_STAFF, STUDENT
from .models import Profile, TwoFactor
from .permissions import admin_required

User = get_user_model()
PAGE_SIZE = 10
LOG_PAGE_SIZE = 25
EMERGENCY_TAG = "[EMERGENCY ACCESS]"

KIND_LABEL = {"admin": "Administrator", "staff": "Clinic Staff", "student": "Student", "other": "No role"}
STAFF_ROLES = [Profile.Role.RECEPTIONIST, Profile.Role.NURSE, Profile.Role.PHYSICIAN]
GROUP_FOR_KIND = {"admin": ADMINISTRATOR, "staff": CLINIC_STAFF, "student": STUDENT}


# --------------------------------------------------------------------------- reading users
def kind_of(user):
    """'admin', 'staff', 'student' or 'other'. Uses prefetched groups so lists stay fast."""
    names = {g.name for g in user.groups.all()}
    if user.is_superuser or ADMINISTRATOR in names:
        return "admin"
    if CLINIC_STAFF in names:
        return "staff"
    if STUDENT in names:
        return "student"
    return "other"


def _profile(user):
    return getattr(user, "profile", None)


def status_of(user):
    """('active'|'pending'|'inactive'|'denied', label). Students are 'pending' until clinic staff link them to a record."""
    profile = _profile(user)
    kind = kind_of(user)
    if user.is_active:
        if kind == "student" and getattr(user, "patient_record", None) is None:
            return "pending", "Pending"
        return "active", "Active"
    if kind == "staff" and profile is not None:
        if profile.denied_at:
            return "denied", "Denied"
        if profile.reviewed_at is None and user.last_login is None:
            return "pending", "Pending"
    return "inactive", "Inactive"


def last_login_label(user):
    if user.last_login is None:
        return "Never"
    when = timezone.localtime(user.last_login)
    days = (timezone.localdate() - when.date()).days
    clock = when.strftime("%I:%M %p")
    if days == 0:
        return f"Today, {clock}"
    if days == 1:
        return f"Yesterday, {clock}"
    return when.strftime("%b %d, %Y, ") + clock


def display_name(user):
    profile = _profile(user)
    name = user.get_full_name() or user.get_username()
    return f"Dr. {name}" if profile and profile.role == Profile.Role.PHYSICIAN else name


def initials(user):
    words = (user.get_full_name() or user.get_username()).split()
    return "".join(w[0] for w in words if w[0].isalpha())[:2].upper()


def job_line(user):
    profile = _profile(user)
    if profile is None:
        return ""
    line = profile.get_role_display()
    return f"{line} · {profile.department}" if profile.department else line


def _rows(users):
    return [{"user": u, "kind": kind_of(u), "kind_label": KIND_LABEL[kind_of(u)], "status": status_of(u), "last": last_login_label(u),
             "name": display_name(u), "job": job_line(u)} for u in users]


def _audit(request, text, patient=None):
    log(request.user, AuditEntry.Kind.MODIFIED, text[:255], patient)


def _back(request, default="manage_users"):
    target = request.POST.get("next", "")
    if target and url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()}):
        return redirect(target)
    return redirect(default)


def _active_admins():
    return User.objects.filter(is_active=True).filter(Q(is_superuser=True) | Q(groups__name=ADMINISTRATOR)).distinct()


def _temporary_password():
    import secrets

    words = ["Maple", "River", "Cedar", "Harbor", "Summit", "Willow", "Falcon", "Meadow"]
    return f"{secrets.choice(words)}-{secrets.choice(words)}-{secrets.randbelow(9000) + 1000}"


# --------------------------------------------------------------------------- emails
def send_password_link(request, user, *, new_account):
    """Email a link so the person can choose (or reset) their own password. Nobody ever knows it but them."""
    url = request.build_absolute_uri(reverse("password_reset_confirm", args=[urlsafe_base64_encode(force_bytes(user.pk)),
                                                                              default_token_generator.make_token(user)]))
    intro = ("An account has been created for you on CareBoard. Choose a password to start using it:" if new_account
             else "A CareBoard administrator sent you this link to reset your password:")
    send_mail("Set your CareBoard password" if new_account else "Reset your CareBoard password",
              f"Hello {user.first_name or ''},\n\n{intro}\n\n{url}\n\nThe link works for {settings.PASSWORD_RESET_TIMEOUT // 86400} days "
              "and only once. If you weren't expecting this, ignore this email.", None, [user.email], fail_silently=True)


def _email(user, subject, body):
    if user.email:
        send_mail(subject, body, None, [user.email], fail_silently=True)


# --------------------------------------------------------------------------- shared readings
OFF_HOURS = (22, 5)          # 10 pm to 5 am, local time
ACCOUNT_WORDS = ("account", "two-step", "password reset", "unlocked", "staff access")


def ago(moment):
    seconds = int((timezone.now() - moment).total_seconds())
    if seconds < 60:
        return "Just now"
    if seconds < 3600:
        minutes = seconds // 60
        return f"{minutes} min{'s' if minutes != 1 else ''} ago"
    if seconds < 86400:
        hours = seconds // 3600
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    days = (timezone.localdate() - timezone.localtime(moment).date()).days
    return "Yesterday" if days == 1 else f"{days} days ago"


def who(entry):
    return display_name(entry.user) if entry.user else "System"


def users_online(minutes=5):
    """People whose session saw activity in the last few minutes. Sessions are renewed on every request, so
    'expires in nearly the full 30 minutes' means 'used just now'."""
    from django.contrib.sessions.models import Session

    threshold = timezone.now() + timedelta(seconds=settings.SESSION_COOKIE_AGE - minutes * 60)
    ids = set()
    for session in Session.objects.filter(expire_date__gt=threshold):
        user_id = session.get_decoded().get("_auth_user_id")
        if user_id:
            ids.add(user_id)
    return len(ids)


def is_off_hours(moment):
    hour = timezone.localtime(moment).hour
    return hour >= OFF_HOURS[0] or hour < OFF_HOURS[1]


def security_alerts(days=7, limit=5):
    """Things an administrator should look at: repeated failed sign-ins, emergency access, exports, night-time access."""
    now = timezone.now()
    since = now - timedelta(days=days)
    per_source = limit or 50            # limit=0 means "give me all of them"
    alerts = []
    for attempt in AccessAttempt.objects.filter(attempt_time__gte=since, failures_since_start__gte=3):
        alerts.append({"title": "Repeated Authentication Failures", "detail": f"{attempt.failures_since_start} failed passwords for {attempt.username}",
                       "level": "critical" if attempt.failures_since_start >= settings.AXES_FAILURE_LIMIT else "warning", "when": attempt.attempt_time})
    entries = AuditEntry.objects.filter(created_at__gte=since).select_related("user", "patient")
    for e in entries.filter(text__contains=EMERGENCY_TAG)[:per_source]:
        alerts.append({"title": "Emergency Record Access", "detail": f"{who(e)} opened {e.patient.code if e.patient else 'a record'} in an emergency",
                       "level": "warning", "when": e.created_at})
    for e in entries.filter(text__startswith="exported")[:per_source]:
        alerts.append({"title": "Audit Log Exported", "detail": f"{who(e)} exported log entries to CSV", "level": "warning", "when": e.created_at})
    for e in entries.filter(kind=AuditEntry.Kind.AUTHORIZED, patient__isnull=False).exclude(text__contains=EMERGENCY_TAG)[:200]:
        if is_off_hours(e.created_at):
            alerts.append({"title": "Off-Hours Record Access", "detail": f"{who(e)} opened {e.patient.code} at {timezone.localtime(e.created_at):%I:%M %p}",
                           "level": "warning", "when": e.created_at})
    alerts.sort(key=lambda a: a["when"], reverse=True)
    for a in alerts:
        a["ago"] = ago(a["when"])
    return alerts[:limit] if limit else alerts


def integrity_summary():
    """('intact'|'problem'|'empty', entries checked). Cached briefly and re-run whenever the log grows."""
    from django.core.cache import cache

    latest = AuditEntry.objects.order_by("-id").values_list("id", flat=True).first()
    key = f"audit-integrity:{latest}"
    result = cache.get(key)
    if result is None:
        checked, problems = verify_chain()
        result = ("problem" if problems else "intact" if checked else "empty", checked)
        cache.set(key, result, 300)
    return result


def _dot(text):
    lowered = text.lower()
    if any(w in lowered for w in ("deactivated", "denied", "unlinked")):
        return "red"
    if any(w in lowered for w in ("approved", "created", "reactivated", "linked")):
        return "green"
    if any(w in lowered for w in ("updated", "role")):
        return "purple"
    return "orange"


def recent_account_activity(limit=4):
    query = Q()
    for word in ACCOUNT_WORDS:
        query |= Q(text__icontains=word)
    rows = []
    for e in AuditEntry.objects.filter(query).exclude(kind__in=[AuditEntry.Kind.SIGN_IN, AuditEntry.Kind.SIGN_IN_FAILED]).select_related("user")[:limit]:
        rows.append({"title": e.text[:1].upper() + e.text[1:], "by": who(e) if e.user else "Self-service portal", "ago": ago(e.created_at), "dot": _dot(e.text)})
    return rows


# --------------------------------------------------------------------------- dashboard
@admin_required
def manage_dashboard(request):
    users = list(User.objects.select_related("profile", "patient_record").prefetch_related("groups"))
    kinds = [kind_of(u) for u in users]
    active_kinds = [kind_of(u) for u in users if u.is_active]
    pending_staff = [u for u in users if kind_of(u) == "staff" and status_of(u)[0] == "pending"]
    integrity, checked = integrity_summary()
    alerts = security_alerts()
    total_active = len(active_kinds) or 1
    segments = []
    for key, label, colour in (("staff", "Clinic Staff", "blue"), ("student", "Students", "green"), ("admin", "System Admins", "purple")):
        count = active_kinds.count(key)
        segments.append({"key": key, "label": label, "colour": colour, "count": count, "pct": round(count * 100 / total_active, 1)})
    return render(request, "manage/dashboard.html", {
        "total": len(users), "kind_counts": {"staff": kinds.count("staff"), "student": kinds.count("student"), "admin": kinds.count("admin")},
        "online": users_online(), "pending_count": len(pending_staff), "integrity": integrity, "checked": checked,
        "activity": recent_account_activity(), "alerts": alerts, "flag_count": len(alerts), "segments": segments,
        "any_active": bool(active_kinds),
    })


# --------------------------------------------------------------------------- user list
@admin_required
def manage_users(request):
    q = request.GET.get("q", "").strip()
    role = request.GET.get("role", "")
    users = User.objects.select_related("profile", "patient_record").prefetch_related("groups")
    if q:
        users = users.filter(Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(username__icontains=q) | Q(email__icontains=q))
    if role == "admin":
        users = users.filter(Q(is_superuser=True) | Q(groups__name=ADMINISTRATOR))
    elif role in ("staff", "student"):
        users = users.filter(groups__name=GROUP_FOR_KIND[role]).exclude(is_superuser=True)
    else:
        role = ""
    page = Paginator(users.distinct().order_by("first_name", "last_name", "username"), PAGE_SIZE).get_page(request.GET.get("page"))

    pending = [u for u in User.objects.select_related("profile").prefetch_related("groups")
               .filter(is_active=False, groups__name=CLINIC_STAFF, profile__denied_at__isnull=True, profile__reviewed_at__isnull=True,
                       last_login__isnull=True).distinct().order_by("date_joined")]
    query = "&".join(f"{k}={v}" for k, v in (("q", q), ("role", role)) if v)
    return render(request, "manage/users.html", {
        "rows": _rows(page.object_list), "page": page, "q": q, "role": role, "pending": _rows(pending), "qs": query,
        "total": User.objects.count(), "me_id": request.user.pk,
    })


# --------------------------------------------------------------------------- one user
@admin_required
@require_POST
def manage_user_action(request, pk):
    target = get_object_or_404(User.objects.select_related("profile").prefetch_related("groups"), pk=pk)
    action = request.POST.get("action", "")
    name, kind, profile = display_name(target), kind_of(target), _profile(target)
    now = timezone.now()
    is_me = target.pk == request.user.pk

    def stamp():
        if profile is not None:
            profile.reviewed_by, profile.reviewed_at = request.user, now

    if is_me and action in ("deactivate", "deny", "reset_2fa"):
        messages.error(request, "You can't do that to your own account. Ask another administrator.")
    elif action == "approve" and status_of(target)[0] == "pending" and kind == "staff" and profile is not None:
        stamp()
        profile.denied_at = None
        profile.save()
        target.is_active = True
        target.save(update_fields=["is_active"])
        _email(target, "Your CareBoard account is approved",
               "Hello,\n\nYour CareBoard account has been approved. You can now sign in with your email and password."
               + ("\nYou will be asked to set up two-step sign-in with an authenticator app the first time.\n" if settings.REQUIRE_2FA else "\n"))
        _audit(request, f"approved the staff account of {name}")
        messages.success(request, f"{name} was approved and can now sign in.")
    elif action == "deny" and status_of(target)[0] == "pending" and kind == "staff" and profile is not None:
        stamp()
        profile.denied_at = now
        profile.save()
        _email(target, "Your CareBoard access request", "Hello,\n\nYour request for CareBoard staff access was not approved. "
                                                       "If you think this is a mistake, please contact your system administrator.\n")
        _audit(request, f"denied the staff access request of {name}")
        messages.success(request, f"{name}'s request was denied.")
    elif action == "deactivate" and target.is_active:
        if kind == "admin" and _active_admins().count() <= 1:
            messages.error(request, "That is the only active administrator. Add another one first.")
        else:
            target.is_active = False
            target.save(update_fields=["is_active"])
            if profile is not None and profile.reviewed_at is None:
                stamp()
                profile.save()
            _audit(request, f"deactivated the account of {name}")
            messages.success(request, f"{name} was deactivated. They are signed out and can't sign in until reactivated.")
    elif action == "activate" and not target.is_active:
        if profile is not None:
            stamp()
            profile.denied_at = None
            profile.save()
        target.is_active = True
        target.save(update_fields=["is_active"])
        _audit(request, f"reactivated the account of {name}")
        messages.success(request, f"{name} was reactivated.")
    elif action == "reset_2fa":
        deleted, _ = TwoFactor.objects.filter(user=target).delete()
        if deleted:
            _audit(request, f"reset the two-step sign-in of {name}")
            messages.success(request, f"Two-step sign-in was reset. {name} will set it up again at their next sign-in.")
        else:
            messages.info(request, f"{name} has no two-step sign-in set up.")
    elif action == "temp_password" and settings.DEMO_MODE and not is_me:
        temporary = _temporary_password()
        target.set_password(temporary)
        target.save(update_fields=["password"])
        _audit(request, f"set a temporary password for {name}")
        messages.success(request, f"Temporary password for {target.email}: {temporary}   (shown only once; they can change it under Change password after signing in)")
    elif action == "send_reset" and target.is_active and target.email:
        send_password_link(request, target, new_account=False)
        _audit(request, f"sent a password reset link to {name}")
        messages.success(request, f"A password reset link was emailed to {target.email}.")
    elif action == "unlock":
        cleared = reset_lockout(username=target.username)
        _audit(request, f"unlocked the account of {name}")
        messages.success(request, f"{name}'s sign-in lock was cleared." if cleared else f"{name} wasn't locked.")
    else:
        messages.error(request, "That action isn't available for this account right now.")
    return _back(request)


class UserForm(forms.Form):
    """Shared by 'add user' and 'edit user'."""

    full_name = forms.CharField(label="Full Name", max_length=150)
    email = forms.EmailField(label="Email Address", max_length=150)
    role = forms.ChoiceField(label="Role", choices=[("administrator", "Administrator"), ("physician", "Physician"), ("nurse", "Nurse"),
                                                      ("receptionist", "Receptionist"), ("student", "Student")])
    department = forms.CharField(label="Department", max_length=100, required=False)
    employee_id = forms.CharField(label="Employee / License ID", max_length=40, required=False)
    student_id = forms.CharField(label="Student ID", max_length=40, required=False)
    date_of_birth = forms.DateField(label="Date of Birth", required=False, input_formats=["%m/%d/%Y"],
                                    widget=forms.TextInput(attrs={"placeholder": "MM/DD/YYYY"}))
    shift_start = forms.TimeField(label="Shift starts", required=False, widget=forms.TimeInput(attrs={"type": "time"}))
    shift_end = forms.TimeField(label="Shift ends", required=False, widget=forms.TimeInput(attrs={"type": "time"}))

    STAFF_ONLY = ("department", "employee_id", "shift_start", "shift_end")
    STUDENT_ONLY = ("student_id", "date_of_birth")

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        if user is None:
            return
        kind = kind_of(user)
        if kind == "staff":
            self.fields["role"].choices = [(r.value, r.label) for r in STAFF_ROLES]
            drop = self.STUDENT_ONLY
        else:
            # Administrators and students keep their role: changing it would change what they are allowed to see.
            self.fields["role"].disabled = True
            self.initial.setdefault("role", "student" if kind == "student" else "administrator")
            drop = self.STAFF_ONLY + (self.STUDENT_ONLY if kind != "student" else ())
        for name in drop:
            self.fields.pop(name, None)

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        clash = User.objects.filter(Q(username__iexact=email) | Q(email__iexact=email))
        if self.user is not None:
            clash = clash.exclude(pk=self.user.pk)
        if clash.exists():
            raise forms.ValidationError("Another account already uses this email.")
        return email

    def _unique(self, name, value):
        clash = Profile.objects.filter(**{f"{name}__iexact": value})
        if self.user is not None:
            clash = clash.exclude(user=self.user)
        if clash.exists():
            raise forms.ValidationError("This ID is already registered.")
        return value

    def clean_employee_id(self):
        value = self.cleaned_data["employee_id"].strip()
        return self._unique("employee_id", value) if value else ""

    def clean_student_id(self):
        value = self.cleaned_data["student_id"].strip()
        return self._unique("student_id", value) if value else ""

    def clean(self):
        cleaned = super().clean()
        role = cleaned.get("role") or (self.initial.get("role") if self.user else None)
        if role == "student" and self.user is None:
            for name in ("student_id", "date_of_birth"):
                if not cleaned.get(name):
                    self.add_error(name, "Required for students, so the clinic can link their record.")
        if role in ("physician", "nurse", "receptionist") and "department" in self.fields and not cleaned.get("department"):
            self.add_error("department", "Please add a department.")
        return cleaned


def _apply(user, profile, cd):
    first, _, last = cd["full_name"].strip().partition(" ")
    user.first_name, user.last_name = first[:150], last[:150]
    user.email = user.username = cd["email"]
    for field in ("department", "shift_start", "shift_end", "date_of_birth"):
        if field in cd:
            setattr(profile, field, cd[field] or (None if field != "department" else ""))
    if "employee_id" in cd:
        profile.employee_id = cd["employee_id"] or None
    if "student_id" in cd:
        profile.student_id = cd["student_id"] or None


@admin_required
def manage_user_new(request):
    form = UserForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        cd = dict(form.cleaned_data)
        if cd["role"] not in ("physician", "nurse", "receptionist"):    # staff-only details don't apply to administrators or students
            cd.update(department="", employee_id="", shift_start=None, shift_end=None)
        if cd["role"] != "student":
            cd.update(student_id="", date_of_birth=None)
        with transaction.atomic():
            user = User(is_active=True)
            user.set_unusable_password()
            profile = Profile(role=cd["role"], reviewed_by=request.user, reviewed_at=timezone.now())
            _apply(user, profile, cd)
            user.save()
            profile.user = user
            if cd["role"] == "administrator":
                group = ADMINISTRATOR
            elif cd["role"] == "student":
                group = STUDENT
            else:
                group = CLINIC_STAFF
            user.groups.add(Group.objects.get_or_create(name=group)[0])
            profile.save()
            _audit(request, f"created the {profile.get_role_display().lower()} account of {display_name(user)}")
        if settings.DEMO_MODE:  # no email in demo mode: hand the password over in person
            temporary = _temporary_password()
            user.set_password(temporary)
            user.save(update_fields=["password"])
            messages.success(request, f"Account created. Sign-in: {user.email} / temporary password: {temporary}   (shown only once)")
        else:
            send_password_link(request, user, new_account=True)
            messages.success(request, f"Account created. A link to choose a password was emailed to {user.email}.")
        return redirect("manage_users")
    return render(request, "manage/user_form.html", {"form": form, "target": None})


@admin_required
def manage_user_edit(request, pk):
    target = get_object_or_404(User.objects.select_related("profile", "patient_record").prefetch_related("groups"), pk=pk)
    profile = _profile(target)
    initial = {"full_name": target.get_full_name(), "email": target.email}
    if profile is not None:
        initial.update(role=profile.role, department=profile.department, employee_id=profile.employee_id or "",
                       student_id=profile.student_id or "", shift_start=profile.shift_start, shift_end=profile.shift_end,
                       date_of_birth=profile.date_of_birth.strftime("%m/%d/%Y") if profile.date_of_birth else "")
    form = UserForm(request.POST or None, initial=initial, user=target)
    if request.method == "POST" and form.is_valid():
        cd = form.cleaned_data
        before = (target.get_full_name(), target.email, profile.role if profile else "", profile.department if profile else "")
        with transaction.atomic():
            if profile is None:
                profile = Profile(user=target, role="administrator" if kind_of(target) == "admin" else "student")
            if "role" in cd and not form.fields["role"].disabled:
                profile.role = cd["role"]
            _apply(target, profile, cd)
            target.save()
            profile.save()
            changed = [label for label, old, new in (("name", before[0], target.get_full_name()), ("email", before[1], target.email),
                                                     ("role", before[2], profile.role), ("department", before[3], profile.department)) if old != new]
            _audit(request, f"updated the account of {display_name(target)}" + (f" ({', '.join(changed)})" if changed else ""))
        messages.success(request, "Account updated.")
        return redirect("manage_users")
    attempts = AccessAttempt.objects.filter(username=target.username, failures_since_start__gte=settings.AXES_FAILURE_LIMIT).exists()
    return render(request, "manage/user_form.html", {
        "form": form, "target": target, "kind": KIND_LABEL[kind_of(target)], "status": status_of(target),
        "last_login": last_login_label(target), "has_2fa": getattr(target, "two_factor", None) is not None and target.two_factor.is_confirmed,
        "locked": attempts, "is_me": target.pk == request.user.pk, "linked": getattr(target, "patient_record", None),
    })


# --------------------------------------------------------------------------- audit trail
RANGE_CHOICES = [("today", "Today"), ("week", "Last 7 days"), ("month", "Last 30 days"), ("all", "All time")]
ROLE_CHOICES = [("", "All Users"), ("admin", "Administrators"), ("staff", "Clinic Staff"), ("student", "Students")]


def _since(range_key):
    now = timezone.localtime()
    if range_key == "today":
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    if range_key == "week":
        return now - timedelta(days=7)
    if range_key == "month":
        return now - timedelta(days=30)
    return None


def _filtered_entries(params):
    entries = AuditEntry.objects.select_related("user", "user__profile", "patient")
    q, who_text, kind, patient, role = (params.get(k, "").strip() for k in ("q", "who", "kind", "patient", "role"))
    if q:
        entries = entries.filter(text__icontains=q)
    if who_text:
        entries = entries.filter(Q(user__email__icontains=who_text) | Q(user__first_name__icontains=who_text) | Q(user__last_name__icontains=who_text))
    if kind in dict(AuditEntry.Kind.choices):
        entries = entries.filter(kind=kind)
    if role == "admin":
        entries = entries.filter(Q(user__is_superuser=True) | Q(user__groups__name=ADMINISTRATOR)).distinct()
    elif role in ("staff", "student"):
        entries = entries.filter(user__groups__name=GROUP_FOR_KIND[role]).exclude(user__is_superuser=True).distinct()
    if patient:
        entries = entries.filter(Q(patient__code__icontains=patient) | Q(patient__first_name__icontains=patient) | Q(patient__last_name__icontains=patient))
    explicit_dates = False
    for key, lookup in (("since", "created_at__date__gte"), ("until", "created_at__date__lte")):
        value = params.get(key, "").strip()
        if value:
            try:
                entries = entries.filter(**{lookup: timezone.datetime.strptime(value, "%Y-%m-%d").date()})
                explicit_dates = True
            except ValueError:
                pass
    range_key = params.get("range", "today")
    if range_key not in dict(RANGE_CHOICES):
        range_key = "today"
    if not explicit_dates and (start := _since(range_key)):
        entries = entries.filter(created_at__gte=start)
    if params.get("emergency") == "1":
        entries = entries.filter(text__contains=EMERGENCY_TAG)
    return entries, range_key


def action_of(entry):
    """(label, style) for the coloured 'Action' badge."""
    kind, has_patient = entry.kind, entry.patient_id is not None
    if kind == AuditEntry.Kind.SIGN_IN:
        return "Login Success", "login"
    if kind == AuditEntry.Kind.SIGN_IN_FAILED:
        return "Login Failed", "fail"
    if kind == AuditEntry.Kind.AUTHORIZED:
        return ("Viewed Record" if has_patient else "Searched Directory"), "view"
    if kind == AuditEntry.Kind.MODIFIED:
        return ("Edited Record" if has_patient else "Account Change"), "edit"
    if kind == AuditEntry.Kind.CREATED:
        return ("Created Record" if has_patient else "Account Created"), "create"
    return "System", "system"


def _log_rows(entries):
    rows = []
    for e in entries:
        label, style = action_of(e)
        local = timezone.localtime(e.created_at)
        rows.append({"e": e, "date": local.strftime("%b %d, %Y"), "time": local.strftime("%I:%M:%S %p"), "who": who(e), "label": label, "style": style,
                     "record": f"{e.patient.full_name} ({e.patient.code})" if e.patient else "System Audit Panel", "ip": e.ip_address or "—"})
    return rows


@admin_required
def manage_logs(request):
    params = request.GET
    entries, range_key = _filtered_entries(params)
    if params.get("export") == "csv":
        rows = entries[:50000]
        log(request.user, AuditEntry.Kind.AUTHORIZED, f"exported {min(entries.count(), 50000)} audit log entries to CSV")
        writer = csv.writer(_Echo())

        def stream():
            yield writer.writerow(["time", "user_email", "user_name", "type", "patient_code", "ip_address", "activity"])
            for e in rows.iterator():
                yield writer.writerow([_safe_cell(timezone.localtime(e.created_at).strftime("%Y-%m-%d %H:%M:%S")),
                                       _safe_cell(e.user.email if e.user else ""), _safe_cell(e.user.get_full_name() if e.user else "System"),
                                       e.kind, _safe_cell(e.patient.code if e.patient else ""), _safe_cell(e.ip_address or ""), _safe_cell(e.text)])

        response = StreamingHttpResponse(stream(), content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="audit-log.csv"'
        response["Cache-Control"] = "private, no-store"
        return response

    page = Paginator(entries, LOG_PAGE_SIZE).get_page(params.get("page"))
    filters = {k: params.get(k, "").strip() for k in ("q", "who", "kind", "patient", "since", "until", "emergency", "role", "range") if params.get(k, "").strip()}
    context = {
        "page": page, "rows": _log_rows(page.object_list), "f": filters, "range": range_key, "qs": urlencode(filters),
        "kinds": AuditEntry.Kind.choices, "ranges": RANGE_CHOICES, "roles": ROLE_CHOICES, "total": AuditEntry.objects.count(),
        "emergency_tag": EMERGENCY_TAG, "stats": {
            "total": entries.count(), "people": entries.exclude(user=None).values("user").distinct().count(),
            "records": entries.filter(kind=AuditEntry.Kind.AUTHORIZED, patient__isnull=False).count(), "alerts": len(security_alerts(limit=0)),
        },
    }
    if params.get("fragment"):
        return render(request, "manage/_logs_live.html", context)
    return render(request, "manage/logs.html", context)


class _Echo:
    def write(self, value):
        return value


def _safe_cell(value):
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text  # stops spreadsheet formula injection


@admin_required
@require_POST
def manage_logs_verify(request):
    checked, problems = verify_chain()
    if problems:
        for line in problems[:5]:
            messages.error(request, line)
        messages.error(request, f"Audit log check FAILED: {len(problems)} problem(s) found in {checked} entries.")
    else:
        messages.success(request, f"Audit log intact: {checked} chained entries checked, no edits or gaps found.")
    return redirect("manage_logs")
