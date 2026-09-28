import hashlib

from django.conf import settings
from django.db import models, transaction
from django.utils import timezone


class AuditEntry(models.Model):
    """Who did what, and when. Entries can be added but never changed or deleted."""

    class Kind(models.TextChoices):
        CREATED = "CREATED", "Created"
        MODIFIED = "MODIFIED", "Modified"
        AUTHORIZED = "AUTHORIZED", "Authorized"
        SYSTEM = "SYSTEM", "System"
        SIGN_IN = "SIGN_IN", "Sign in"
        SIGN_IN_FAILED = "SIGN_IN_FAILED", "Failed sign-in"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="audit_entries")
    kind = models.CharField(max_length=16, choices=Kind.choices)
    text = models.CharField(max_length=255, help_text="What was done, without the person's name, e.g. 'registered new patient X'.")
    patient = models.ForeignKey("patients.Patient", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(default=timezone.now, db_index=True, editable=False)
    ip_address = models.GenericIPAddressField(null=True, blank=True, editable=False)
    prev_hash = models.CharField(max_length=64, blank=True, editable=False)
    entry_hash = models.CharField(max_length=64, blank=True, editable=False)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "audit entries"

    def __str__(self):
        return f"{self.created_at:%Y-%m-%d %H:%M} {self.user} {self.text}"

    def compute_hash(self):
        """A fingerprint of this entry and the one before it, so later changes or gaps can be detected."""
        payload = "|".join([
            self.prev_hash, str(self.user_id or ""), self.kind, self.text, str(self.patient_id or ""), self.created_at.isoformat(),
        ])
        if self.ip_address:  # only when present, so entries written before the address existed still verify
            payload += "|" + self.ip_address
        return hashlib.sha256(payload.encode()).hexdigest()

    def save(self, *args, **kwargs):
        if self.pk:
            raise PermissionError("Audit entries cannot be edited.")
        with transaction.atomic():
            last = AuditEntry.objects.select_for_update().order_by("-id").first()
            from .context import current_ip

            self.ip_address = self.ip_address or current_ip()
            self.prev_hash = last.entry_hash if last else ""
            self.created_at = timezone.now()
            self.entry_hash = self.compute_hash()
            super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionError("Audit entries cannot be deleted.")
