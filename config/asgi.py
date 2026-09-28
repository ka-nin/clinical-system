import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.prod")
application = get_asgi_application()

if os.environ.get("AUTO_SETUP") == "1":
    from apps.accounts.bootstrap import prepare_database

    prepare_database()

app = application  # Wasmer Edge runs this with uvicorn: uvicorn config.asgi:app
