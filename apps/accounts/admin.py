from django.conf import settings
from django.contrib import admin, messages
from django.core.mail import send_mail

from .models import Profile


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "department", "employee_id", "student_id", "shift_label", "is_active", "created_at")
    list_filter = ("role", "user__is_active")
    search_fields = ("user__email", "user__first_name", "user__last_name", "employee_id", "student_id")
    actions = ["approve_accounts"]

    @admin.display(boolean=True, description="Active")
    def is_active(self, obj):
        return obj.user.is_active

    @admin.action(description="Approve selected accounts (allow sign-in)")
    def approve_accounts(self, request, queryset):
        count = 0
        for profile in queryset.select_related("user"):
            if not profile.user.is_active:
                profile.user.is_active = True
                profile.user.save(update_fields=["is_active"])
                count += 1
                send_mail(
                    "Your CareBoard account is approved",
                    "Hello,\n\nYour CareBoard account has been approved. You can now sign in with your email and password.\n"
                    + ("You will be asked to set up two-step sign-in with an authenticator app the first time.\n" if settings.REQUIRE_2FA else ""),
                    None, [profile.user.email], fail_silently=True,
                )
        self.message_user(request, f"Approved {count} account(s).", messages.SUCCESS)


from .models import TwoFactor  # noqa: E402


@admin.register(TwoFactor)
class TwoFactorAdmin(admin.ModelAdmin):
    """Deleting a row here resets someone's two-step sign-in (for example after they lose their phone)."""

    list_display = ("user", "confirmed_at")
    readonly_fields = ("user", "secret", "confirmed_at", "last_step", "recovery_hashes")

    def has_add_permission(self, request):
        return False
