from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from apps.accounts.views import CareLoginView, landing

urlpatterns = [
    path("", landing, name="home"),
    path("admin/", admin.site.urls),
    path("login/", CareLoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("account/password/", auth_views.PasswordChangeView.as_view(template_name="accounts/password_change.html", success_url="/account/password/done/"), name="password_change"),
    path("account/password/done/", auth_views.PasswordChangeDoneView.as_view(template_name="accounts/password_change_done.html"), name="password_change_done"),
    path("password-reset/", auth_views.PasswordResetView.as_view(
        template_name="accounts/password_reset_form.html", email_template_name="accounts/emails/password_reset_email.txt",
        subject_template_name="accounts/emails/password_reset_subject.txt"), name="password_reset"),
    path("password-reset/sent/", auth_views.PasswordResetDoneView.as_view(template_name="accounts/password_reset_done.html"), name="password_reset_done"),
    path("password-reset/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(template_name="accounts/password_reset_confirm.html"), name="password_reset_confirm"),
    path("password-reset/complete/", auth_views.PasswordResetCompleteView.as_view(template_name="accounts/password_reset_complete.html"), name="password_reset_complete"),
    path("", include("apps.accounts.urls")),
    path("patients/", include("apps.patients.urls")),
    path("triage/", include("apps.triage.urls")),
    path("history/", include("apps.history.urls")),
    path("audit/", include("apps.audit.urls")),
]

handler403 = "apps.accounts.errors.permission_denied"
handler404 = "apps.accounts.errors.page_not_found"
handler500 = "apps.accounts.errors.server_error"
