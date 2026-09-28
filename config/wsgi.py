import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.prod")
application = get_wsgi_application()

if os.environ.get("AUTO_SETUP") == "1":
    from apps.accounts.bootstrap import prepare_database

    prepare_database()

app = application  # the name Wasmer Edge looks for
