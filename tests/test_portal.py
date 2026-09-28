import hashlib
from html import unescape

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.urls import reverse

from apps.audit.models import AuditEntry
from apps.history import attachments
from apps.history.models import Attachment
from apps.history.sample_pdf import make_pdf
from apps.patients.models import Patient
from apps.accounts.models import Profile

PDF = make_pdf("Test report", ["hello"])


def upload(name="report.pdf", data=PDF, ctype="application/pdf"):
    return SimpleUploadedFile(name, data, content_type=ctype)


def hughes():
    return Patient.objects.get(code="PAT-984-219")


# ---- the student portal ------------------------------------------------------------------------------------------
def test_portal_shows_only_the_students_own_record(as_role):
    student = as_role("student")
    html = student.get(reverse("portal_profile")).content.decode()
    assert "Elizabeth Hughes" in html and "STU-984-219" in html and "Oct 14, 1988" in html and "ACTIVE RECORD" in html
    assert "Latest Triage Vitals Quick View" in html and "Follow-up Hypertension Management" in html
    for other in ("David Miller", "Thomas Vance", "Sophia Reynolds"):
        assert other not in html


def test_visit_summary_uses_the_doctors_plain_language_text_and_hides_the_clinical_notes(as_role):
    html = as_role("student").get(reverse("portal_profile")).content.decode()
    assert "Blood pressure readings remain stable within target parameters" in html
    assert "Chest auscultation" not in html and "Primary Diagnosis" not in html


def test_vitals_use_calm_wording_when_a_reading_is_abnormal(as_role):
    from apps.triage.models import Triage

    Triage.objects.filter(visit__patient=hughes()).update(temperature_c="39.8", pulse=140)
    html = as_role("student").get(reverse("portal_profile")).content.decode()
    assert "Discuss with clinic" in html and "High Fever" not in html and "Abnormal" not in html and "Crisis" not in html


def test_an_unlinked_student_sees_nothing_and_is_told_how_to_get_linked(client, seeded):
    from apps.accounts.forms import StudentRegistrationForm

    form = StudentRegistrationForm({"full_name": "Sam New", "email": "sam@uni.edu", "date_of_birth": "01/02/2004", "phone": "1",
                                    "student_id": "STU-1", "password1": "Str0ng-Passw0rd!", "password2": "Str0ng-Passw0rd!"})
    assert form.is_valid(), form.errors
    form.save()
    assert client.login(username="sam@uni.edu", password="Str0ng-Passw0rd!")
    for name in ("portal_profile", "portal_records", "portal_visits"):
        html = client.get(reverse(name)).content.decode()
        assert "isn't linked to a clinic record" in html and "Elizabeth" not in html
    assert client.post(reverse("portal_upload"), {"file": upload(), "category": "lab"}).status_code == 302
    assert not Attachment.objects.filter(uploaded_by__username="sam@uni.edu").exists()


def test_portal_is_for_students_only(client, as_role):
    assert client.get(reverse("portal_profile")).status_code == 302
    for role in ("nurse", "physician", "receptionist", "admin"):
        assert as_role(role).get(reverse("portal_profile")).status_code == 403


def test_students_cannot_reach_clinical_pages(as_role):
    student = as_role("student")
    p = hughes()
    for url in (reverse("patient_detail", args=[p.pk]), reverse("patient_list"), reverse("triage_queue"), reverse("dashboard_live")):
        assert student.get(url).status_code in (403, 302) and student.get(url).status_code != 200


def test_portal_access_is_logged(as_role):
    as_role("student").get(reverse("portal_profile"))
    assert AuditEntry.objects.filter(user__username="student@careboard.demo", text="viewed their own health record").count() == 1


def test_records_page_lists_only_what_the_patient_may_see(as_role):
    Attachment.objects.filter(patient=hughes(), filename="blood-count-report.pdf").update(visible_to_patient=False)
    html = as_role("student").get(reverse("portal_records")).content.decode()
    assert "blood-count-report.pdf" not in html and "outside-clinic-letter.pdf" in html and "Awaiting review" in html


# ---- the PDF rules --------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("name,data,ok", [
    ("report.pdf", PDF, True),
    ("report.exe", PDF, False),                                  # wrong extension
    ("report.pdf", b"MZ\x90\x00 not a pdf", False),              # wrong content
    ("report.pdf", PDF[:-8], False),                             # truncated: no %%EOF
    ("report.pdf", PDF.replace(b"/Type /Catalog", b"/Type /Catalog /OpenAction << /S /JavaScript /JS (app.alert(1)) >>"), False),
    ("report.pdf", PDF.replace(b"/Type /Catalog", b"/Type /Catalog /Names << /EmbeddedFiles 9 0 R >> /EmbeddedFile"), False),
    ("report.pdf", PDF.replace(b"/Type /Catalog", b"/Type /Catalog /S /J#61vaScript"), False),   # hidden with #hex
])
def test_pdf_validation(name, data, ok):
    form = attachments.AttachmentForm({"category": "lab"}, {"file": upload(name, data)})
    assert form.is_valid() == ok


def test_oversized_files_are_refused():
    big = PDF + b"0" * (attachments.MAX_BYTES + 1)
    assert not attachments.AttachmentForm({"category": "lab"}, {"file": upload(data=big)}).is_valid()


def test_filenames_are_cleaned():
    assert attachments.clean_filename("../../etc/passwd") == "passwd.pdf"
    assert attachments.clean_filename('a"b<c>.pdf') == "a_b_c_.pdf"
    assert attachments.clean_filename("") == "document.pdf"


# ---- staff upload, review, withdraw, download -----------------------------------------------------------------------------
def staff_upload(client, patient, **extra):
    return client.post(reverse("attachment_upload", args=[patient.pk]), {"file": upload(), "category": "lab", "description": "CBC",
                                                                       "visible_to_patient": "on", **extra})


def test_clinical_staff_can_attach_a_pdf_and_the_student_can_download_it(as_role):
    nurse, student = as_role("nurse"), as_role("student")
    p = hughes()
    assert staff_upload(nurse, p).status_code == 302
    item = Attachment.objects.get(patient=p, description="CBC")
    assert item.source == "clinic" and item.review_status == "accepted" and item.sha256 == hashlib.sha256(PDF).hexdigest()
    assert AuditEntry.objects.filter(patient=p, text__startswith="uploaded the lab report").exists()
    r = student.get(reverse("attachment_download", args=[item.pk]))
    assert r.status_code == 200 and r["Content-Type"] == "application/pdf" and r.content == PDF
    assert r["X-Content-Type-Options"] == "nosniff" and "no-store" in r["Cache-Control"] and "attachment" in r["Content-Disposition"]
    assert "inline" in nurse.get(reverse("attachment_download", args=[item.pk]) + "?inline=1")["Content-Disposition"]
    assert AuditEntry.objects.filter(patient=p, text__startswith="opened the file", user__username="student@careboard.demo").exists()


def test_hidden_files_are_not_visible_to_the_patient(as_role):
    p = hughes()
    nurse = as_role("nurse")
    nurse.post(reverse("attachment_upload", args=[p.pk]), {"file": upload(), "category": "other"})   # checkbox left off
    item = Attachment.objects.get(patient=p, category="other")
    assert not item.visible_to_patient
    assert as_role("student").get(reverse("attachment_download", args=[item.pk])).status_code == 403
    assert nurse.get(reverse("attachment_download", args=[item.pk])).status_code == 200


def test_files_of_other_patients_and_front_desk_are_blocked(as_role):
    nurse = as_role("nurse")
    other = Patient.objects.get(code="PAT-810-A")
    staff_upload(nurse, other)
    item = Attachment.objects.get(patient=other)
    assert as_role("student").get(reverse("attachment_download", args=[item.pk])).status_code == 403   # someone else's file
    assert as_role("receptionist").get(reverse("attachment_download", args=[item.pk])).status_code == 403
    assert as_role("admin").get(reverse("attachment_download", args=[item.pk])).status_code == 403
    assert as_role("receptionist").post(reverse("attachment_upload", args=[other.pk]), {"file": upload(), "category": "lab"}).status_code == 403


def test_downloads_need_a_login(client, seeded):
    item = Attachment.objects.first()
    r = client.get(reverse("attachment_download", args=[item.pk]))
    assert r.status_code == 302 and "/login/" in r["Location"]


def test_a_bad_upload_is_refused_with_a_message(as_role):
    nurse = as_role("nurse")
    r = nurse.post(reverse("attachment_upload", args=[hughes().pk]), {"file": upload("x.pdf", b"nope"), "category": "lab"}, follow=True)
    assert "doesn't look like a valid PDF" in unescape(r.content.decode()) and not Attachment.objects.filter(description="").exclude(filename__contains="-").exists()


def test_withdrawing_hides_a_file_everywhere_but_keeps_it(as_role):
    nurse, student = as_role("nurse"), as_role("student")
    p = hughes()
    staff_upload(nurse, p)
    item = Attachment.objects.get(patient=p, description="CBC")
    nurse.post(reverse("attachment_withdraw", args=[item.pk]), {"reason": ""})
    item.refresh_from_db()
    assert not item.is_withdrawn                                            # a reason is required
    nurse.post(reverse("attachment_withdraw", args=[item.pk]), {"reason": "Wrong patient"})
    item.refresh_from_db()
    assert item.is_withdrawn and item.withdrawn_reason == "Wrong patient" and Attachment.objects.filter(pk=item.pk).exists()
    for client in (nurse, student):
        assert client.get(reverse("attachment_download", args=[item.pk])).status_code == 403
    assert "CBC" not in nurse.get(reverse("patient_detail", args=[p.pk]), {"tab": "attachments"}).content.decode()


# ---- students sending documents --------------------------------------------------------------------------------------------
def test_a_student_upload_waits_for_review_and_is_never_silently_accepted(as_role):
    student, nurse = as_role("student"), as_role("nurse")
    p = hughes()
    Attachment.objects.filter(patient=p, source="patient").delete()
    r = student.post(reverse("portal_upload"), {"file": upload("note.pdf"), "category": "outside", "description": "From my doctor"})
    assert r.status_code == 302
    item = Attachment.objects.get(patient=p, source="patient")
    assert item.review_status == "pending" and item.uploaded_by.username == "student@careboard.demo"
    tab = nurse.get(reverse("patient_detail", args=[p.pk]), {"tab": "attachments"}).content.decode()
    assert "Patient · Awaiting review" in tab and 'class="tab__badge"' in tab
    nurse.post(reverse("attachment_review", args=[item.pk]), {"decision": "decline", "note": ""})
    item.refresh_from_db()
    assert item.review_status == "pending"                                  # declining needs a note
    nurse.post(reverse("attachment_review", args=[item.pk]), {"decision": "decline", "note": "Please send a clearer scan"})
    item.refresh_from_db()
    assert item.review_status == "rejected"
    assert "Please send a clearer scan" in student.get(reverse("portal_records")).content.decode()


def test_accepting_a_student_file(as_role):
    student, nurse = as_role("student"), as_role("nurse")
    student.post(reverse("portal_upload"), {"file": upload("n.pdf"), "category": "lab"})
    item = Attachment.objects.filter(source="patient").latest("uploaded_at")
    nurse.post(reverse("attachment_review", args=[item.pk]), {"decision": "accept"})
    item.refresh_from_db()
    assert item.review_status == "accepted" and item.reviewed_by.username == "nurse.reyes@careboard.demo"
    assert as_role("receptionist").post(reverse("attachment_review", args=[item.pk]), {"decision": "accept"}).status_code == 403


def test_students_cannot_flood_the_clinic_with_uploads(as_role):
    student = as_role("student")
    Attachment.objects.filter(patient=hughes(), source="patient").delete()
    for i in range(attachments.MAX_PENDING_PER_PATIENT + 2):
        student.post(reverse("portal_upload"), {"file": upload(f"n{i}.pdf"), "category": "other"})
    assert Attachment.objects.filter(patient=hughes(), source="patient", review_status="pending").count() == attachments.MAX_PENDING_PER_PATIENT


def test_students_cannot_review_or_withdraw_or_use_staff_upload(as_role):
    student = as_role("student")
    item = Attachment.objects.filter(patient=hughes(), source="patient").first()
    assert student.post(reverse("attachment_review", args=[item.pk]), {"decision": "accept"}).status_code == 403
    assert student.post(reverse("attachment_withdraw", args=[item.pk]), {"reason": "x"}).status_code == 403
    assert student.post(reverse("attachment_upload", args=[hughes().pk]), {"file": upload(), "category": "lab"}).status_code == 403


# ---- linking a portal account -------------------------------------------------------------------------------------------------
def make_unlinked_student():
    from apps.accounts.forms import StudentRegistrationForm

    form = StudentRegistrationForm({"full_name": "Sam Lee", "email": "sam@uni.edu", "date_of_birth": "05/05/1999", "phone": "1",
                                    "student_id": "STU-777", "password1": "Str0ng-Passw0rd!", "password2": "Str0ng-Passw0rd!"})
    assert form.is_valid(), form.errors
    return form.save()


def test_front_desk_links_an_account_only_when_the_date_of_birth_matches(as_role):
    make_unlinked_student()
    desk = as_role("receptionist")
    p = Patient.objects.create(first_name="Sam", last_name="Lee", date_of_birth="1999-05-05", phone="1", address="x")
    wrong = Patient.objects.create(first_name="Sam", last_name="Li", date_of_birth="1990-01-01", phone="2", address="x")
    desk.post(reverse("patient_link_account", args=[wrong.pk]), {"student_id": "STU-777"})
    wrong.refresh_from_db()
    assert wrong.user is None                                                # date of birth differs
    desk.post(reverse("patient_link_account", args=[p.pk]), {"student_id": "stu-777"})
    p.refresh_from_db()
    assert p.user.username == "sam@uni.edu"
    assert AuditEntry.objects.filter(patient=p, text__startswith="linked the student portal account").exists()
    desk.post(reverse("patient_link_account", args=[wrong.pk]), {"student_id": "STU-777"})   # already used
    wrong.refresh_from_db()
    assert wrong.user is None


def test_unlinking_removes_the_students_access(as_role):
    student, desk = as_role("student"), as_role("receptionist")
    p = hughes()
    desk.post(reverse("patient_unlink_account", args=[p.pk]))
    assert "isn't linked to a clinic record" in student.get(reverse("portal_profile")).content.decode()


def test_students_cannot_link_accounts(as_role):
    assert as_role("student").post(reverse("patient_link_account", args=[hughes().pk]), {"student_id": "STU-984-219"}).status_code == 403


# ---- the summary the doctor writes for the patient ----------------------------------------------------------------------------------
def test_the_physician_can_write_a_patient_summary_and_it_appears_in_the_portal(as_role):
    from apps.history.models import Visit

    doctor, student = as_role("physician"), as_role("student")
    v = Visit.objects.get(patient=hughes(), status="with_doctor")
    notes = {"subjective": "s", "objective": "o", "assessment": "Primary Diagnosis: Common Cold, viral.", "plan": "p",
             "patient_summary": "You have a common cold. Rest, drink fluids and come back if it gets worse.", "action": "complete"}
    doctor.post(reverse("consultation_save", args=[v.pk]), notes)
    html = student.get(reverse("portal_profile")).content.decode()
    assert "You have a common cold. Rest, drink fluids" in html and "Common Cold" in html
    assert "Primary Diagnosis" not in html


def test_a_visit_without_a_summary_shows_a_polite_fallback_and_no_clinical_notes(as_role):
    from apps.history.models import Consultation

    Consultation.objects.filter(visit__patient=hughes()).update(patient_summary="")
    html = unescape(as_role("student").get(reverse("portal_profile")).content.decode())
    assert "didn't add a summary" in html and "Mild epigastric tenderness" not in html
