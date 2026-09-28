from django.contrib.auth import get_user_model
from django.contrib.auth.signals import user_logged_in, user_login_failed
from django.dispatch import receiver

from .models import AuditEntry
from .services import log


@receiver(user_logged_in)
def record_sign_in(sender, request, user, **kwargs):
    log(user, AuditEntry.Kind.SIGN_IN, "signed in")


@receiver(user_login_failed)
def record_failed_sign_in(sender, credentials, request=None, **kwargs):
    """Note the failure without ever storing what was typed (people sometimes type a password into the email box)."""
    typed = (credentials or {}).get("username") or ""
    User = get_user_model()
    user = User.objects.filter(username__iexact=typed).first() if typed else None
    log(user, AuditEntry.Kind.SIGN_IN_FAILED, f"failed sign-in for {user.get_username()}" if user else "failed sign-in for an unknown account")
