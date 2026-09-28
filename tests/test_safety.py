from datetime import timedelta

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.urls import reverse
from django.utils import timezone

from apps.audit.models import AuditEntry
from apps.audit.services import log
from apps.history.models import LabResult, Prescription, Visit
from apps.patients.models import Patient, PatientChange
from apps.triage.models import Triage, TriageAmendment


def visit_of(code):
    return Visit.objects.get(patient__code=code, status__in=Visit.ACTIVE)


# ---- minimum necessary access ----------------------------------------------------------------------
def test_records_of_people_not_in_the_queue_need_a_reason(as_role):
    nurse = as_role("nurse")
    archived = Patient.objects.get(code="PAT-301-A")
    url = reverse("patient_detail", args=[archived.pk])
    r = nurse.get(url)
    assert r.status_code == 302 and r["Location"].startswith(reverse("patient_access", args=[archived.pk]))
    assert nurse.post(reverse("patient_access", args=[archived.pk]), {"reason": ""}).status_code == 200
    assert nurse.post(reverse("patient_access", args=[archived.pk]), {"reason": "other", "note": ""}).status_code == 200  # needs an explanation
    r = nurse.post(reverse("patient_access", args=[archived.pk]), {"reason": "continuing", "note": "", "next": "https://evil.example/"})
    assert r.status_code == 302 and r["Location"] == url  # a link to another site is ignored
    assert nurse.get(url).status_code == 200
    entry = AuditEntry.objects.filter(patient=archived, user__username="nurse.reyes@careboard.demo").first()
    assert "reason: Continuing care" in entry.text


def test_emergency_access_is_flagged_in_the_audit_log(as_role):
    doctor = as_role("physician")
    archived = Patient.objects.get(code="PAT-301-A")
    doctor.post(reverse("patient_access", args=[archived.pk]), {"reason": "emergency"})
    assert "[EMERGENCY ACCESS]" in AuditEntry.objects.filter(patient=archived).first().text


def test_patients_in_todays_queue_open_without_a_prompt(as_role):
    assert as_role("nurse").get(reverse("patient_detail", args=[visit_of("PAT-304-X").patient_id])).status_code == 200


def test_access_grant_expires(as_role):
    nurse = as_role("nurse")
    archived = Patient.objects.get(code="PAT-301-A")
    nurse.post(reverse("patient_access", args=[archived.pk]), {"reason": "continuing"})
    session = nurse.session
    session["record_access"][str(archived.pk)] -= 31 * 60
    session.save()
    assert nurse.get(reverse("patient_detail", args=[archived.pk])).status_code == 302


def test_directory_searches_are_logged_once_per_window(as_role):
    nurse = as_role("nurse")
    for _ in range(3):
        nurse.get(reverse("patient_list"), {"q": "hughes"})
    assert AuditEntry.objects.filter(text="searched the patient directory").count() == 1


# ---- correcting vitals ----------------------------------------------------------------------------------
AMEND = {"temperature_c": "36.8", "blood_pressure": "118 / 74", "pulse": "72", "respiratory_rate": "16", "oxygen_sat": "99", "pain_score": "2",
         "weight_kg": "62.0", "height_cm": "168", "chief_complaint": "Mild, dry cough for 3 days. No fever.", "reason": "Typing mistake"}


def test_correcting_a_vital_keeps_the_original(as_role):
    nurse = as_role("nurse")
    v = visit_of("PAT-984-219")
    r = nurse.post(reverse("triage_amend", args=[v.pk]), {**AMEND, "blood_pressure": "188 / 74"[::1].replace("188", "128")})
    assert r.status_code == 302
    v.triage.refresh_from_db()
    assert (v.triage.systolic, v.triage.diastolic) == (128, 74)
    a = TriageAmendment.objects.get(triage=v.triage)
    assert (a.label, a.old_value, a.new_value, a.reason) == ("Blood pressure", "118 / 74", "128 / 74", "Typing mistake")
    assert a.amended_by.username == "nurse.reyes@careboard.demo"
    assert AuditEntry.objects.filter(patient=v.patient, text__startswith="corrected blood pressure").exists()
    page = as_role("physician").get(reverse("patient_detail", args=[v.patient_id])).content.decode()
    assert "Corrected blood pressure" in page and "118 / 74 → 128 / 74" in page


def test_a_correction_needs_a_reason_and_a_real_change(as_role):
    nurse = as_role("nurse")
    v = visit_of("PAT-984-219")
    assert nurse.post(reverse("triage_amend", args=[v.pk]), {**AMEND, "reason": ""}).status_code == 200
    r = nurse.post(reverse("triage_amend", args=[v.pk]), AMEND)  # nothing differs from what is recorded
    assert r.status_code == 200 and b"Nothing was changed" in r.content and not TriageAmendment.objects.exists()


def test_correction_that_worsens_the_picture_warns_about_priority(as_role):
    nurse = as_role("nurse")
    v = visit_of("PAT-984-219")
    r = nurse.post(reverse("triage_amend", args=[v.pk]), {**AMEND, "oxygen_sat": "86"}, follow=True)
    assert "now suggest Urgent" in r.content.decode()


def test_only_nurses_and_physicians_can_correct_vitals(as_role):
    v = visit_of("PAT-984-219")
    assert as_role("receptionist").post(reverse("triage_amend", args=[v.pk]), AMEND).status_code == 403
    assert as_role("student").get(reverse("triage_amend", args=[v.pk])).status_code == 403


# ---- editing patient details ------------------------------------------------------------------------------------
def test_editing_details_keeps_the_old_values(as_role):
    desk = as_role("receptionist")
    p = Patient.objects.get(code="PAT-984-219")
    data = {"phone": "+1 (555) 000-9999", "email": "", "address": p.address, "civil_status": "Married", "blood_type": "A+",
            "allergies": p.allergies, "emergency_contact_name": "Robert Hughes", "emergency_relationship": "Spouse",
            "emergency_phone": "+1 (555) 919-4820", "reason": "New number"}
    assert desk.post(reverse("patient_edit", args=[p.pk]), data).status_code == 302
    p.refresh_from_db()
    change = PatientChange.objects.get(patient=p)
    assert p.phone == "+1 (555) 000-9999" and (change.old_value, change.new_value, change.reason) == ("+1 (555) 019-2831", "+1 (555) 000-9999", "New number")
    assert AuditEntry.objects.filter(patient=p, text__startswith="updated contact number").exists()
    r = desk.post(reverse("patient_edit", args=[p.pk]), {**data, "reason": ""}, follow=True)  # no further change
    assert b"Nothing was changed" in r.content and PatientChange.objects.filter(patient=p).count() == 1


def test_name_and_birth_date_cannot_be_changed_here(as_role):
    p = Patient.objects.get(code="PAT-984-219")
    data = {"phone": p.phone, "address": p.address, "allergies": p.allergies, "first_name": "Hacked", "date_of_birth": "01/01/2000"}
    as_role("nurse").post(reverse("patient_edit", args=[p.pk]), data)
    p.refresh_from_db()
    assert p.first_name == "Elizabeth" and str(p.date_of_birth) == "1988-10-14"


# ---- closing visits ---------------------------------------------------------------------------------------------------
def test_cancelling_needs_a_reason_and_removes_the_patient_from_the_queue(as_role):
    desk = as_role("receptionist")
    v = visit_of("PAT-304-X")
    url = reverse("visit_close", args=[v.pk])
    desk.post(url, {"outcome": "cancelled", "reason": ""})
    v.refresh_from_db()
    assert v.status == Visit.Status.REGISTERED
    desk.post(url, {"outcome": "cancelled", "reason": "Registered by mistake", "next": "https://evil.example/"})
    v.refresh_from_db()
    assert v.status == Visit.Status.CANCELLED and v.closed_reason == "Registered by mistake" and v.closed_by.username == "sarah.cole@careboard.demo"
    assert not Visit.objects.active().filter(pk=v.pk).exists()
    assert AuditEntry.objects.filter(patient=v.patient, text__startswith="cancelled the visit").exists()


def test_left_without_being_seen_and_visits_with_a_doctor_cannot_be_closed_this_way(as_role):
    nurse = as_role("nurse")
    waiting, seen = visit_of("PAT-105-D"), visit_of("PAT-984-219")
    nurse.post(reverse("visit_close", args=[waiting.pk]), {"outcome": "left"})
    nurse.post(reverse("visit_close", args=[seen.pk]), {"outcome": "left"})
    waiting.refresh_from_db(); seen.refresh_from_db()
    assert waiting.status == Visit.Status.LEFT and seen.status == Visit.Status.WITH_DOCTOR


def test_stale_waiting_visits_are_closed_by_the_command_but_visits_with_a_doctor_are_not(as_role):
    old = timezone.now() - timedelta(hours=20)
    Visit.objects.filter(patient__code__in=["PAT-810-A", "PAT-984-219"]).update(registered_at=old)
    call_command("close_stale_visits", "--dry-run", verbosity=0)
    assert visit_of("PAT-810-A").status == Visit.Status.IN_TRIAGE
    call_command("close_stale_visits", verbosity=0)
    assert Visit.objects.filter(patient__code="PAT-810-A").order_by("-registered_at").first().status == Visit.Status.LEFT
    assert visit_of("PAT-984-219").status == Visit.Status.WITH_DOCTOR


def test_dashboard_warns_about_visits_left_open_from_earlier_days(as_role):
    Visit.objects.filter(patient__code="PAT-984-219").update(registered_at=timezone.now() - timedelta(days=2))
    html = as_role("nurse").get(reverse("dashboard")).content.decode()
    assert "1 visit from before today is still open" in html


# ---- two people, one pre-check -----------------------------------------------------------------------------------
def test_a_second_person_cannot_barge_into_someone_elses_precheck_but_can_take_over(as_role):
    nurse, doctor = as_role("nurse"), as_role("physician")
    v = visit_of("PAT-304-X")
    nurse.post(reverse("triage_start", args=[v.pk]))
    r = doctor.get(reverse("triage_form", args=[v.pk]), follow=True)
    assert "is doing this pre-check" in r.content.decode()
    assert b"Take over" in doctor.get(reverse("triage_queue")).content
    doctor.post(reverse("triage_takeover", args=[v.pk]))
    v.refresh_from_db()
    assert v.triage_by.username == "dr.henderson@careboard.demo"
    assert doctor.get(reverse("triage_form", args=[v.pk])).status_code == 200
    assert nurse.get(reverse("triage_form", args=[v.pk])).status_code == 302
    assert AuditEntry.objects.filter(text__startswith="took over the triage pre-check").exists()


# ---- prescriptions and lab results ----------------------------------------------------------------------------------
RX = {"form": "rx", "medication": "Albuterol HFA", "dose": "90 mcg", "frequency": "every 4-6 hours", "duration": "10 days", "instructions": ""}


def test_prescribing_checks_allergies_first(as_role):
    doctor = as_role("physician")
    hughes = visit_of("PAT-984-219")              # allergic to penicillin
    url = reverse("patient_detail", args=[hughes.patient_id])
    r = doctor.post(url, {**RX, "medication": "Amoxicillin 500 mg"})
    assert r.status_code == 200 and b"Allergy check" in r.content and not Prescription.objects.exists()
    r = doctor.post(url, {**RX, "medication": "Amoxicillin 500 mg", "override_allergy": "on"})
    assert r.status_code == 302
    rx = Prescription.objects.get()
    assert "penicillin" in rx.allergy_warning
    assert AuditEntry.objects.filter(text__contains="allergy warning overridden").exists()
    assert doctor.post(url, RX).status_code == 302   # an unrelated drug goes straight through
    assert Prescription.objects.count() == 2


def test_prescribing_is_blocked_while_allergies_are_unknown(as_role):
    Patient.objects.filter(code="PAT-411-V").update(allergies="")
    thomas = visit_of("PAT-411-V")
    doctor = as_role("physician")
    r = doctor.post(reverse("patient_detail", args=[thomas.patient_id]), RX)
    assert r.status_code == 200 and b"have not been recorded" in r.content and not Prescription.objects.exists()


def test_only_the_physician_on_a_visit_in_consultation_can_prescribe(as_role):
    hughes = visit_of("PAT-984-219")
    for role in ("nurse", "receptionist"):
        assert as_role(role).post(reverse("patient_detail", args=[hughes.patient_id]), RX).status_code == 403
    sophia = visit_of("PAT-304-X")   # still at reception
    assert as_role("physician").post(reverse("patient_detail", args=[sophia.patient_id]), RX).status_code == 403


def test_lab_results_can_be_added_by_clinical_staff_and_never_edited(as_role):
    v = visit_of("PAT-984-219")
    url = reverse("patient_detail", args=[v.patient_id])
    lab = {"form": "lab", "test_name": "Hemoglobin", "value": "13.8", "unit": "g/dL", "reference_range": "12.0-15.5", "flag": "normal", "comment": ""}
    assert as_role("receptionist").post(url, lab).status_code == 403
    assert as_role("nurse").post(url, lab).status_code == 302
    result = LabResult.objects.get()
    assert result.entered_by.username == "nurse.reyes@careboard.demo" and result.visit == v
    assert b"Hemoglobin" in as_role("physician").get(url, {"tab": "labs"}).content
    assert as_role("physician").post(url, {**lab, "value": ""}).status_code == 200   # a result needs a value


# ---- the audit trail ----------------------------------------------------------------------------------------------------
def test_audit_chain_verifies_and_detects_tampering(seeded):
    call_command("verify_audit", verbosity=0)
    first = AuditEntry.objects.order_by("id")[0]
    AuditEntry.objects.filter(pk=first.pk).update(text="something else entirely")
    with pytest.raises(CommandError, match="FAILED"):
        call_command("verify_audit", verbosity=0)


def test_audit_chain_detects_a_deleted_entry(seeded):
    ids = list(AuditEntry.objects.order_by("id").values_list("pk", flat=True))
    AuditEntry.objects.filter(pk=ids[1]).delete()   # a bulk delete slips past the model's own guard, but not the chain
    with pytest.raises(CommandError, match="FAILED"):
        call_command("verify_audit", verbosity=0)


def test_every_new_entry_links_to_the_one_before(seeded):
    a = log(None, "SYSTEM", "first")
    b = log(None, "SYSTEM", "second")
    assert b.prev_hash == a.entry_hash and a.entry_hash == a.compute_hash()


# ---- live updates --------------------------------------------------------------------------------------------------------------------
def test_dashboard_fragment_carries_alerts_for_urgent_and_ready_patients(as_role):
    html = as_role("physician").get(reverse("dashboard_live")).content.decode()
    assert "Urgent patient waiting: David Miller" in html and "Thomas Vance is ready for consultation" in html
    assert 'id="live-alerts"' in html and "<html" not in html   # a fragment, not a whole page


def test_live_endpoints_are_for_the_right_people(client, as_role):
    assert client.get(reverse("dashboard_live")).status_code == 302
    assert as_role("student").get(reverse("dashboard_live")).status_code == 403
    assert as_role("receptionist").get(reverse("triage_queue_fragment")).status_code == 403
    assert as_role("nurse").get(reverse("triage_queue_fragment")).status_code == 200


def test_front_desk_dashboard_has_no_triage_button(as_role):
    html = as_role("receptionist").get(reverse("dashboard")).content.decode()
    assert "Start Triage pre-check" not in html and "Register New Patient" in html


def test_shift_is_shown_only_when_set(as_role):
    nurse = as_role("nurse")
    assert "Shift: 08:00 AM - 04:00 PM" in nurse.get(reverse("dashboard")).content.decode()
    nurse.user = None
    from apps.accounts.models import Profile
    Profile.objects.filter(user__username="nurse.reyes@careboard.demo").update(shift_start=None, shift_end=None)
    assert "Shift:" not in nurse.get(reverse("dashboard")).content.decode()


def test_old_triage_drafts_expire(as_role):
    nurse = as_role("nurse")
    v = visit_of("PAT-304-X")
    nurse.post(reverse("triage_start", args=[v.pk]))
    nurse.post(reverse("triage_form", args=[v.pk]), {"action": "draft", "temperature_c": "38.2"})
    session = nurse.session
    session[f"triage_draft_{v.pk}"]["_saved"] -= 13 * 3600
    session.save()
    assert not nurse.get(reverse("triage_form", args=[v.pk])).context["draft_loaded"]
