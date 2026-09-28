from django.conf import settings
from django.db import models


class Profile(models.Model):
    """Extra details collected at registration. Students and staff share one table."""

    class Role(models.TextChoices):
        STUDENT = "student", "Student"
        NURSE = "nurse", "Nurse"
        RECEPTIONIST = "receptionist", "Receptionist"
        PHYSICIAN = "physician", "Physician"
        ADMINISTRATOR = "administrator", "Administrator"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    role = models.CharField(max_length=20, choices=Role.choices)
    phone = models.CharField(max_length=30, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    student_id = models.CharField(max_length=40, null=True, blank=True, unique=True)
    employee_id = models.CharField(max_length=40, null=True, blank=True, unique=True)
    department = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
                                    help_text="The administrator who approved or denied this account.")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    denied_at = models.DateTimeField(null=True, blank=True)
    shift_start = models.TimeField(null=True, blank=True)
    shift_end = models.TimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.get_username()} ({self.get_role_display()})"

    @property
    def shift_label(self):
        if not (self.shift_start and self.shift_end):
            return ""
        return f"{self.shift_start:%I:%M %p} - {self.shift_end:%I:%M %p}"


class TwoFactor(models.Model):
    """Authenticator-app (TOTP) sign-in for one account, plus one-time recovery codes."""

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="two_factor")
    secret = models.CharField(max_length=64)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    last_step = models.BigIntegerField(default=0, help_text="Last accepted 30-second time step, so a code can't be reused.")
    recovery_hashes = models.JSONField(default=list, blank=True)

    def __str__(self):
        return f"2FA for {self.user}"

    @property
    def is_confirmed(self):
        return self.confirmed_at is not None
