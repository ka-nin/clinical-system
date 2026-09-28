from django.contrib import admin

from .models import Triage, TriageAmendment


@admin.register(Triage)
class TriageAdmin(admin.ModelAdmin):
    list_display = ("visit", "systolic", "diastolic", "pulse", "temperature_c", "recorded_by", "recorded_at")


@admin.register(TriageAmendment)
class TriageAmendmentAdmin(admin.ModelAdmin):
    """Corrections to recorded vitals, with the original values. Read-only."""

    list_display = ("triage", "label", "old_value", "new_value", "reason", "amended_by", "amended_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
