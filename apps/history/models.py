from django.conf import settings
from django.db import models
from django.utils import timezone


class VisitQuerySet(models.QuerySet):
    def active(self):
        return self.filter(status__in=Visit.ACTIVE)

    def waiting(self):
        return self.filter(status__in=Visit.WAITING)


class Visit(models.Model):
    """One trip to the clinic. New visits are added to a patient; nothing is overwritten."""

    class Status(models.TextChoices):
        REGISTERED = "registered", "Registered"
        IN_TRIAGE = "in_triage", "In Triage"
        WITH_DOCTOR = "with_doctor", "With Doctor"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"
        LEFT = "left", "Left Without Being Seen"

    class Priority(models.TextChoices):
        # Stored values sort alphabetically as normal < priority < urgent, so "-priority" puts urgent first.
        NORMAL = "normal", "Normal Level"
        PRIORITY = "priority", "Priority Level"
        URGENT = "urgent", "Urgent Level"

    CLOSE_OUTCOMES = [("cancelled", "Cancel this visit (registered by mistake)"), ("left", "Patient left without being seen")]

    ACTIVE = [Status.REGISTERED, Status.IN_TRIAGE, Status.WITH_DOCTOR]
    WAITING = [Status.REGISTERED, Status.IN_TRIAGE]
    STAGES = {
        Status.REGISTERED: "Reception",
        Status.IN_TRIAGE: "Triage pre-check",
        Status.WITH_DOCTOR: "Consultation",
        Status.COMPLETED: "Completed",
        Status.CANCELLED: "Cancelled",
        Status.LEFT: "Left",
    }

    patient = models.ForeignKey("patients.Patient", on_delete=models.CASCADE, related_name="visits")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.REGISTERED, db_index=True)
    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.NORMAL)
    registered_at = models.DateTimeField(default=timezone.now, db_index=True)
    triage_started_at = models.DateTimeField(null=True, blank=True)
    consultation_started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    triage_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
                                  help_text="The person currently doing this pre-check.")
    closed_reason = models.CharField(max_length=255, blank=True)
    closed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")

    objects = VisitQuerySet.as_manager()

    class Meta:
        ordering = ["-registered_at"]

    def __str__(self):
        return f"{self.patient.full_name} — {self.get_status_display()}"

    @property
    def stage(self):
        return self.STAGES[self.status]

    def minutes_since(self, moment):
        return max(0, int((timezone.now() - moment).total_seconds() // 60))


class Consultation(models.Model):
    """The doctor's SOAP note for a visit. Editable as a draft; frozen once the visit is completed."""

    visit = models.OneToOneField(Visit, on_delete=models.CASCADE, related_name="consultation")
    subjective = models.TextField(blank=True)
    objective = models.TextField(blank=True)
    assessment = models.TextField(blank=True)
    plan = models.TextField(blank=True)
    patient_summary = models.TextField(blank=True, help_text="Plain-language summary the patient sees in their portal. Optional.")
    doctor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    SECTIONS = ("subjective", "objective", "assessment", "plan")

    def __str__(self):
        return f"Consultation for {self.visit}"

    @property
    def is_completed(self):
        return self.completed_at is not None

    @property
    def title(self):
        """A short heading for the timeline, taken from the first line of the assessment."""
        import re

        lines = self.assessment.strip().splitlines()
        text = re.sub(r"^(primary\s+)?diagnosis\s*:\s*", "", lines[0].strip(), flags=re.I) if lines else ""
        text = re.split(r"[,.;]", text)[0].strip()
        return text[:60] or "Consultation"

    def save(self, *args, **kwargs):
        if self.pk and Consultation.objects.filter(pk=self.pk, completed_at__isnull=False).exists():
            raise PermissionError("A completed consultation cannot be edited.")
        super().save(*args, **kwargs)


class Prescription(models.Model):
    """A medication ordered during a visit. Added, never edited."""

    visit = models.ForeignKey(Visit, on_delete=models.CASCADE, related_name="prescriptions")
    medication = models.CharField(max_length=150)
    dose = models.CharField(max_length=100)
    frequency = models.CharField(max_length=100)
    duration = models.CharField(max_length=100, blank=True)
    instructions = models.CharField(max_length=255, blank=True)
    allergy_warning = models.CharField(max_length=255, blank=True, help_text="Set when the allergy check flagged this order and the doctor overrode it.")
    prescribed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.medication} {self.dose} — {self.visit}"


class LabResult(models.Model):
    """A lab result typed in by staff. Added, never edited; a correction is a new result with a comment."""

    class Flag(models.TextChoices):
        NORMAL = "normal", "Normal"
        ABNORMAL = "abnormal", "Abnormal"
        CRITICAL = "critical", "Critical"

    patient = models.ForeignKey("patients.Patient", on_delete=models.CASCADE, related_name="lab_results")
    visit = models.ForeignKey(Visit, null=True, blank=True, on_delete=models.SET_NULL, related_name="lab_results")
    test_name = models.CharField(max_length=150)
    value = models.CharField(max_length=100)
    unit = models.CharField(max_length=40, blank=True)
    reference_range = models.CharField(max_length=80, blank=True)
    flag = models.CharField(max_length=10, choices=Flag.choices, default=Flag.NORMAL)
    comment = models.CharField(max_length=255, blank=True)
    resulted_at = models.DateTimeField(default=timezone.now)
    entered_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-resulted_at"]

    def __str__(self):
        return f"{self.test_name}: {self.value} {self.unit}".strip()


class Attachment(models.Model):
    """A PDF kept with a patient's record. The file itself is stored in the database and is only ever served
    through a view that checks who is asking. Added, never edited; a mistake is withdrawn (hidden), not deleted."""

    class Category(models.TextChoices):
        LAB = "lab", "Lab report"
        IMAGING = "imaging", "Imaging report"
        REFERRAL = "referral", "Referral letter"
        CERTIFICATE = "certificate", "Medical certificate"
        OUTSIDE = "outside", "Outside medical record"
        OTHER = "other", "Other"

    class Source(models.TextChoices):
        CLINIC = "clinic", "Clinic"
        PATIENT = "patient", "Sent by the patient"

    class Review(models.TextChoices):
        ACCEPTED = "accepted", "Accepted"
        PENDING = "pending", "Awaiting review"
        REJECTED = "rejected", "Not accepted"

    patient = models.ForeignKey("patients.Patient", on_delete=models.CASCADE, related_name="attachments")
    visit = models.ForeignKey(Visit, null=True, blank=True, on_delete=models.SET_NULL, related_name="attachments")
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.OTHER)
    description = models.CharField(max_length=200, blank=True)
    filename = models.CharField(max_length=150)
    size = models.PositiveIntegerField()
    sha256 = models.CharField(max_length=64)
    content = models.BinaryField(editable=False)

    source = models.CharField(max_length=10, choices=Source.choices, default=Source.CLINIC)
    review_status = models.CharField(max_length=10, choices=Review.choices, default=Review.ACCEPTED)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.CharField(max_length=255, blank=True)
    visible_to_patient = models.BooleanField(default=True, help_text="Show this file in the patient's portal.")

    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    uploaded_at = models.DateTimeField(auto_now_add=True)
    withdrawn_at = models.DateTimeField(null=True, blank=True)
    withdrawn_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    withdrawn_reason = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self):
        return f"{self.filename} ({self.get_category_display()}) — {self.patient}"

    @property
    def is_withdrawn(self):
        return self.withdrawn_at is not None
