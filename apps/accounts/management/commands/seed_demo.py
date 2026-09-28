from datetime import date, time, timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.accounts.models import Profile
from apps.audit.models import AuditEntry
from apps.audit.services import log
import hashlib

from apps.history.models import Attachment, Consultation, Visit
from apps.history.sample_pdf import make_pdf
from apps.patients.models import Patient
from apps.triage.models import Triage

import os

# Local default only. On a hosted demo set DEMO_PASSWORD as a secret so the password is not in the code.
PASSWORD = os.environ.get("DEMO_PASSWORD") or "CareBoard-Demo1!"

# email, first, last, group, role, extras
DEMO = [
    ("admin@careboard.demo", "System", "Administrator", "Administrator", None, {}),
    ("dr.henderson@careboard.demo", "Clara", "Henderson", "ClinicStaff", "physician",
     {"employee_id": "DOC-10001", "department": "Internal Medicine"}),
    ("nurse.reyes@careboard.demo", "Maria", "Reyes", "ClinicStaff", "nurse",
     {"employee_id": "NUR-10002", "department": "Triage"}),
    ("sarah.cole@careboard.demo", "Sarah", "Cole", "ClinicStaff", "receptionist",
     {"employee_id": "REC-10003", "department": "Front Desk"}),
    ("student@careboard.demo", "Elizabeth", "Hughes", "Student", "student",
     {"student_id": "STU-984-219", "date_of_birth": date(1988, 10, 14), "phone": "+1 (555) 019-2831"}),
]


# code, first, last, dob, minutes since registered, status, urgent
DEMO_PATIENTS = [
    ("PAT-810-A", "David", "Miller", date(1978, 5, 12), 5, "in_triage", True),
    ("PAT-984-219", "Elizabeth", "Hughes", date(1988, 10, 14), 40, "with_doctor", False),
    ("PAT-105-D", "Gabriel", "Marcus", date(1991, 1, 22), 15, "in_triage", False),
    ("PAT-304-X", "Sophia", "Reynolds", date(1995, 7, 5), 22, "registered", False),
    ("PAT-771-B", "Marcus", "Webb", date(1984, 3, 2), 200, "completed", False),
    ("PAT-411-V", "Thomas", "Vance", date(1974, 2, 18), 30, "with_doctor", False),
    ("PAT-552-C", "Olivia", "Grant", date(1999, 11, 30), 170, "completed", False),
]

# Older patients so the directory has history: code, first, last, dob, phone, last visit, active
ARCHIVE = [
    ("PAT-009-K", "Maria", "Cruz", date(1991, 11, 23), "+1 (555) 881-2294", date(2025, 7, 19), False),
    ("PAT-301-A", "Juan", "Dela Cruz", date(1985, 8, 9), "+1 (555) 443-8101", date(2025, 6, 30), True),
]


class Command(BaseCommand):
    help = "Create demo accounts for every role (development only). Safe to re-run."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", help="Allow running with DEBUG off.")
        parser.add_argument("--if-empty", action="store_true", help="Do nothing if the database already has accounts (safe to run on every start).")

    def handle(self, *args, **options):
        User = get_user_model()
        if options.get("if_empty") and User.objects.exists():
            return
        if not settings.DEBUG and not options["force"]:
            raise CommandError("Demo accounts have a public password. Refusing to run with DEBUG off (use --force).")
        call_command("seed_roles", verbosity=0)
        User = get_user_model()
        for email, first, last, group, role, extra in DEMO:
            user, _ = User.objects.get_or_create(username=email, defaults={"email": email})
            user.email, user.first_name, user.last_name, user.is_active = email, first, last, True
            if group == "Administrator":
                user.is_staff = user.is_superuser = True
            user.set_password(PASSWORD)
            user.save()
            user.groups.set([Group.objects.get(name=group)])
            if role:
                Profile.objects.update_or_create(user=user, defaults={"role": role, **extra})
                if role != "student":
                    Profile.objects.filter(user=user).update(shift_start=time(8, 0), shift_end=time(16, 0))
        self.seed_people(User)
        self.seed_patients(User)
        self.stdout.write(self.style.SUCCESS("Demo accounts ready (password for all: %s)" % PASSWORD))
        for email, first, last, group, role, _ in DEMO:
            self.stdout.write(f"  {role or 'administrator':<13} {email}")

    def seed_patients(self, User):
        """A realistic queue so the dashboard has something to show. Re-running refreshes the waiting times."""
        now = timezone.now()
        codes = [row[0] for row in DEMO_PATIENTS] + [row[0] for row in ARCHIVE]
        # Keep the patients (and so their ID numbers and links) stable between runs; only rebuild their visits.
        Visit.objects.filter(patient__code__in=codes).delete()
        Attachment.objects.filter(patient__code__in=codes).delete()
        AuditEntry.objects.filter(user__username__endswith="@careboard.demo").delete()
        nurse = User.objects.get(username="nurse.reyes@careboard.demo")
        doctor = User.objects.get(username="dr.henderson@careboard.demo")
        desk = User.objects.get(username="sarah.cole@careboard.demo")
        by_name = {}
        for code, first, last, dob, mins, status, urgent in DEMO_PATIENTS:
            patient, _ = Patient.objects.update_or_create(
                code=code,
                defaults=dict(first_name=first, last_name=last, date_of_birth=dob, phone="+1 (555) 019-2831",
                              address="842 Hilltop Dr, Apt 4C", blood_type="A+", created_by=desk,
                              allergies={"Hughes": "Penicillin, Tree Nuts", "Reynolds": ""}.get(last, "NKDA")),
            )
            if last == "Hughes":
                patient.user = User.objects.get(username="student@careboard.demo")  # the demo student sees this record in the portal
                patient.sex, patient.civil_status = "female", "Married"
                patient.emergency_contact_name, patient.emergency_relationship = "Robert Hughes", "Spouse"
                patient.emergency_phone = "+1 (555) 919-4820"
                patient.save()
            by_name[first] = patient
            registered = now - timedelta(minutes=mins)
            visit = Visit.objects.create(patient=patient, status=status, priority="urgent" if urgent else "normal", registered_at=registered, created_by=desk)
            if status != "registered":
                visit.triage_started_at = registered + timedelta(minutes=min(mins - 1, 12 if status == "completed" else mins - 1))
            if status in ("with_doctor", "completed"):
                visit.consultation_started_at = now - timedelta(minutes=12 if status == "with_doctor" else mins - 30)
                Triage.objects.create(
                    visit=visit, temperature_c="36.8", systolic=118, diastolic=74, pulse=72, weight_kg="62.0", height_cm=168, oxygen_sat=99, respiratory_rate=16, pain_score=2, identity_verified=True,
                    chief_complaint="Mild, dry cough for 3 days. No fever.", recorded_by=nurse,
                )
            if status == "completed":
                visit.completed_at = now - timedelta(minutes=mins - 90)
            visit.save()
        # One visit yesterday, so "vs yesterday" has something to compare with.
        old = Visit.objects.create(patient=by_name["Olivia"], status="completed", registered_at=now - timedelta(days=1, hours=2), created_by=desk)
        old.triage_started_at = old.registered_at + timedelta(minutes=16)
        old.completed_at = old.registered_at + timedelta(minutes=60)
        old.save()
        for code, first, last, dob, phone, last_visit, active in ARCHIVE:
            patient, _ = Patient.objects.update_or_create(
                code=code, defaults=dict(first_name=first, last_name=last, date_of_birth=dob, phone=phone,
                                         address="12 Archive Way", is_active=active, created_by=desk))
            when = timezone.make_aware(timezone.datetime(last_visit.year, last_visit.month, last_visit.day, 10, 0))
            Visit.objects.create(patient=patient, status="completed", registered_at=when, triage_started_at=when + timedelta(minutes=10),
                                 completed_at=when + timedelta(minutes=50), created_by=desk)
        self.seed_thomas_history(by_name["Thomas"], doctor, nurse, desk)
        self.seed_hughes_history(by_name["Elizabeth"], doctor, nurse, desk)
        admin = User.objects.get(username="admin@careboard.demo")
        log(doctor, "SIGN_IN", "signed in", ip="192.168.1.104")
        log(admin, "SIGN_IN", "signed in", ip="192.168.1.101")
        log(desk, "CREATED", "registered new patient Sophia Reynolds", by_name["Sophia"], ip="192.168.1.101")
        log(nurse, "MODIFIED", "recorded vital pre-checks for Elizabeth Hughes", by_name["Elizabeth"], ip="192.168.1.112")
        log(doctor, "AUTHORIZED", "opened the record of David Miller", by_name["David"], ip="192.168.1.104")
        log(doctor, "MODIFIED", "updated medical records for Elizabeth Hughes", by_name["Elizabeth"], ip="192.168.1.104")
        log(admin, "MODIFIED", "created the nurse account of Sarah Jenkins", ip="192.168.1.101")
        log(None, "SYSTEM", "student account created for Student Jenkins (self-service registration)")

    def seed_thomas_history(self, patient, doctor, nurse, desk):
        """Past completed visits with notes, so the record view has a timeline."""
        patient.sex, patient.civil_status = "male", "Married"
        patient.save()
        current = patient.visits.get()
        Triage.objects.filter(visit=current).update(temperature_c="37.2", systolic=128, diastolic=82, pulse=72, oxygen_sat=98, respiratory_rate=16,
                                                     chief_complaint="Persistent dry cough for 4 days, worse at night.")
        past = [
            ((2025, 6, 14), "Primary Diagnosis: Seasonal Allergies, mild.", "Sneezing, itchy eyes for two weeks.", "Clear lungs, mild nasal congestion.", "Antihistamine daily; avoid triggers."),
            ((2025, 1, 10), "Primary Diagnosis: Routine Physical Exam, no concerns.", "Annual check-up, no complaints.", "All vitals within normal limits.", "Continue current lifestyle; return in 12 months."),
            ((2024, 8, 4), "Primary Diagnosis: Acute Sinusitis, bacterial.", "Facial pressure and congestion for 8 days.", "Tender maxillary sinuses.", "Course of antibiotics; rest and fluids."),
        ]
        for (y, m, d), assessment, subj, obj, plan in past:
            when = timezone.make_aware(timezone.datetime(y, m, d, 9, 30))
            visit = Visit.objects.create(patient=patient, status="completed", registered_at=when, triage_started_at=when + timedelta(minutes=8),
                                         completed_at=when + timedelta(minutes=45), created_by=desk)
            Triage.objects.create(visit=visit, temperature_c="36.8", systolic=124, diastolic=80, pulse=70, weight_kg="82.0", identity_verified=True,
                                  chief_complaint=subj, recorded_by=nurse)
            note = Consultation.objects.create(visit=visit, subjective=subj, objective=obj, assessment=assessment, plan=plan, doctor=doctor)
            Consultation.objects.filter(pk=note.pk).update(completed_at=visit.completed_at)
        draft = Consultation.objects.create(
            visit=current, doctor=doctor,
            subjective="Patient complains of persistent non-productive dry cough for 4 days, worsening at night. Accompanied by mild chest tightness and slight shortness of breath when climbing stairs.",
            objective="Chest auscultation reveals mild bilateral expiratory wheezing. No rales or rhonchi. Throat is slightly erythematous, no exudates.",
        )

    def _attach(self, patient, uploader, title, lines, *, category, source, review, description, visible=True, note=""):
        data = make_pdf(title, lines)
        return Attachment.objects.create(
            patient=patient, category=category, description=description, filename=title.lower().replace(" ", "-") + ".pdf", size=len(data),
            sha256=hashlib.sha256(data).hexdigest(), content=data, source=source, review_status=review, uploaded_by=uploader,
            visible_to_patient=visible, review_note=note,
        )

    def seed_hughes_history(self, patient, doctor, nurse, desk):
        """Past visits with plain-language summaries, and two sample PDFs, for the student portal."""
        student = patient.user
        past = [
            ((2025, 10, 14), "Primary Diagnosis: Follow-up Hypertension Management.", "Blood pressure follow-up.", "BP 120/80, stable.",
             "Continue current plan; review in 3 months.",
             "Student reports adherence to therapeutic guidelines. Blood pressure readings remain stable within target parameters. Routine 3-month review."),
            ((2025, 6, 2), "Primary Diagnosis: Acute Gastritis Flare-up.", "Episodic epigastric pain.", "Mild epigastric tenderness.",
             "Trial of antacids; dietary counselling.",
             "Evaluated for episodic epigastric distress. Prescribed a trial course of antacids and gave nutritional counselling."),
            ((2025, 3, 11), "Primary Diagnosis: Influenza Type A.", "Fever, cough, body aches.", "Febrile, clear chest.",
             "Supportive care and rest.",
             "Showed typical flu symptoms. Supportive care was given and full recovery was confirmed."),
        ]
        for (y, m, d), assessment, subj, obj, plan, summary in past:
            when = timezone.make_aware(timezone.datetime(y, m, d, 10, 0))
            visit = Visit.objects.create(patient=patient, status="completed", registered_at=when, triage_started_at=when + timedelta(minutes=8),
                                         completed_at=when + timedelta(minutes=45), created_by=desk)
            Triage.objects.create(visit=visit, temperature_c="36.9", systolic=120, diastolic=80, pulse=72, weight_kg="63.0", height_cm=168,
                                  chief_complaint=subj, identity_verified=True, recorded_by=nurse)
            note = Consultation.objects.create(visit=visit, subjective=subj, objective=obj, assessment=assessment, plan=plan,
                                               patient_summary=summary, doctor=doctor)
            Consultation.objects.filter(pk=note.pk).update(completed_at=visit.completed_at)
        self._attach(patient, nurse, "Blood Count Report", ["Patient: Elizabeth Hughes", "Hemoglobin 13.8 g/dL", "Platelets 220,000 /uL", "All within reference range."],
                     category="lab", source="clinic", review="accepted", description="Complete blood count, Sept 2026")
        self._attach(patient, student, "Outside Clinic Letter", ["Sample letter sent by the student", "Awaiting review by the clinic."],
                     category="outside", source="patient", review="pending", description="Letter from my previous doctor")

    def seed_people(self, User):
        """Realistic last-login times, an administrator profile, and staff/student requests waiting for the admin."""
        now = timezone.now()
        admin = User.objects.get(username="admin@careboard.demo")
        Profile.objects.update_or_create(user=admin, defaults={"role": "administrator"})
        for email, when in (("dr.henderson@careboard.demo", now - timedelta(minutes=45)), ("nurse.reyes@careboard.demo", now - timedelta(days=1, hours=2)),
                            ("sarah.cole@careboard.demo", now - timedelta(hours=5)), ("admin@careboard.demo", now - timedelta(minutes=5))):
            User.objects.filter(username=email).update(last_login=when)
        User.objects.filter(username="student@careboard.demo").update(last_login=now - timedelta(days=3))
        staff_group = Group.objects.get(name="ClinicStaff")
        for email, first, last, role, dept, emp in (("aris.thorne@careboard.demo", "Aris", "Thorne", "physician", "Emergency Medicine Dept.", "DOC-20001"),
                                                     ("sarah.jenkins@careboard.demo", "Sarah", "Jenkins", "nurse", "Pediatric Clinical Rotation", "NUR-20002")):
            user, _ = User.objects.get_or_create(username=email, defaults={"email": email})
            user.email, user.first_name, user.last_name, user.is_active, user.last_login = email, first, last, False, None
            user.set_password(PASSWORD)
            user.save()
            user.groups.set([staff_group])
            Profile.objects.update_or_create(user=user, defaults={"role": role, "department": dept, "employee_id": emp, "reviewed_at": None,
                                                                  "reviewed_by": None, "denied_at": None})
        # a student who registered but has not been linked to a clinic record yet
        user, _ = User.objects.get_or_create(username="s.jenkins@careboard.demo", defaults={"email": "s.jenkins@careboard.demo"})
        user.email, user.first_name, user.last_name, user.is_active, user.last_login = "s.jenkins@careboard.demo", "Student", "Jenkins", True, None
        user.set_password(PASSWORD)
        user.save()
        user.groups.set([Group.objects.get(name="Student")])
        Profile.objects.update_or_create(user=user, defaults={"role": "student", "student_id": "STU-555-001", "date_of_birth": date(2004, 3, 3), "phone": "+1 (555) 000-1234"})
