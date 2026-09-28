import pytest
from django.core.management import call_command
from django.urls import reverse

from apps.audit.models import AuditEntry
from apps.history.models import Consultation, Visit
from apps.patients.models import Patient

PW = "CareBoard-Demo1!"
NOTES = {"subjective": "Cough for 4 days.", "objective": "Mild wheeze.", "assessment": "Primary Diagnosis: Mild Acute Bronchitis, viral.", "plan": "Fluids and rest."}


@pytest.fixture
def seeded(db):
    call_command("seed_demo", force=True, verbosity=0)
    return Visit.objects.get(patient__code="PAT-411-V", status="with_doctor")


def as_user(client, email):
    assert client.login(username=email, password=PW)
    return client


def test_record_page_shows_triage_summary_and_timeline(client, seeded):
    as_user(client, "dr.henderson@careboard.demo")
    html = client.get(reverse("patient_detail", args=[seeded.patient_id])).content.decode()
    assert "Clinical Consultation Suite" in html and "Triage Pre-Check Summary" in html
    assert "128/82 mmHg" in html and "Logged by Nurse Reyes" in html
    for title in ("Seasonal Allergies", "Routine Physical Exam", "Acute Sinusitis"):
        assert title in html
    assert html.count("CURRENT") == 1


def test_physician_saves_draft_autosaves_and_completes(client, seeded):
    as_user(client, "dr.henderson@careboard.demo")
    r = client.post(reverse("consultation_autosave", args=[seeded.pk]), {**NOTES, "plan": ""})
    assert r.status_code == 200 and r.json()["ok"]
    r = client.post(reverse("consultation_save", args=[seeded.pk]), {**NOTES, "plan": "", "action": "complete"})
    seeded.refresh_from_db()
    assert seeded.status == Visit.Status.WITH_DOCTOR  # plan missing -> not completed
    assert Consultation.objects.get(visit=seeded).plan == ""

    r = client.post(reverse("consultation_save", args=[seeded.pk]), {**NOTES, "action": "complete"})
    assert r.status_code == 302 and r["Location"] == reverse("dashboard")
    seeded.refresh_from_db()
    assert seeded.status == Visit.Status.COMPLETED and seeded.completed_at
    assert seeded.consultation.is_completed and seeded.consultation.title == "Mild Acute Bronchitis"
    assert AuditEntry.objects.filter(patient=seeded.patient, text__startswith="completed the consultation").exists()


def test_completed_notes_cannot_be_changed(client, seeded):
    as_user(client, "dr.henderson@careboard.demo")
    client.post(reverse("consultation_save", args=[seeded.pk]), {**NOTES, "action": "complete"})
    assert client.post(reverse("consultation_autosave", args=[seeded.pk]), {**NOTES, "plan": "hacked"}).status_code == 403
    note = Consultation.objects.get(visit=seeded)
    note.plan = "changed"
    with pytest.raises(PermissionError):
        note.save()


def test_nurse_can_read_but_not_write_notes(client, seeded):
    as_user(client, "nurse.reyes@careboard.demo")
    page = client.get(reverse("patient_detail", args=[seeded.patient_id]))
    assert page.status_code == 200 and b"Only physicians can write" in page.content and b"data-consult" not in page.content
    for name in ("consultation_save", "consultation_autosave"):
        assert client.post(reverse(name, args=[seeded.pk]), NOTES).status_code == 403
    assert not Consultation.objects.get(visit=seeded).plan  # untouched


def test_front_desk_sees_no_vitals_or_notes_and_cannot_write(client, seeded):
    as_user(client, "sarah.cole@careboard.demo")
    page = client.get(reverse("patient_detail", args=[seeded.patient_id]))
    assert page.status_code == 200 and b"nurses and physicians only" in page.content
    for hidden in (b"Triage Pre-Check Summary", b"Subjective", b"128/82", b"wheez"):
        assert hidden not in page.content
    for name in ("consultation_save", "consultation_autosave"):
        assert client.post(reverse(name, args=[seeded.pk]), NOTES).status_code == 403


def test_students_and_anonymous_are_blocked(client, seeded):
    assert client.post(reverse("consultation_save", args=[seeded.pk]), NOTES).status_code == 302
    as_user(client, "student@careboard.demo")
    assert client.get(reverse("patient_detail", args=[seeded.patient_id])).status_code == 403
    assert client.post(reverse("consultation_save", args=[seeded.pk]), NOTES).status_code == 403


def test_cannot_write_notes_before_triage_is_done(client, seeded):
    sophia = Visit.objects.get(patient__code="PAT-304-X")
    as_user(client, "dr.henderson@careboard.demo")
    assert client.post(reverse("consultation_autosave", args=[sophia.pk]), NOTES).status_code == 403
    assert b"Not in consultation yet" in client.get(reverse("patient_detail", args=[sophia.patient_id])).content


def test_past_visits_tab_is_read_only_and_selectable(client, seeded):
    as_user(client, "dr.henderson@careboard.demo")
    old = seeded.patient.visits.filter(status="completed").order_by("registered_at").first()
    html = client.get(reverse("patient_detail", args=[seeded.patient_id]), {"tab": "past", "visit": old.pk}).content.decode()
    assert "read-only" in html and "Acute Sinusitis" in html and "<textarea" not in html
    assert client.get(reverse("patient_detail", args=[seeded.patient_id]), {"tab": "bogus"}).status_code == 200
