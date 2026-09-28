from datetime import date

from django.conf import settings
from django.db import models


class Patient(models.Model):
    """Identity and demographics. One record per person, reused for every visit."""

    BLOOD_TYPES = [
        (b, f"{b[:-1]}-{'Positive' if b.endswith('+') else 'Negative'}")
        for b in ("A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-")
    ]
    SEXES = [("female", "Female"), ("male", "Male")]
    CIVIL_STATUSES = [(c, c) for c in ("Single", "Married", "Widowed", "Divorced", "Separated")]

    code = models.CharField(max_length=20, unique=True, null=True, blank=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    date_of_birth = models.DateField()
    phone = models.CharField(max_length=30)
    email = models.EmailField(blank=True)
    address = models.CharField(max_length=255)
    sex = models.CharField("biological sex", max_length=10, choices=SEXES, blank=True)
    civil_status = models.CharField(max_length=12, choices=CIVIL_STATUSES, blank=True)
    blood_type = models.CharField(max_length=3, choices=BLOOD_TYPES, blank=True)
    emergency_contact_name = models.CharField(max_length=150, blank=True)
    emergency_relationship = models.CharField(max_length=60, blank=True)
    emergency_phone = models.CharField(max_length=30, blank=True)
    allergies = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField("active", default=True, help_text="Inactive patients stay in the archive; nothing is deleted.")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="patient_record",
                                help_text="The student portal account that may see this record. Linked by clinic staff after checking ID.")

    class Meta:
        ordering = ["last_name", "first_name"]

    def __str__(self):
        return f"{self.full_name} ({self.code})"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.code:
            self.code = f"PAT-{self.pk:05d}"
            super().save(update_fields=["code"])

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    NO_ALLERGY_WORDS = {"none", "nkda", "nka", "no known allergies", "none known", "no known drug allergies", "n/a", "na", "nil", "no"}

    @property
    def allergy_status(self):
        """'unknown' (never asked), 'none' (asked, none) or 'listed'."""
        text = (self.allergies or "").strip().lower().rstrip(".")
        if not text:
            return "unknown"
        return "none" if text in self.NO_ALLERGY_WORDS else "listed"

    @property
    def blood_type_short(self):
        """'A+' -> 'A-Pos', for compact headers."""
        if not self.blood_type:
            return ""
        return self.blood_type[:-1] + ("-Pos" if self.blood_type.endswith("+") else "-Neg")

    @property
    def short_code(self):
        return (self.code or "").removeprefix("PAT-")

    @property
    def initials(self):
        return f"{self.first_name[:1]}{self.last_name[:1]}".upper()

    @property
    def age(self):
        today = date.today()
        dob = self.date_of_birth
        return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


class PatientChange(models.Model):
    """One changed detail on a patient, kept forever. Details are updated, never silently overwritten."""

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="changes")
    field = models.CharField(max_length=60)
    label = models.CharField(max_length=80)
    old_value = models.CharField(max_length=255, blank=True)
    new_value = models.CharField(max_length=255, blank=True)
    reason = models.CharField(max_length=255, blank=True)
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-changed_at"]

    def __str__(self):
        return f"{self.patient}: {self.label} {self.old_value!r} -> {self.new_value!r}"
