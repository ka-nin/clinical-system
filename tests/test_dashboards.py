import pytest
from django.core.management import call_command
from django.urls import reverse

PW = "CareBoard-Demo1!"


@pytest.fixture(autouse=True)
def demo(db):
    call_command("seed_demo", force=True, verbosity=0)


def login(client, email):
    assert client.login(username=email, password=PW)


def test_dashboard_requires_login(client):
    r = client.get(reverse("dashboard"))
    assert r.status_code == 302 and "/login/" in r["Location"]


@pytest.mark.parametrize("email", ["dr.henderson@careboard.demo", "nurse.reyes@careboard.demo", "sarah.cole@careboard.demo"])
def test_staff_roles_see_command_center(client, email):
    login(client, email)
    r = client.get(reverse("dashboard"))
    assert r.status_code == 200 and b"Clinical Command Center" in r.content


def test_physician_greeting_uses_title(client):
    login(client, "dr.henderson@careboard.demo")
    assert b"Dr. Henderson!" in client.get(reverse("dashboard")).content


def test_student_is_sent_to_the_portal(client):
    login(client, "student@careboard.demo")
    r = client.get(reverse("dashboard"))
    assert r.status_code == 302 and r["Location"] == reverse("portal_profile")
    page = client.get(reverse("portal_profile"))
    assert page.status_code == 200 and b"My Profile" in page.content and b"Clinical Command Center" not in page.content


def test_admin_goes_to_the_admin_area(client):
    login(client, "admin@careboard.demo")
    r = client.get(reverse("dashboard"))
    assert r.status_code == 302 and r["Location"] == reverse("manage_dashboard")


def test_login_view_lands_on_dashboard(client):
    r = client.post(reverse("login"), {"username": "DR.HENDERSON@careboard.demo", "password": PW})
    assert r.status_code == 302 and r["Location"] == reverse("dashboard")
