import os
from pathlib import Path

import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# No default here on purpose: dev.py supplies a throwaway key, prod.py refuses to start without a real one.
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
DEBUG = False
ALLOWED_HOSTS = [h.strip() for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",") if h.strip()]

INSTALLED_APPS = [
    "axes",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "apps.accounts",
    "apps.patients",
    "apps.triage",
    "apps.history",
    "apps.audit",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "apps.audit.context.AuditContextMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "apps.accounts.middleware.RequireTwoFactorMiddleware",
    "axes.middleware.AxesMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.app"  # Wasmer Edge looks for a module-level `app`

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.accounts.context.shell",
                "apps.accounts.context.demo",
            ],
        },
    },
]

def _database():
    """Where the data lives, in order of preference:
    1. DATABASE_URL (any database, e.g. postgres://… or mysql://…)
    2. Wasmer Edge's own MySQL database (Wasmer sets DB_HOST, DB_PORT, DB_NAME, DB_USERNAME, DB_PASSWORD)
    3. A local SQLite file, for development on your own computer.
    """
    if os.environ.get("DATABASE_URL"):
        return dj_database_url.config(conn_max_age=60, conn_health_checks=True)
    if os.environ.get("DB_HOST") and os.environ.get("DB_NAME"):
        if os.environ.get("DB_ENGINE", "mysql") == "postgres":  # set DB_ENGINE=postgres if Wasmer gave you PostgreSQL
            return {"ENGINE": "django.db.backends.postgresql", "NAME": os.environ["DB_NAME"],
                    "USER": os.environ.get("DB_USERNAME") or os.environ.get("DB_USER", ""), "PASSWORD": os.environ.get("DB_PASSWORD", ""),
                    "HOST": os.environ["DB_HOST"], "PORT": os.environ.get("DB_PORT", "5432"), "CONN_MAX_AGE": 60}
        return {
            "ENGINE": "django.db.backends.mysql",
            "NAME": os.environ["DB_NAME"],
            "USER": os.environ.get("DB_USERNAME") or os.environ.get("DB_USER", ""),
            "PASSWORD": os.environ.get("DB_PASSWORD", ""),
            "HOST": os.environ["DB_HOST"],
            "PORT": os.environ.get("DB_PORT", "3306"),
            "CONN_MAX_AGE": 60,
            "CONN_HEALTH_CHECKS": True,
            "OPTIONS": {"charset": "utf8mb4", "init_command": "SET sql_mode='STRICT_TRANS_TABLES'"},
            "TEST": {"CHARSET": "utf8mb4", "COLLATION": "utf8mb4_unicode_ci"},
        }
    return {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}


DATABASES = {"default": _database()}

# Use the pure-Python MySQL driver when the compiled one (mysqlclient, which Wasmer provides) isn't installed.
if DATABASES["default"]["ENGINE"] == "django.db.backends.mysql":
    try:
        import MySQLdb  # noqa: F401
    except ImportError:
        import pymysql

        pymysql.version_info = (2, 2, 7, "final", 0)  # Django checks the mysqlclient version number
        pymysql.install_as_MySQLdb()

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
     "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",  # must come first: blocks locked-out sign-ins
    "apps.accounts.backends.CaseInsensitiveBackend",
]

# Lock an email + address pair for 15 minutes after 5 failed sign-ins.
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = 0.25  # hours
AXES_LOCKOUT_PARAMETERS = [["username", "ip_address"]]
AXES_RESET_ON_SUCCESS = True
AXES_LOCKOUT_TEMPLATE = "lockout.html"
AXES_ENABLED = os.environ.get("AXES_ENABLED", "1") == "1"

REQUIRE_2FA = False  # prod.py turns this on

# Set TRUST_PROXY_HEADERS=1 only when the app runs behind a proxy you control (it then reads X-Forwarded-For).
TRUST_PROXY_HEADERS = os.environ.get("TRUST_PROXY_HEADERS") == "1"

# Demo mode: for showing the system to others, never for real patients. Adds a warning banner, turns off the
# two-step sign-in requirement and email, and lets the admin hand out temporary passwords.
DEMO_MODE = os.environ.get("DEMO_MODE") == "1"
DEFAULT_FROM_EMAIL = "CareBoard <no-reply@localhost>"

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "dashboard"
LOGOUT_REDIRECT_URL = "login"
SESSION_COOKIE_AGE = 60 * 30  # 30-minute idle timeout
SESSION_SAVE_EVERY_REQUEST = True

LANGUAGE_CODE = "en-us"
TIME_ZONE = os.environ.get("DJANGO_TIME_ZONE", "UTC")
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
