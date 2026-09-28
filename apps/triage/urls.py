from django.urls import path

from . import views

urlpatterns = [
    path("", views.triage_queue, name="triage_queue"),
    path("list/", views.triage_queue_fragment, name="triage_queue_fragment"),
    path("<int:pk>/start/", views.triage_start, name="triage_start"),
    path("<int:pk>/takeover/", views.triage_takeover, name="triage_takeover"),
    path("<int:pk>/assess/", views.triage_assess, name="triage_assess"),
    path("<int:pk>/amend/", views.triage_amend, name="triage_amend"),
    path("<int:pk>/", views.triage_form, name="triage_form"),
]
