from django.urls import path

from . import manage_views as manage
from . import portal, views

urlpatterns = [
    path("dashboard/", views.dashboard, name="dashboard"),
    path("dashboard/live/", views.dashboard_live, name="dashboard_live"),
    path("login/verify/", views.login_verify, name="login_verify"),
    path("account/security/", views.security_2fa, name="security_2fa"),
    path("portal/", portal.portal_profile, name="portal_profile"),
    path("portal/records/", portal.portal_records, name="portal_records"),
    path("portal/records/upload/", portal.portal_upload, name="portal_upload"),
    path("portal/visits/", portal.portal_visits, name="portal_visits"),
    path("manage/", manage.manage_dashboard, name="manage_dashboard"),
    path("manage/users/", manage.manage_users, name="manage_users"),
    path("manage/users/new/", manage.manage_user_new, name="manage_user_new"),
    path("manage/users/<int:pk>/", manage.manage_user_edit, name="manage_user_edit"),
    path("manage/users/<int:pk>/action/", manage.manage_user_action, name="manage_user_action"),
    path("manage/logs/", manage.manage_logs, name="manage_logs"),
    path("manage/logs/verify/", manage.manage_logs_verify, name="manage_logs_verify"),
    path("register/student/", views.StudentRegisterView.as_view(), name="register_student"),
    path("register/staff/", views.StaffRegisterView.as_view(), name="register_staff"),
]
