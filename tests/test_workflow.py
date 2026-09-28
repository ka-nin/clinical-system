import pytest
from django.urls import reverse

from apps.audit.models import AuditEntry
from apps.history.models import Visit
from apps.patients.models import Patient

NEW = {"full_name": "Ana Lopez", "date_of_birth": "02/03/1990", "sex": "female", "civil_status": "", "blood_type": "", "allergies": "NKDA",
       "phone": "+1 555 000 1111", "email": "", "address": "1 Main St",
       "emergency_contact_name": "Pedro Lopez", "emergency_relationship": "Father", "emergency_phone": "+1 555 000 2222"}
VITALS = {"temperature_c": "37.1", "blood_pressure": "120 / 80", "pulse": "70", "respiratory_rate": "16", "oxygen_sat": "98", "pain_score": "2",
          "weight_kg": "60.5", "height_cm": "165", "chief_complaint": "Headache", "priority": "normal", "identity_verified": "on"}


def register(client, **overrides):
    return client.post(reverse("patient_create"), {**NEW, **overrides})


def start_triage(as_role):
    desk, nurse = as_role("receptionist"), as_role("nurse")
    register(desk)
    visit = Visit.objects.get(patient__last_name="Lopez")
    nurse.post(reverse("triage_start", args=[visit.pk]))
    return nurse, visit


# ---- intake ----------------------------------------------------------------------------------
def test_register_new_patient_adds_to_queue_and_logs(as_role):
    desk = as_role("receptionist")
    r = register(desk)
    assert r.status_code == 302 and r["Location"] == reverse("dashboard")  # the front desk has no triage page
    p = Patient.objects.get(last_name="Lopez")
    assert p.code == f"PAT-{p.pk:05d}" and (p.first_name, p.emergency_relationship, p.allergies) == ("Ana", "Father", "NKDA")
    assert p.visits.get().status == Visit.Status.REGISTERED
    assert AuditEntry.objects.filter(patient=p, kind="CREATED", user__username="sarah.cole@careboard.demo").exists()


def test_a_nurse_registering_lands_on_the_triage_list(as_role):
    assert register(as_role("nurse"))["Location"] == reverse("triage_queue")


def test_allergies_must_be_answered(as_role):
    r = register(as_role("receptionist"), allergies="")
    assert r.status_code == 200 and "allergies" in r.context["form"].errors and not Patient.objects.filter(last_name="Lopez").exists()


def test_existing_patient_is_reused_not_duplicated(as_role):
    desk = as_role("receptionist")
    register(desk)
    Visit.objects.filter(patient__last_name="Lopez").update(status="completed")
    register(desk)
    assert Patient.objects.filter(last_name="Lopez").count() == 1 and Visit.objects.filter(patient__last_name="Lopez").count() == 2


def test_cannot_queue_someone_already_in_queue(as_role):
    desk = as_role("receptionist")
    register(desk)
    r = register(desk)
    assert r.status_code == 200 and b"already in today" in r.content and Visit.objects.filter(patient__last_name="Lopez").count() == 1


def test_multi_word_surname_is_kept_together(as_role):
    register(as_role("receptionist"), full_name="Juan Dela Cruz", date_of_birth="08/09/1985")
    assert Patient.objects.get(first_name="Juan", last_name="Dela Cruz").full_name == "Juan Dela Cruz"


def test_single_name_and_missing_emergency_contact_rejected(as_role):
    r = register(as_role("receptionist"), full_name="Madonna", emergency_phone="")
    assert {"full_name", "emergency_phone"} <= set(r.context["form"].errors) and not Patient.objects.filter(first_name="Madonna").exists()


def test_possible_duplicate_asks_before_creating_a_second_record(as_role):
    desk = as_role("receptionist")
    register(desk, full_name="Jon Smith", date_of_birth="05/05/1985")
    Visit.objects.filter(patient__last_name="Smith").update(status="completed")
    r = register(desk, full_name="John Smith", date_of_birth="05/05/1985")
    assert r.status_code == 200 and b"might be someone already registered" in r.content
    assert Patient.objects.filter(last_name="Smith").count() == 1
    # "none of these" registers a new person
    r = register(desk, full_name="John Smith", date_of_birth="05/05/1985", confirm_new="1")
    assert r.status_code == 302 and Patient.objects.filter(last_name="Smith").count() == 2


def test_choosing_a_suggested_record_reuses_it(as_role):
    desk = as_role("receptionist")
    register(desk, full_name="Jon Smith", date_of_birth="05/05/1985")
    jon = Patient.objects.get(first_name="Jon")
    Visit.objects.filter(patient=jon).update(status="completed")
    r = desk.post(reverse("patient_create"), {**NEW, "full_name": "John Smith", "date_of_birth": "05/05/1985", "use_patient": jon.pk})
    assert r.status_code == 302 and Patient.objects.filter(last_name="Smith").count() == 1 and jon.visits.count() == 2


def test_save_as_draft_then_restore_then_register_clears_it(as_role):
    desk = as_role("receptionist")
    assert desk.post(reverse("patient_create"), {"action": "draft", "full_name": "Ana Lopez", "phone": "123"}).status_code == 302
    assert not Patient.objects.filter(last_name="Lopez").exists()
    page = desk.get(reverse("patient_create"))
    assert page.context["draft_loaded"] and b'value="Ana Lopez"' in page.content
    register(desk)
    assert not desk.get(reverse("patient_create")).context["draft_loaded"]


def test_discard_draft(as_role):
    desk = as_role("receptionist")
    desk.post(reverse("patient_create"), {"action": "draft", "full_name": "Ana Lopez"})
    desk.post(reverse("patient_create"), {"action": "discard"})
    assert not desk.get(reverse("patient_create")).context["draft_loaded"]


def test_old_drafts_expire(as_role):
    desk = as_role("receptionist")
    desk.post(reverse("patient_create"), {"action": "draft", "full_name": "Ana Lopez"})
    session = desk.session
    session["intake_draft"]["_saved"] -= 13 * 3600
    session.save()
    assert not desk.get(reverse("patient_create")).context["draft_loaded"]


# ---- triage ------------------------------------------------------------------------------------
def test_triage_flow_moves_patient_to_doctor(as_role):
    nurse, v = start_triage(as_role)
    v.refresh_from_db()
    assert v.status == Visit.Status.IN_TRIAGE and v.triage_started_at and v.triage_by.username == "nurse.reyes@careboard.demo"
    assert nurse.post(reverse("triage_form", args=[v.pk]), VITALS).status_code == 302
    v.refresh_from_db()
    t = v.triage
    assert v.status == Visit.Status.WITH_DOCTOR and (t.systolic, t.respiratory_rate, t.pain_score, t.identity_verified) == (120, 16, 2, True)
    nurse.post(reverse("triage_form", args=[v.pk]), {**VITALS, "blood_pressure": "200 / 90"})  # recorded once
    v.triage.refresh_from_db()
    assert v.triage.systolic == 120


def test_front_desk_cannot_use_triage(as_role):
    nurse, v = start_triage(as_role)
    desk = as_role("receptionist")
    assert desk.get(reverse("triage_queue")).status_code == 403
    assert desk.get(reverse("triage_form", args=[v.pk])).status_code == 403
    assert desk.post(reverse("triage_start", args=[v.pk])).status_code == 403


def test_bad_vitals_are_rejected(as_role):
    nurse, v = start_triage(as_role)
    r = nurse.post(reverse("triage_form", args=[v.pk]), {**VITALS, "temperature_c": "99"})
    assert r.status_code == 200 and not hasattr(Visit.objects.get(pk=v.pk), "triage")


def test_identity_must_be_confirmed(as_role):
    nurse, v = start_triage(as_role)
    r = nurse.post(reverse("triage_form", args=[v.pk]), {k: x for k, x in VITALS.items() if k != "identity_verified"})
    assert r.status_code == 200 and "identity_verified" in r.context["form"].errors


def test_blood_pressure_must_be_valid(as_role):
    nurse, v = start_triage(as_role)
    for bad in ("120", "abc", "80 / 120", "300 / 90", "120/"):
        r = nurse.post(reverse("triage_form", args=[v.pk]), {**VITALS, "blood_pressure": bad})
        assert r.status_code == 200 and "blood_pressure" in r.context["form"].errors, bad
    assert nurse.post(reverse("triage_form", args=[v.pk]), {**VITALS, "blood_pressure": "118/74"}).status_code == 302
    v.refresh_from_db()
    assert (v.triage.systolic, v.triage.diastolic, v.triage.height_cm) == (118, 74, 165)


def test_priority_level_is_saved_and_urgent_sorts_first(as_role):
    nurse, v = start_triage(as_role)
    nurse.post(reverse("triage_form", args=[v.pk]), {**VITALS, "priority": "urgent"})
    v.refresh_from_db()
    assert v.priority == "urgent" and v.status == Visit.Status.WITH_DOCTOR
    assert list(Visit.objects.active().order_by("-priority", "registered_at").values_list("priority", flat=True))[0] == "urgent"
    assert b"Urgent" in as_role("physician").get(reverse("dashboard")).content


def test_choosing_a_lower_priority_than_suggested_needs_a_reason(as_role):
    nurse, v = start_triage(as_role)
    danger = {**VITALS, "oxygen_sat": "86", "priority": "normal"}   # SpO2 86% suggests Urgent
    r = nurse.post(reverse("triage_form", args=[v.pk]), danger)
    assert r.status_code == 200 and "override_reason" in r.context["form"].errors
    r = nurse.post(reverse("triage_form", args=[v.pk]), {**danger, "override_reason": "Reading was a loose finger probe; re-measured 97%"})
    assert r.status_code == 302
    v.refresh_from_db()
    assert v.triage.suggested_priority == "urgent" and "loose finger" in v.triage.override_reason and v.priority == "normal"


def test_matching_the_suggestion_needs_no_reason_and_none_is_stored(as_role):
    nurse, v = start_triage(as_role)
    nurse.post(reverse("triage_form", args=[v.pk]), {**VITALS, "oxygen_sat": "86", "priority": "urgent", "override_reason": "ignored"})
    v.refresh_from_db()
    assert v.triage.override_reason == "" and v.priority == "urgent"


def test_allergies_are_asked_at_triage_when_never_recorded(as_role):
    nurse = as_role("nurse")
    sophia = Visit.objects.get(patient__code="PAT-304-X")
    assert sophia.patient.allergy_status == "unknown"
    nurse.post(reverse("triage_start", args=[sophia.pk]))
    page = nurse.get(reverse("triage_form", args=[sophia.pk]))
    assert b"Allergies not recorded" in page.content and "allergies" in page.context["form"].fields
    r = nurse.post(reverse("triage_form", args=[sophia.pk]), VITALS)
    assert r.status_code == 200 and "allergies" in r.context["form"].errors  # must be answered
    r = nurse.post(reverse("triage_form", args=[sophia.pk]), {**VITALS, "allergies": "Latex"})
    assert r.status_code == 302
    sophia.patient.refresh_from_db()
    assert sophia.patient.allergies == "Latex"


def test_triage_save_progress_restores_and_does_not_complete(as_role):
    nurse, v = start_triage(as_role)
    r = nurse.post(reverse("triage_form", args=[v.pk]), {"action": "draft", "temperature_c": "38.2", "blood_pressure": "130 / 85", "priority": "priority"})
    assert r.status_code == 302
    v.refresh_from_db()
    assert v.status == Visit.Status.IN_TRIAGE and not hasattr(v, "triage")
    page = nurse.get(reverse("triage_form", args=[v.pk]))
    assert page.context["draft_loaded"] and b'value="38.2"' in page.content and b'value="130 / 85"' in page.content
    nurse.post(reverse("triage_form", args=[v.pk]), VITALS)
    assert nurse.get(reverse("triage_form", args=[v.pk])).status_code == 302


def test_assess_endpoint_uses_the_patients_age(as_role):
    nurse, v = start_triage(as_role)
    r = nurse.post(reverse("triage_assess", args=[v.pk]), {"pulse": "130", "spo2": "99", "bp": "118 / 74", "temp": "", "weight": "abc"})
    data = r.json()
    assert data["hints"]["pulse"][0] == "Abnormal" and data["hints"]["spo2"] == ["Optimal", "ok"] and data["suggested"] == "urgent"
    assert "weight" not in data["hints"]  # half-typed numbers are ignored, not errors
    assert nurse.get(reverse("triage_assess", args=[v.pk])).status_code == 405
