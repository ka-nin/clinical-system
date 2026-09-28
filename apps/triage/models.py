from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Triage(models.Model):
    """Vitals and the reason for the visit, attached to that visit. Recorded once, never edited."""

    visit = models.OneToOneField("history.Visit", on_delete=models.CASCADE, related_name="triage")
    temperature_c = models.DecimalField("Temperature (°C)", max_digits=4, decimal_places=1,
                                        validators=[MinValueValidator(30), MaxValueValidator(45)])
    systolic = models.PositiveSmallIntegerField("Systolic (mmHg)", validators=[MinValueValidator(50), MaxValueValidator(260)])
    diastolic = models.PositiveSmallIntegerField("Diastolic (mmHg)", validators=[MinValueValidator(30), MaxValueValidator(160)])
    pulse = models.PositiveSmallIntegerField("Pulse (bpm)", validators=[MinValueValidator(20), MaxValueValidator(250)])
    weight_kg = models.DecimalField("Weight (kg)", max_digits=5, decimal_places=1,
                                    validators=[MinValueValidator(1), MaxValueValidator(500)])
    height_cm = models.PositiveSmallIntegerField("Height (cm)", null=True, blank=True,
                                                 validators=[MinValueValidator(30), MaxValueValidator(250)])
    oxygen_sat = models.PositiveSmallIntegerField("Oxygen saturation (%)", null=True, blank=True,
                                                  validators=[MinValueValidator(50), MaxValueValidator(100)])
    respiratory_rate = models.PositiveSmallIntegerField("Respiratory rate (breaths/min)", null=True, blank=True,
                                                        validators=[MinValueValidator(4), MaxValueValidator(80)])
    pain_score = models.PositiveSmallIntegerField("Pain score (0-10)", null=True, blank=True,
                                                  validators=[MinValueValidator(0), MaxValueValidator(10)])
    chief_complaint = models.TextField("Chief complaint")
    identity_verified = models.BooleanField(default=False, help_text="Name and date of birth were checked with the patient.")
    suggested_priority = models.CharField(max_length=10, blank=True, help_text="What the vitals suggested when this was saved.")
    override_reason = models.CharField(max_length=255, blank=True, help_text="Why a lower priority than suggested was chosen.")
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    recorded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Triage for {self.visit}"

    @property
    def blood_pressure(self):
        return f"{self.systolic} / {self.diastolic}"


class TriageAmendment(models.Model):
    """A correction to a recorded vital. The original value is kept here forever."""

    triage = models.ForeignKey(Triage, on_delete=models.CASCADE, related_name="amendments")
    field = models.CharField(max_length=40)
    label = models.CharField(max_length=60)
    old_value = models.CharField(max_length=60, blank=True)
    new_value = models.CharField(max_length=60, blank=True)
    reason = models.CharField(max_length=255)
    amended_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    amended_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["amended_at"]

    def __str__(self):
        return f"{self.label}: {self.old_value} -> {self.new_value} ({self.reason})"
