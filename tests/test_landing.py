from django.core.cache import cache
from django.urls import reverse

from apps.audit.services import log
from apps.history.models import Visit
from apps.patients.models import Patient

NAMES = ["Elizabeth", "Hughes", "David Miller", "Sophia", "Thomas Vance", "Henderson", "Reyes", "Sarah Cole", "Juan Dela Cruz",
         "PAT-", "@careboard.demo", "Penicillin", "192.168."]


def test_landing_shows_real_counts(client, seeded):
    ctx = client.get(reverse("home")).context["live"]
    assert ctx["patients"] == Patient.objects.count()
    assert ctx["active"] == Visit.objects.filter(status__in=Visit.ACTIVE).count()
    assert ctx["registered"] + ctx["in_triage"] + ctx["with_doctor"] == ctx["active"]


def test_landing_changes_when_the_data_changes(client, seeded):
    before = client.get(reverse("home")).context["live"]["patients"]
    Patient.objects.create(first_name="New", last_name="Person", date_of_birth="2000-01-01", phone="1", address="x")
    cache.clear()
    assert client.get(reverse("home")).context["live"]["patients"] == before + 1


def test_public_page_never_shows_names_or_patient_details(client, seeded):
    p = Patient.objects.get(code="PAT-984-219")
    log(None, "AUTHORIZED", "opened the record of Elizabeth Hughes [EMERGENCY ACCESS]", p, ip="192.168.1.9")
    cache.clear()
    html = client.get(reverse("home")).content.decode()
    for name in NAMES:
        assert name not in html, name
    assert "The system opened a patient record" in html


def test_sign_ins_are_not_shown_publicly(client, seeded):
    log(None, "SIGN_IN_FAILED", "failed sign-in for someone")
    cache.clear()
    assert "sign-in" not in client.get(reverse("home")).content.decode().lower().split("live audit log")[1][:3000]


def test_empty_database_shows_a_friendly_message(client, db):
    html = client.get(reverse("home")).content.decode()
    assert "No activity yet" in html and ">0<" in html
