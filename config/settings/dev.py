import os

from .base import *  # noqa

DEBUG = True
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY") or "dev-only-insecure-key-do-not-use-in-production"
ALLOWED_HOSTS = ["*"]
STORAGES["staticfiles"] = {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"  # emails print in the terminal
