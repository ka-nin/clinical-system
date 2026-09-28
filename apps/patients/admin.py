from django.contrib import admin

from .models import Patient, PatientChange


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ("code", "last_name", "first_name", "date_of_birth", "phone", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("code", "first_name", "last_name", "phone")


@admin.register(PatientChange)
class PatientChangeAdmin(admin.ModelAdmin):
    """The history of edited details. Read-only."""

    list_display = ("patient", "label", "old_value", "new_value", "changed_by", "changed_at")
    search_fields = ("patient__first_name", "patient__last_name", "patient__code")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
