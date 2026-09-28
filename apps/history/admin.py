from django.contrib import admin

from .models import Attachment, Consultation, LabResult, Prescription, Visit


@admin.register(Visit)
class VisitAdmin(admin.ModelAdmin):
    list_display = ("patient", "status", "priority", "registered_at")
    list_filter = ("status", "priority")


@admin.register(Consultation)
class ConsultationAdmin(admin.ModelAdmin):
    list_display = ("visit", "doctor", "updated_at", "completed_at")
    readonly_fields = ("visit", "doctor", "completed_at")


@admin.register(Prescription)
class PrescriptionAdmin(admin.ModelAdmin):
    list_display = ("medication", "dose", "visit", "prescribed_by", "created_at")


@admin.register(LabResult)
class LabResultAdmin(admin.ModelAdmin):
    list_display = ("test_name", "value", "flag", "patient", "resulted_at")
    list_filter = ("flag",)


@admin.register(Attachment)
class AttachmentAdmin(admin.ModelAdmin):
    """Metadata only: the file bytes are never loaded or shown here."""

    list_display = ("filename", "patient", "category", "source", "review_status", "size", "uploaded_at", "withdrawn_at")
    list_filter = ("source", "review_status", "category")
    exclude = ("content",)
    readonly_fields = ("patient", "visit", "filename", "size", "sha256", "uploaded_by", "uploaded_at")

    def get_queryset(self, request):
        return super().get_queryset(request).defer("content")

    def has_add_permission(self, request):
        return False
