from django.urls import path

from . import views

urlpatterns = [
    path("", views.patient_list, name="patient_list"),
    path("new/", views.patient_create, name="patient_create"),
    path("<int:pk>/", views.patient_detail, name="patient_detail"),
    path("<int:pk>/access/", views.patient_access, name="patient_access"),
    path("<int:pk>/edit/", views.patient_edit, name="patient_edit"),
    path("<int:pk>/portal/link/", views.patient_link_account, name="patient_link_account"),
    path("<int:pk>/portal/unlink/", views.patient_unlink_account, name="patient_unlink_account"),
]
