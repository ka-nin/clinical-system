import os
import subprocess
import sys

import pyotp
import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.management import call_command
from django.test import override_settings
from django.urls import reverse

from apps.accounts import twofactor
from apps.accounts.models import Profile, TwoFactor

PW = "CareBoard-Demo1!"
User = get_user_model()
GOOD_ENV = {
    "DJANGO_SETTINGS_MODULE": "config.settings.prod", "DJANGO_SECRET_KEY": "x" * 50, "DJANGO_ALLOWED_HOSTS": "clinic.example.com",
    "DATABASE_URL": "postgres://u:p@localhost:5432/db",
}


def run_prod(env_overrides):
    env = {k: v for k, v in os.environ.items() if not k.startswith("DJANGO_") and k != "DATABASE_URL"}
    env.update(GOOD_ENV)
    env.update(env_overrides)
    env = {k: v for k, v in env.items() if v is not None}
    return subprocess.run([sys.executable, "-c", "import django; django.setup()"], env=env, capture_output=True, text=True, cwd=os.getcwd())


# ---- production safeguards -------------------------------------------------
def test_prod_starts_with_a_complete_environment():
    assert run_prod({}).returncode == 0


@pytest.mark.parametrize("override, expected", [
    ({"DJANGO_SECRET_KEY": ""}, "DJANGO_SECRET_KEY"),
    ({"DJANGO_SECRET_KEY": "short"}, "DJANGO_SECRET_KEY"),
    ({"DJANGO_ALLOWED_HOSTS": ""}, "DJANGO_ALLOWED_HOSTS"),
    ({"DATABASE_URL": "sqlite:///db.sqlite3"}, "DATABASE_URL"),
])
def test_prod_refuses_unsafe_configuration(override, expected):
    result = run_prod(override)
    assert result.returncode != 0 and expected in result.stderr


# ---- login lockout ---------------------------------------------------------
AXES = dict(
    AXES_ENABLED=True,
    AUTHENTICATION_BACKENDS=["axes.backends.AxesStandaloneBackend", "apps.accounts.backends.CaseInsensitiveBackend"],
    MIDDLEWARE=[
        "django.middleware.security.SecurityMiddleware", "django.contrib.sessions.middleware.SessionMiddleware",
        "django.middleware.common.CommonMiddleware", "django.middleware.csrf.CsrfViewMiddleware",
        "django.contrib.auth.middleware.AuthenticationMiddleware", "apps.accounts.middleware.RequireTwoFactorMiddleware",
        "axes.middleware.AxesMiddleware", "django.contrib.messages.middleware.MessageMiddleware",
    ],
)


@pytest.mark.django_db
def test_five_wrong_passwords_lock_the_account(client):
    call_command("seed_demo", force=True, verbosity=0)
    with override_settings(**AXES):
        for _ in range(5):
            client.post(reverse("login"), {"username": "nurse.reyes@careboard.demo", "password": "wrong-password"})
        r = client.post(reverse("login"), {"username": "nurse.reyes@careboard.demo", "password": PW})  # even the right one
        assert r.status_code == 429 or b"Too many failed sign-ins" in r.content
        assert "_auth_user_id" not in client.session


# ---- two-step sign-in ------------------------------------------------------
@pytest.fixture
def nurse(db):
    call_command("seed_demo", force=True, verbosity=0)
    return User.objects.get(username="nurse.reyes@careboard.demo")


def enrol(user):
    device = twofactor.get_or_start(user)
    twofactor.confirm(device)
    return device, twofactor.new_recovery_codes(device)


def test_password_alone_is_not_enough_once_2fa_is_on(client, nurse):
    device, _ = enrol(nurse)
    r = client.post(reverse("login"), {"username": nurse.username, "password": PW})
    assert r.status_code == 302 and r["Location"] == reverse("login_verify")
    assert "_auth_user_id" not in client.session
    assert client.get(reverse("dashboard")).status_code == 302  # still signed out

    r = client.post(reverse("login_verify"), {"code": pyotp.TOTP(device.secret).now()})
    assert r.status_code == 302 and client.get(reverse("dashboard")).status_code == 200


def test_wrong_and_reused_codes_are_rejected(client, nurse):
    device, _ = enrol(nurse)
    client.post(reverse("login"), {"username": nurse.username, "password": PW})
    assert client.post(reverse("login_verify"), {"code": "000000"}).status_code == 200
    code = pyotp.TOTP(device.secret).now()
    client.post(reverse("login_verify"), {"code": code})
    client.post(reverse("logout"))
    client.post(reverse("login"), {"username": nurse.username, "password": PW})
    client.post(reverse("login_verify"), {"code": code})  # same code again
    assert "_auth_user_id" not in client.session


def test_five_wrong_codes_cancel_the_attempt(client, nurse):
    enrol(nurse)
    client.post(reverse("login"), {"username": nurse.username, "password": PW})
    for _ in range(5):
        r = client.post(reverse("login_verify"), {"code": "111111"})
    assert r.status_code == 302 and r["Location"] == reverse("login")
    assert client.get(reverse("login_verify")).status_code == 302


def test_recovery_code_works_once(client, nurse):
    _, codes = enrol(nurse)
    client.post(reverse("login"), {"username": nurse.username, "password": PW})
    assert client.post(reverse("login_verify"), {"code": codes[0]}).status_code == 302
    assert client.get(reverse("dashboard")).status_code == 200
    client.post(reverse("logout"))
    client.post(reverse("login"), {"username": nurse.username, "password": PW})
    client.post(reverse("login_verify"), {"code": codes[0]})
    assert "_auth_user_id" not in client.session


@override_settings(REQUIRE_2FA=True)
def test_staff_without_2fa_are_sent_to_set_it_up(client, nurse):
    client.login(username=nurse.username, password=PW)
    r = client.get(reverse("dashboard"))
    assert r.status_code == 302 and r["Location"] == reverse("security_2fa")
    page = client.get(reverse("security_2fa"))
    assert page.status_code == 200 and b"<svg" in page.content
    device = TwoFactor.objects.get(user=nurse)
    assert client.post(reverse("security_2fa"), {"code": "000000"}).status_code == 200
    r = client.post(reverse("security_2fa"), {"code": pyotp.TOTP(device.secret).now()})
    assert b"recovery codes" in r.content
    assert client.get(reverse("dashboard")).status_code == 200


@override_settings(REQUIRE_2FA=True)
def test_students_are_not_forced_into_2fa(client, db):
    call_command("seed_demo", force=True, verbosity=0)
    client.login(username="student@careboard.demo", password=PW)
    assert client.get(reverse("portal_profile")).status_code == 200  # no detour to the 2FA setup page


# ---- password reset and approval email ------------------------------------
def test_password_reset_email_goes_to_active_accounts_only(client, nurse):
    client.post(reverse("password_reset"), {"email": nurse.email})
    assert len(mail.outbox) == 1 and "/password-reset/" in mail.outbox[0].body
    client.post(reverse("password_reset"), {"email": "nobody@nowhere.test"})
    assert len(mail.outbox) == 1  # unknown address: same page, no email, nothing revealed
    nurse.is_active = False
    nurse.save()
    client.post(reverse("password_reset"), {"email": nurse.email})
    assert len(mail.outbox) == 1


def test_password_reset_link_sets_a_new_password(client, nurse):
    client.post(reverse("password_reset"), {"email": nurse.email})
    link = next(w for w in mail.outbox[0].body.split() if "/password-reset/" in w)
    page = client.get(link, follow=True)
    assert page.status_code == 200
    r = client.post(page.request["PATH_INFO"], {"new_password1": "Another-Str0ng-Pass!", "new_password2": "Another-Str0ng-Pass!"})
    assert r.status_code == 302
    nurse.refresh_from_db()
    assert nurse.check_password("Another-Str0ng-Pass!")


def test_approving_staff_sends_an_email(db):
    from django.contrib.admin.sites import site
    from django.test import RequestFactory

    from apps.accounts.forms import StaffRegistrationForm

    form = StaffRegistrationForm({"full_name": "New Nurse", "email": "new@x.org", "employee_id": "N-1", "department": "ER",
                                  "role": "nurse", "password1": PW, "password2": PW})
    assert form.is_valid(), form.errors
    form.save()
    admin_obj = site._registry[Profile]
    request = RequestFactory().get("/")
    request._messages = type("M", (), {"add": lambda *a, **k: None})()
    admin_obj.approve_accounts(request, Profile.objects.filter(user__username="new@x.org"))
    assert User.objects.get(username="new@x.org").is_active
    assert len(mail.outbox) == 1 and mail.outbox[0].to == ["new@x.org"]
