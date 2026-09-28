from django.urls import path

from . import views

urlpatterns = [
    path("visit/<int:pk>/notes/", views.consultation_save, name="consultation_save"),
    path("visit/<int:pk>/close/", views.visit_close, name="visit_close"),
    path("patient/<int:patient_pk>/files/upload/", views.attachment_upload, name="attachment_upload"),
    path("files/<int:pk>/review/", views.attachment_review, name="attachment_review"),
    path("files/<int:pk>/withdraw/", views.attachment_withdraw, name="attachment_withdraw"),
    path("files/<int:pk>/", views.attachment_download, name="attachment_download"),
    path("visit/<int:pk>/autosave/", views.consultation_autosave, name="consultation_autosave"),
]
