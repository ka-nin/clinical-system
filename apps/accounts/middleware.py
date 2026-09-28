from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse

from .dashboard import ADMINISTRATOR, in_group
from .forms import CLINIC_STAFF


def needs_two_factor(user):
    """Staff and administrators must use an authenticator app when REQUIRE_2FA is on."""
    return user.is_superuser or in_group(user, CLINIC_STAFF) or in_group(user, ADMINISTRATOR)


class RequireTwoFactorMiddleware:
    """Sends staff without a confirmed authenticator to set one up before they can use the system."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if settings.REQUIRE_2FA and user is not None and user.is_authenticated and needs_two_factor(user):
            allowed = (reverse("security_2fa"), reverse("logout"), settings.STATIC_URL)
            if not request.path.startswith(allowed):
                device = getattr(user, "two_factor", None)
                if device is None or not device.is_confirmed:
                    return redirect("security_2fa")
        return self.get_response(request)
