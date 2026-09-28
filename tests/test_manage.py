import csv
import io
from datetime import timedelta

import pytest
from axes.models import AccessAttempt
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Profile, TwoFactor
from apps.audit.models import AuditEntry
from apps.audit.services import log
from apps.patients.models import Patient

User = get_user_model()
PW = "CareBoard-Demo1!"
ADMIN_URLS = ["manage_dashboard", "manage_users", "manage_user_new", "manage_logs"]


def uid(email):
    return User.objects.get(username=email).pk


def act(admin, email, action, **extra):
    return admin.post(reverse("manage_user_action", args=[uid(email)]), {"action": action, **extra})


# ---- who may enter ---------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("role", ["receptionist", "nurse", "physician", "student"])
def test_only_administrators_can_use_the_admin_area(as_role, role):
    client = as_role(role)
    for name in ADMIN_URLS:
        assert client.get(reverse(name)).status_code == 403, name
    assert client.post(reverse("manage_user_action", args=[uid("nurse.reyes@careboard.demo")]), {"action": "deactivate"}).status_code == 403
    assert client.post(reverse("manage_logs_verify")).status_code == 403


def test_anonymous_visitors_are_sent_to_sign_in(client, seeded):
    for name in ADMIN_URLS:
        r = client.get(reverse(name))
        assert r.status_code == 302 and "/login/" in r["Location"]


def test_administrators_do_not_get_clinical_access(as_role):
    admin = as_role("admin")
    p = Patient.objects.get(code="PAT-984-219")
    for url in (reverse("patient_list"), reverse("patient_detail", args=[p.pk]), reverse("triage_queue"), reverse("portal_profile")):
        assert admin.get(url).status_code == 403, url


def test_actions_need_post(as_role):
    r = as_role("admin").get(reverse("manage_user_action", args=[uid("nurse.reyes@careboard.demo")]))
    assert r.status_code == 302 and r["Location"] == reverse("dashboard")          # nothing done; sent home
    assert User.objects.get(username="nurse.reyes@careboard.demo").is_active


# ---- the user list --------------------------------------------------------------------------------------------------------
def test_user_list_shows_pending_cards_roles_statuses_and_last_login(as_role):
    html = as_role("admin").get(reverse("manage_users")).content.decode()
    assert "Pending Clinical Staff Activations" in html and "Aris Thorne" in html and "Sarah Jenkins" in html
    assert "Deny Access" in html and "Approve Staff Member" in html
    assert "Clinic Staff" in html and "Administrator" in html and "Student" in html
    assert "Today," in html and "Yesterday," in html and "Never" in html
    assert 'statusbadge--pending">Pending' in html                      # the unlinked student, and the two staff requests


def test_search_role_filter_and_paging(as_role):
    admin = as_role("admin")
    r = admin.get(reverse("manage_users"), {"q": "reyes"})
    assert b"nurse.reyes@careboard.demo" in r.content and b"dr.henderson@careboard.demo" not in r.content
    students = admin.get(reverse("manage_users"), {"role": "student"}).content
    assert b"student@careboard.demo" in students and b"nurse.reyes" not in students
    assert b"admin@careboard.demo" in admin.get(reverse("manage_users"), {"role": "admin"}).content
    for i in range(12):
        User.objects.create(username=f"bulk{i}@x.org", email=f"bulk{i}@x.org", first_name="Bulk", last_name=str(i))
    page = admin.get(reverse("manage_users")).context["page"]
    assert page.paginator.num_pages >= 2 and len(page.object_list) == 10
    assert admin.get(reverse("manage_users"), {"page": "junk"}).status_code == 200


# ---- approving and denying staff ------------------------------------------------------------------------------------------------
def test_approving_a_staff_request(as_role, seeded):
    admin = as_role("admin")
    email = "aris.thorne@careboard.demo"
    assert not User.objects.get(username=email).is_active
    assert Client().login(username=email, password=PW) is False
    act(admin, email, "approve")
    user = User.objects.get(username=email)
    assert user.is_active and user.profile.reviewed_by.username == "admin@careboard.demo" and user.profile.reviewed_at
    assert any(m.to == [email] and "approved" in m.subject for m in mail.outbox)
    assert AuditEntry.objects.filter(user__username="admin@careboard.demo", text__startswith="approved the staff account of Dr. Aris Thorne").exists()
    assert Client().login(username=email, password=PW)
    act(admin, email, "approve")                                         # already approved: nothing more happens
    assert len([m for m in mail.outbox if "approved" in m.subject]) == 1


def test_denying_a_staff_request_can_be_reversed(as_role):
    admin = as_role("admin")
    email = "sarah.jenkins@careboard.demo"
    act(admin, email, "deny")
    user = User.objects.get(username=email)
    assert not user.is_active and user.profile.denied_at
    html = admin.get(reverse("manage_users")).content.decode()
    assert "Sarah Jenkins" in html and 'statusbadge--denied">Denied' in html
    assert "Deny Access" not in html or "Sarah Jenkins" not in html.split("Pending Clinical Staff Activations")[-1].split("Search Active Users")[0]
    act(admin, email, "activate")
    user.refresh_from_db(); user.profile.refresh_from_db()
    assert user.is_active and user.profile.denied_at is None


def test_students_cannot_be_approved_as_staff(as_role):
    admin = as_role("admin")
    act(admin, "student@careboard.demo", "approve")
    act(admin, "s.jenkins@careboard.demo", "deny")
    assert User.objects.get(username="s.jenkins@careboard.demo").is_active
    assert Profile.objects.get(user__username="s.jenkins@careboard.demo").denied_at is None


# ---- deactivating -------------------------------------------------------------------------------------------------------------------
def test_deactivating_signs_the_person_out_at_once_and_blocks_sign_in(as_role):
    admin, nurse = as_role("admin"), as_role("nurse")
    assert nurse.get(reverse("dashboard")).status_code == 200
    act(admin, "nurse.reyes@careboard.demo", "deactivate")
    r = nurse.get(reverse("dashboard"))
    assert r.status_code == 302 and "/login/" in r["Location"]           # the existing session no longer works
    assert Client().login(username="nurse.reyes@careboard.demo", password=PW) is False
    assert AuditEntry.objects.filter(user__username="admin@careboard.demo", text="deactivated the account of Maria Reyes").exists()
    act(admin, "nurse.reyes@careboard.demo", "activate")
    assert Client().login(username="nurse.reyes@careboard.demo", password=PW)


def test_a_deactivated_staff_member_does_not_reappear_as_pending(as_role):
    admin = as_role("admin")
    act(admin, "sarah.cole@careboard.demo", "deactivate")
    html = admin.get(reverse("manage_users")).content.decode()
    pending_block = html.split("Pending Clinical Staff Activations")[1].split("Search Active Users")[0]
    assert "Sarah Cole" not in pending_block and 'statusbadge--inactive">Inactive' in html


def test_you_cannot_deactivate_or_reset_yourself(as_role):
    admin = as_role("admin")
    from html import unescape

    page = admin.post(reverse("manage_user_action", args=[uid("admin@careboard.demo")]), {"action": "deactivate"}, follow=True)
    assert "You can't do that to your own account" in unescape(page.content.decode())
    admin.post(reverse("manage_user_action", args=[uid("admin@careboard.demo")]), {"action": "reset_2fa"})
    assert User.objects.get(username="admin@careboard.demo").is_active


def test_redirect_targets_are_checked(as_role):
    r = act(as_role("admin"), "sarah.cole@careboard.demo", "activate", next="https://evil.example/")
    assert r.status_code == 302 and r["Location"] == reverse("manage_users")


# ---- adding people -------------------------------------------------------------------------------------------------------------------
NEW_STAFF = {"full_name": "Nora Vega", "email": "Nora.Vega@Clinic.org", "role": "nurse", "department": "Triage", "employee_id": "NUR-9",
             "student_id": "", "date_of_birth": "", "shift_start": "07:00", "shift_end": "15:00"}


def test_admin_creates_staff_who_choose_their_own_password(as_role):
    admin = as_role("admin")
    r = admin.post(reverse("manage_user_new"), NEW_STAFF)
    assert r.status_code == 302
    user = User.objects.get(username="nora.vega@clinic.org")
    assert user.is_active and not user.has_usable_password() and user.groups.filter(name="ClinicStaff").exists()
    assert (user.profile.role, user.profile.department, user.profile.reviewed_by.username, str(user.profile.shift_start)) == ("nurse", "Triage", "admin@careboard.demo", "07:00:00")
    body = next(m for m in mail.outbox if m.to == ["nora.vega@clinic.org"]).body
    link = next(w for w in body.split() if "/password-reset/" in w)
    client = Client()
    page = client.get(link, follow=True)
    assert page.status_code == 200
    r = client.post(page.request["PATH_INFO"], {"new_password1": "Her-Own-Passw0rd!", "new_password2": "Her-Own-Passw0rd!"})
    assert r.status_code == 302 and Client().login(username="nora.vega@clinic.org", password="Her-Own-Passw0rd!")
    assert AuditEntry.objects.filter(text__startswith="created the nurse account of Nora Vega").exists()


def test_creating_an_administrator_and_a_student(as_role):
    admin = as_role("admin")
    admin.post(reverse("manage_user_new"), {**NEW_STAFF, "email": "boss@clinic.org", "full_name": "Big Boss", "role": "administrator", "department": ""})
    boss = User.objects.get(username="boss@clinic.org")
    assert boss.groups.filter(name="Administrator").exists() and not boss.is_superuser and not boss.is_staff
    admin.post(reverse("manage_user_new"), {**NEW_STAFF, "email": "kid@uni.edu", "full_name": "Kid Student", "role": "student", "department": "",
                                            "student_id": "STU-42", "date_of_birth": "02/03/2005"})
    kid = User.objects.get(username="kid@uni.edu")
    assert kid.groups.filter(name="Student").exists() and kid.profile.student_id == "STU-42"


def test_new_user_form_rules(as_role):
    admin = as_role("admin")
    assert "department" in admin.post(reverse("manage_user_new"), {**NEW_STAFF, "department": ""}).context["form"].errors      # staff need a department
    r = admin.post(reverse("manage_user_new"), {**NEW_STAFF, "role": "student", "department": ""})
    assert {"student_id", "date_of_birth"} <= set(r.context["form"].errors)                                                  # students need both
    assert "email" in admin.post(reverse("manage_user_new"), {**NEW_STAFF, "email": "NURSE.REYES@careboard.demo"}).context["form"].errors
    assert "employee_id" in admin.post(reverse("manage_user_new"), {**NEW_STAFF, "employee_id": "nur-10002"}).context["form"].errors
    assert not User.objects.filter(username="nora.vega@clinic.org").exists()


# ---- editing -----------------------------------------------------------------------------------------------------------------------------
def edit_data(**kw):
    return {"full_name": "Maria Reyes", "email": "nurse.reyes@careboard.demo", "role": "nurse", "department": "Triage",
            "employee_id": "NUR-10002", "shift_start": "08:00", "shift_end": "16:00", **kw}


def test_editing_a_staff_member(as_role):
    admin = as_role("admin")
    pk = uid("nurse.reyes@careboard.demo")
    r = admin.post(reverse("manage_user_edit", args=[pk]), edit_data(role="physician", department="Emergency", full_name="Maria R. Reyes", email="M.Reyes@careboard.demo"))
    assert r.status_code == 302
    user = User.objects.get(pk=pk)
    assert user.username == "m.reyes@careboard.demo" and user.last_name == "R. Reyes" and user.profile.role == "physician" and user.profile.department == "Emergency"
    assert AuditEntry.objects.filter(text__startswith="updated the account of").filter(text__contains="role").exists()
    assert "role" in admin.post(reverse("manage_user_edit", args=[pk]), edit_data(role="administrator")).context["form"].errors   # not an allowed choice


def test_administrators_and_students_keep_their_role(as_role):
    admin = as_role("admin")
    pk = uid("student@careboard.demo")
    admin.post(reverse("manage_user_edit", args=[pk]), {"full_name": "Elizabeth Hughes", "email": "student@careboard.demo", "role": "administrator",
                                                        "student_id": "STU-984-219", "date_of_birth": "10/14/1988"})
    user = User.objects.get(pk=pk)
    assert user.profile.role == "student" and not user.groups.filter(name="Administrator").exists()
    page = admin.get(reverse("manage_user_edit", args=[uid("admin@careboard.demo")]))
    assert page.status_code == 200 and "department" not in page.context["form"].fields


def test_edit_page_shows_status_and_tools(as_role):
    admin = as_role("admin")
    nurse = User.objects.get(username="nurse.reyes@careboard.demo")
    html = admin.get(reverse("manage_user_edit", args=[nurse.pk])).content.decode()
    assert "Yesterday," in html and "Two-step sign-in" in html and "Email a password reset link" in html and "Deactivate account" in html


def test_reset_two_step_and_unlock_and_password_link(as_role):
    admin = as_role("admin")
    nurse = User.objects.get(username="nurse.reyes@careboard.demo")
    TwoFactor.objects.create(user=nurse, secret="ABC", confirmed_at=timezone.now())
    act(admin, nurse.username, "reset_2fa")
    assert not TwoFactor.objects.filter(user=nurse).exists()
    AccessAttempt.objects.create(username=nurse.username, ip_address="1.2.3.4", user_agent="t", http_accept="", path_info="/login/",
                                 failures_since_start=5)
    assert b"This account is locked" in admin.get(reverse("manage_user_edit", args=[nurse.pk])).content
    act(admin, nurse.username, "unlock")
    assert not AccessAttempt.objects.filter(username=nurse.username).exists()
    act(admin, nurse.username, "send_reset")
    assert any("/password-reset/" in m.body and m.to == [nurse.email] for m in mail.outbox)


# ---- the audit log viewer -----------------------------------------------------------------------------------------------------------------
def test_logs_can_be_filtered(as_role):
    admin = as_role("admin")
    p = Patient.objects.get(code="PAT-984-219")
    log(None, "AUTHORIZED", "opened the record of X — reason: Emergency: the patient needs urgent care [EMERGENCY ACCESS]", p)
    total = admin.get(reverse("manage_logs")).context["page"].paginator.count
    assert total >= 5
    assert admin.get(reverse("manage_logs"), {"emergency": "1"}).context["page"].paginator.count == 1
    assert admin.get(reverse("manage_logs"), {"who": "reyes"}).context["page"].paginator.count >= 1
    assert all(e.kind == "CREATED" for e in admin.get(reverse("manage_logs"), {"kind": "CREATED"}).context["page"])
    assert admin.get(reverse("manage_logs"), {"patient": "PAT-984"}).context["page"].paginator.count >= 1
    tomorrow = (timezone.localdate() + timedelta(days=1)).isoformat()
    assert admin.get(reverse("manage_logs"), {"since": tomorrow}).context["page"].paginator.count == 0
    assert admin.get(reverse("manage_logs"), {"since": "garbage", "kind": "nope"}).status_code == 200


def test_logs_are_paged(as_role):
    for i in range(60):
        log(None, "SYSTEM", f"entry {i}")
    page = as_role("admin").get(reverse("manage_logs")).context["page"]
    assert page.paginator.num_pages >= 3 and len(page.object_list) == 25


def test_csv_export_is_safe_and_is_itself_logged(as_role):
    admin = as_role("admin")
    log(None, "SYSTEM", "=HYPERLINK(\"http://evil\",\"click\")")
    r = admin.get(reverse("manage_logs"), {"export": "csv", "q": "HYPERLINK"})
    assert r["Content-Type"].startswith("text/csv") and "attachment" in r["Content-Disposition"] and "no-store" in r["Cache-Control"]
    rows = list(csv.reader(io.StringIO(b"".join(r.streaming_content).decode())))
    assert rows[0] == ["time", "user_email", "user_name", "type", "patient_code", "ip_address", "activity"]
    assert rows[1][6].startswith("'=HYPERLINK")                          # a spreadsheet can't run it as a formula
    assert AuditEntry.objects.filter(user__username="admin@careboard.demo", text__startswith="exported").exists()


def test_integrity_check_passes_then_catches_tampering(as_role):
    admin = as_role("admin")
    ok = admin.post(reverse("manage_logs_verify"), follow=True).content.decode()
    assert "Audit log intact" in ok
    AuditEntry.objects.filter(pk=AuditEntry.objects.order_by("id")[1].pk).update(text="rewritten history")
    bad = admin.post(reverse("manage_logs_verify"), follow=True).content.decode()
    assert "FAILED" in bad and "Audit log intact" not in bad


# ---- the overview -----------------------------------------------------------------------------------------------------------------------------
def test_overview_numbers_are_real(as_role):
    admin = as_role("admin")
    ctx = admin.get(reverse("manage_dashboard")).context
    assert ctx["total"] == User.objects.count() and ctx["pending_count"] == 2
    assert ctx["kind_counts"] == {"staff": 5, "student": 2, "admin": 1}
    assert ctx["integrity"] == "intact" and ctx["checked"] >= 5
    assert ctx["online"] >= 1                                           # the admin just made a request


def test_overview_shows_the_designed_sections(as_role):
    html = as_role("admin").get(reverse("manage_dashboard")).content.decode()
    for text in ("System Overview Dashboard", "Total Accounts", "Active Sessions", "Pending Approvals", "Audit Log Integrity", "Review queue now",
                 "Recent Account Activity", "Security &amp; Access Alerts", "User Distribution by Role", "Clinic Staff", "Students", "System Admins"):
        assert text in html, text
    for false_claim in ("99.8%", "HIPAA", "Live traffic healthy", "nodes operational"):
        assert false_claim not in html


def test_role_distribution_adds_up(as_role):
    segments = as_role("admin").get(reverse("manage_dashboard")).context["segments"]
    assert sum(s["count"] for s in segments) == User.objects.filter(is_active=True).count()
    assert 99.0 <= sum(s["pct"] for s in segments) <= 101.0


def test_recent_account_activity_lists_admin_actions_and_signups(as_role, client):
    admin = as_role("admin")
    act(admin, "aris.thorne@careboard.demo", "approve")
    html = admin.get(reverse("manage_dashboard")).content.decode()
    assert "Approved the staff account of Dr. Aris Thorne" in html and "By " in html
    assert "Self-service portal" in html                                  # the seeded student sign-up
    assert "signed in" not in html.split("Recent Account Activity")[1].split("Security &amp; Access Alerts")[0]


def test_only_account_events_appear_in_recent_account_activity(as_role):
    from apps.accounts.manage_views import recent_account_activity

    log(None, "AUTHORIZED", "opened the record of Someone")
    assert all("record of Someone" not in r["title"] for r in recent_account_activity(limit=20))


def test_active_sessions_counts_people_active_in_the_last_minutes(as_role):
    from django.contrib.sessions.models import Session

    from apps.accounts.manage_views import users_online

    as_role("admin"), as_role("nurse")
    assert users_online() == 2
    stale = Session.objects.first()
    stale.expire_date = timezone.now() + timedelta(minutes=10)           # used ~20 minutes ago
    stale.save()
    assert users_online() == 1
    assert users_online(minutes=30) == 2


def test_integrity_summary_notices_tampering_once_the_log_moves_on(seeded):
    from apps.accounts.manage_views import integrity_summary

    assert integrity_summary()[0] == "intact"
    AuditEntry.objects.filter(pk=AuditEntry.objects.order_by("id")[1].pk).update(text="rewritten")
    log(None, "SYSTEM", "another entry")                                   # a new entry changes the cache key
    assert integrity_summary()[0] == "problem"


# ---- security alerts ----------------------------------------------------------------------------------------------------------------------
def test_alerts_flag_repeated_failures_by_severity(seeded):
    from apps.accounts.manage_views import security_alerts

    for name, n in (("a@x.org", 3), ("b@x.org", 5), ("c@x.org", 2)):
        AccessAttempt.objects.create(username=name, ip_address="1.1.1.1", user_agent="t", http_accept="", path_info="/login/", failures_since_start=n)
    alerts = {a["detail"].split()[-1]: a["level"] for a in security_alerts(limit=0) if a["title"] == "Repeated Authentication Failures"}
    assert alerts == {"a@x.org": "warning", "b@x.org": "critical"}        # 2 failures is normal fumbling: no flag


def test_alerts_flag_emergency_access_and_exports(as_role):
    from apps.accounts import manage_views as mv

    admin = as_role("admin")
    p = Patient.objects.get(code="PAT-984-219")
    log(User.objects.get(username="dr.henderson@careboard.demo"), "AUTHORIZED", f"opened the record of X {mv.EMERGENCY_TAG}", p)
    b"".join(admin.get(reverse("manage_logs"), {"export": "csv"}).streaming_content)          # an export, which is itself flagged
    alerts = {a["title"]: a for a in mv.security_alerts(limit=0)}
    assert "PAT-984-219" in alerts["Emergency Record Access"]["detail"] and alerts["Emergency Record Access"]["level"] == "warning"
    assert "exported log entries" in alerts["Audit Log Exported"]["detail"]
    html = admin.get(reverse("manage_dashboard")).content.decode()
    assert "Emergency Record Access" in html and "WARNING" in html and "Flag" in html


def test_alerts_flag_record_access_at_night(as_role, monkeypatch):
    from apps.accounts import manage_views as mv

    p = Patient.objects.get(code="PAT-984-219")
    monkeypatch.setattr(mv, "is_off_hours", lambda moment: False)
    log(User.objects.get(username="nurse.reyes@careboard.demo"), "AUTHORIZED", "opened the record of Y", p)
    assert not any(a["title"] == "Off-Hours Record Access" for a in mv.security_alerts(limit=0))
    monkeypatch.setattr(mv, "is_off_hours", lambda moment: True)
    found = [a for a in mv.security_alerts(limit=0) if a["title"] == "Off-Hours Record Access"]
    assert found and "PAT-984-219" in found[0]["detail"] and found[0]["level"] == "warning"


def test_off_hours_window():
    from apps.accounts.manage_views import is_off_hours

    def at(hour):
        return timezone.make_aware(timezone.datetime(2026, 9, 28, hour, 30))

    assert [is_off_hours(at(h)) for h in (3, 4, 5, 12, 21, 22, 23)] == [True, True, False, False, False, True, True]


def test_ago_wording():
    from apps.accounts.manage_views import ago

    now = timezone.now()
    assert ago(now) == "Just now" and ago(now - timedelta(minutes=10)) == "10 mins ago" and ago(now - timedelta(minutes=1, seconds=5)) == "1 min ago"
    assert ago(now - timedelta(hours=1, minutes=5)) == "1 hour ago" and ago(now - timedelta(days=2, hours=1)) == "2 days ago"


# ---- the audit trail records where things come from ----------------------------------------------------------------------------------
def test_sign_ins_are_logged_with_an_address(client, seeded):
    client.login(username="nurse.reyes@careboard.demo", password=PW)
    e = AuditEntry.objects.filter(user__username="nurse.reyes@careboard.demo", kind="SIGN_IN").first()
    assert e is not None and e.text == "signed in"
    client.post(reverse("logout"))
    client.post(reverse("login"), {"username": "nurse.reyes@careboard.demo", "password": PW})
    e = AuditEntry.objects.filter(kind="SIGN_IN").first()
    assert e.ip_address == "127.0.0.1" and e.entry_hash == e.compute_hash()


def test_failed_sign_ins_never_store_what_was_typed(client, seeded):
    client.post(reverse("login"), {"username": "nurse.reyes@careboard.demo", "password": "wrong-password-123"})
    client.post(reverse("login"), {"username": "MyRealPassword!99", "password": "x"})
    texts = list(AuditEntry.objects.filter(kind="SIGN_IN_FAILED").values_list("text", flat=True))
    assert "failed sign-in for nurse.reyes@careboard.demo" in texts and "failed sign-in for an unknown account" in texts
    assert not any("MyRealPassword" in t or "wrong-password" in t for t in texts)


def test_forwarded_addresses_are_only_trusted_when_configured(client, seeded, settings):
    client.post(reverse("login"), {"username": "x", "password": "y"}, HTTP_X_FORWARDED_FOR="203.0.113.9, 10.0.0.1")
    assert AuditEntry.objects.filter(kind="SIGN_IN_FAILED").first().ip_address == "127.0.0.1"          # spoofable header ignored
    settings.TRUST_PROXY_HEADERS = True
    client.post(reverse("login"), {"username": "x", "password": "y"}, HTTP_X_FORWARDED_FOR="203.0.113.9, 10.0.0.1")
    assert AuditEntry.objects.filter(kind="SIGN_IN_FAILED").first().ip_address == "203.0.113.9"


def test_the_address_is_protected_by_the_audit_chain(seeded):
    from django.core.management import call_command
    from django.core.management.base import CommandError

    entry = log(None, "SYSTEM", "with address", ip="10.1.1.1")
    call_command("verify_audit", verbosity=0)
    AuditEntry.objects.filter(pk=entry.pk).update(ip_address="10.9.9.9")
    with pytest.raises(CommandError):
        call_command("verify_audit", verbosity=0)


def test_old_entries_without_an_address_still_verify(seeded):
    from django.core.management import call_command

    entry = AuditEntry(kind="SYSTEM", text="old style")
    entry.save()
    AuditEntry.objects.filter(pk=entry.pk).update(ip_address=None)        # exactly how entries looked before addresses existed
    call_command("verify_audit", verbosity=0)


def test_staff_own_activity_list_leaves_out_sign_ins(as_role):
    html = as_role("nurse").get(reverse("dashboard")).content.decode()
    assert "signed in" not in html


def test_self_service_signups_leave_a_trace(client, seeded):
    client.post(reverse("register_student"), {"full_name": "Kid Person", "email": "kid@u.edu", "date_of_birth": "01/01/2004", "phone": "1",
                                              "student_id": "STU-9", "password1": "Str0ng-Passw0rd!", "password2": "Str0ng-Passw0rd!"})
    client.post(reverse("register_staff"), {"full_name": "New Nurse", "email": "nn@x.org", "employee_id": "N-9", "department": "ER", "role": "nurse",
                                            "password1": "Str0ng-Passw0rd!", "password2": "Str0ng-Passw0rd!"})
    texts = list(AuditEntry.objects.filter(kind="SYSTEM").values_list("text", flat=True))
    assert "student account created for Kid Person (self-service registration)" in texts
    assert "staff access requested by New Nurse (Nurse)" in texts


# ---- the audit-log page as designed --------------------------------------------------------------------------------------------------------
def test_log_table_shows_time_user_action_record_and_address(as_role):
    admin = as_role("admin")
    p = Patient.objects.get(code="PAT-984-219")
    log(User.objects.get(username="dr.henderson@careboard.demo"), "MODIFIED", "updated medical records for Elizabeth Hughes", p, ip="192.168.1.104")
    html = admin.get(reverse("manage_logs")).content.decode()
    for text in ("Audit &amp; Security logs", "Timestamp", "Affected Record", "IP Address", "Export Log Session", "Verify integrity",
                 "Edited Record", "Elizabeth Hughes (PAT-984-219)", "192.168.1.104", "Login Success", "Date Range:", "Live: refreshes every 15 seconds"):
        assert text in html, text
    assert "HIPAA" not in html and "Compliance" not in html


def test_action_labels():
    from apps.accounts.manage_views import action_of

    p = Patient(first_name="A", last_name="B", date_of_birth="2000-01-01", pk=1)
    def entry(kind, patient=None):
        return AuditEntry(kind=kind, text="x", patient=patient, patient_id=patient.pk if patient else None)

    assert action_of(entry("MODIFIED", p)) == ("Edited Record", "edit") and action_of(entry("MODIFIED"))[0] == "Account Change"
    assert action_of(entry("AUTHORIZED", p)) == ("Viewed Record", "view") and action_of(entry("CREATED", p)) == ("Created Record", "create")
    assert action_of(entry("SIGN_IN")) == ("Login Success", "login") and action_of(entry("SIGN_IN_FAILED"))[1] == "fail"
    assert action_of(entry("SYSTEM"))[1] == "system"


def test_summary_cards_follow_the_filters(as_role):
    admin = as_role("admin")
    p = Patient.objects.get(code="PAT-984-219")
    log(User.objects.get(username="nurse.reyes@careboard.demo"), "AUTHORIZED", "opened the record of Elizabeth Hughes", p)
    stats = admin.get(reverse("manage_logs")).context["stats"]
    assert stats["records"] >= 1 and stats["people"] >= 2 and stats["total"] >= 5
    nurse_only = admin.get(reverse("manage_logs"), {"who": "reyes"}).context["stats"]
    assert nurse_only["people"] == 1 and nurse_only["total"] < stats["total"]


def test_date_range_and_user_type_filters(as_role):
    admin = as_role("admin")
    old = log(User.objects.get(username="nurse.reyes@careboard.demo"), "SYSTEM", "long ago")
    AuditEntry.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(days=10))
    def texts(**params):
        return {e.text for e in admin.get(reverse("manage_logs"), params).context["page"]}
    assert "long ago" not in texts() and "long ago" not in texts(range="week")
    assert "long ago" in texts(range="month") and "long ago" in texts(range="all")
    assert "long ago" in texts(range="all", role="staff") and "long ago" not in texts(range="all", role="student")
    assert admin.get(reverse("manage_logs"), {"range": "nonsense"}).status_code == 200


def test_the_log_page_can_refresh_itself(as_role):
    admin = as_role("admin")
    page = admin.get(reverse("manage_logs"), {"kind": "SIGN_IN"}).content.decode()
    assert 'data-live="/manage/logs/?kind=SIGN_IN&amp;fragment=1"' in page or "fragment=1" in page
    fragment = admin.get(reverse("manage_logs"), {"kind": "SIGN_IN", "fragment": "1"}).content.decode()
    assert "Total Audit Actions" in fragment and "<html" not in fragment and "Login Success" in fragment
    assert as_role("nurse").get(reverse("manage_logs"), {"fragment": "1"}).status_code == 403
