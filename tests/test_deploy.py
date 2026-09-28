import os
import subprocess
import sys

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client, override_settings
from django.urls import reverse

from apps.accounts.bootstrap import pending_migrations, prepare_database
from apps.audit.models import AuditEntry

User = get_user_model()
PW = "CareBoard-Demo1!"


def run_prod(env):
    base = {k: v for k, v in os.environ.items() if not k.startswith(("DJANGO_", "DB_", "DEMO_")) and k != "DATABASE_URL"}
    base.update({"DJANGO_SETTINGS_MODULE": "config.settings.prod", "DJANGO_SECRET_KEY": "k" * 50}, **env)
    code = "import django; django.setup(); from django.conf import settings as s; print(s.DATABASES['default']['ENGINE'], s.ALLOWED_HOSTS, s.REQUIRE_2FA, s.SECURE_SSL_REDIRECT, s.CSRF_TRUSTED_ORIGINS)"
    return subprocess.run([sys.executable, "-c", code], env=base, capture_output=True, text=True, cwd=os.getcwd())


def test_wasmer_database_settings_are_picked_up():
    r = run_prod({"DEMO_MODE": "1", "DB_HOST": "db", "DB_NAME": "x", "DB_USERNAME": "u", "DB_PASSWORD": "p"})
    assert r.returncode == 0, r.stderr
    assert "django.db.backends.mysql ['.wasmer.app'] False False ['https://*.wasmer.app']" in r.stdout


def test_real_deployments_keep_the_strict_defaults():
    r = run_prod({"DJANGO_ALLOWED_HOSTS": "clinic.org", "DB_HOST": "db", "DB_NAME": "x"})
    assert r.returncode == 0 and "['clinic.org'] True True []" in r.stdout


def test_demo_mode_still_refuses_sqlite_and_weak_keys():
    assert run_prod({"DEMO_MODE": "1"}).returncode != 0                                       # no database server
    assert run_prod({"DEMO_MODE": "1", "DB_HOST": "d", "DB_NAME": "x", "DJANGO_SECRET_KEY": "short"}).returncode != 0


def test_postgres_can_be_chosen():
    r = run_prod({"DEMO_MODE": "1", "DB_HOST": "db", "DB_NAME": "x", "DB_ENGINE": "postgres"})
    assert r.returncode == 0 and "postgresql" in r.stdout


def test_wsgi_exposes_app_for_wasmer():
    r = subprocess.run([sys.executable, "-c", "import config.wsgi as w; print(w.app is w.application)"], capture_output=True, text=True,
                       env={**{k: v for k, v in os.environ.items() if not k.startswith("DJANGO_")}, "DJANGO_SETTINGS_MODULE": "config.settings.dev"})
    assert r.stdout.strip() == "True", r.stderr


@pytest.mark.django_db
def test_first_start_setup_adds_demo_data_once(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "1")
    assert not pending_migrations()
    prepare_database()
    count = User.objects.count()
    assert count >= 5
    prepare_database()                                                          # second start: nothing duplicated or reset
    assert User.objects.count() == count


@pytest.mark.django_db
def test_seed_if_empty_leaves_existing_data_alone(seeded):
    User.objects.filter(username="nurse.reyes@careboard.demo").update(first_name="Changed")
    call_command("seed_demo", force=True, if_empty=True, verbosity=0)
    assert User.objects.get(username="nurse.reyes@careboard.demo").first_name == "Changed"


def test_demo_password_can_come_from_a_secret(db):
    code = "import os; os.environ['DEMO_PASSWORD']='From-A-Secret-99'; from apps.accounts.management.commands import seed_demo; print(seed_demo.PASSWORD)"
    r = subprocess.run([sys.executable, "-c", "import django,os; os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings.test'); django.setup(); " + code],
                       capture_output=True, text=True)
    assert r.stdout.strip() == "From-A-Secret-99", r.stderr


# ---- demo mode behaviour ----------------------------------------------------------------------------------------
@override_settings(DEMO_MODE=True)
def test_demo_banner(as_role):
    assert "Do not enter real patient information" in as_role("nurse").get(reverse("dashboard")).content.decode()


def test_no_banner_outside_demo_mode(as_role):
    assert "Do not enter real patient information" not in as_role("nurse").get(reverse("dashboard")).content.decode()


@override_settings(DEMO_MODE=True)
def test_admin_gets_a_temporary_password_for_new_accounts(as_role):
    admin = as_role("admin")
    r = admin.post(reverse("manage_user_new"), {"full_name": "Pat Friend", "email": "pat@x.org", "role": "nurse", "department": "ER",
                                                "employee_id": "", "shift_start": "", "shift_end": ""}, follow=True)
    text = r.content.decode()
    temp = text.split("temporary password: ")[1].split()[0]
    assert Client().login(username="pat@x.org", password=temp)


@override_settings(DEMO_MODE=True)
def test_admin_can_reset_a_password_to_a_temporary_one(as_role):
    admin = as_role("admin")
    pk = User.objects.get(username="nurse.reyes@careboard.demo").pk
    r = admin.post(reverse("manage_user_action", args=[pk]), {"action": "temp_password"}, follow=True)
    temp = r.content.decode().split("Temporary password for nurse.reyes@careboard.demo: ")[1].split()[0]
    assert Client().login(username="nurse.reyes@careboard.demo", password=temp)
    assert not Client().login(username="nurse.reyes@careboard.demo", password=PW)
    assert AuditEntry.objects.filter(text="set a temporary password for Maria Reyes").exists()


def test_temporary_passwords_are_demo_only(as_role):
    admin = as_role("admin")
    pk = User.objects.get(username="nurse.reyes@careboard.demo").pk
    admin.post(reverse("manage_user_action", args=[pk]), {"action": "temp_password"})
    assert Client().login(username="nurse.reyes@careboard.demo", password=PW)            # unchanged


def test_everyone_can_change_their_own_password(as_role):
    nurse = as_role("nurse")
    assert nurse.get(reverse("password_change")).status_code == 200
    r = nurse.post(reverse("password_change"), {"old_password": PW, "new_password1": "My-New-Passw0rd!", "new_password2": "My-New-Passw0rd!"})
    assert r.status_code == 302 and Client().login(username="nurse.reyes@careboard.demo", password="My-New-Passw0rd!")
    assert Client().get(reverse("password_change")).status_code == 302                 # needs sign-in


def test_gunicorn_stand_in_reads_the_address():
    from gunicorn.__main__ import _address

    assert _address(["config.wsgi:application", "--bind", "0.0.0.0:9000"]) == ("0.0.0.0", 9000)
    assert _address(["-b", "127.0.0.1:81", "x"]) == ("127.0.0.1", 81)
    assert _address(["--bind=[::]:8080"]) == ("::", 8080)
    assert _address(["config.wsgi"]) == ("0.0.0.0", int(os.environ.get("PORT", "8000")))
