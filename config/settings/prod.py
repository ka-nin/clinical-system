import os

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa

DEBUG = False


def _require(condition, message):
    if not condition:
        raise ImproperlyConfigured("Refusing to start in production: " + message)


if DEMO_MODE:
    ALLOWED_HOSTS = ALLOWED_HOSTS or [".wasmer.app"]
    REQUIRE_2FA_DEFAULT = "0"
else:
    REQUIRE_2FA_DEFAULT = "1"

_require(len(SECRET_KEY) >= 40, "set DJANGO_SECRET_KEY to a long random value (at least 40 characters).")
_require(ALLOWED_HOSTS, "set DJANGO_ALLOWED_HOSTS to your domain name(s), comma-separated.")
_require(
    "sqlite" not in DATABASES["default"]["ENGINE"] or os.environ.get("ALLOW_SQLITE_IN_PRODUCTION") == "1",
    "use a real database server (Wasmer's MySQL, or DATABASE_URL). SQLite files are not safe on hosts with temporary disks.",
)

CSRF_TRUSTED_ORIGINS = [o.strip() for o in os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if o.strip()]
if DEMO_MODE and not CSRF_TRUSTED_ORIGINS:
    CSRF_TRUSTED_ORIGINS = ["https://*.wasmer.app"]

# Wasmer already serves the site over HTTPS. The redirect is on outside demo mode (or set SECURE_SSL_REDIRECT=1).
SECURE_SSL_REDIRECT = os.environ.get("SECURE_SSL_REDIRECT", "0" if DEMO_MODE else "1") == "1"
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_REFERRER_POLICY = "same-origin"
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

# Second sign-in step (authenticator app) for staff and administrators.
REQUIRE_2FA = os.environ.get("REQUIRE_2FA", REQUIRE_2FA_DEFAULT) == "1"

# Real email for password resets and account approvals.
EMAIL_HOST = os.environ.get("EMAIL_HOST", "")
if not EMAIL_HOST:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"  # no mail server: messages go to the app log instead of failing
else:
    EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
    EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
    EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
    EMAIL_USE_TLS = True
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "CareBoard <no-reply@localhost>")
