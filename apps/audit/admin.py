from django.contrib import admin

from .models import AuditEntry


@admin.register(AuditEntry)
class AuditEntryAdmin(admin.ModelAdmin):
    """The full activity log, for administrators only. Read-only."""

    list_display = ("created_at", "user", "kind", "text")
    list_filter = ("kind", "user")
    search_fields = ("text", "user__email", "user__first_name", "user__last_name")
    date_hierarchy = "created_at"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
