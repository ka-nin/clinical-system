from .dev import *  # noqa

# Tests sign in with client.login(), which has no request, so the lockout backend is off by default.
# The lockout tests switch it back on with override_settings.
AXES_ENABLED = False
AUTHENTICATION_BACKENDS = ["apps.accounts.backends.CaseInsensitiveBackend"]
MIDDLEWARE = [m for m in MIDDLEWARE if not m.startswith("axes.")]
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]  # faster tests only
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
