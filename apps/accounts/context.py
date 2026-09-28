from .dashboard import in_group, shell_context
from .forms import CLINIC_STAFF


def shell(request):
    """Adds `me` (name, initials, role line) and, for clinic staff, `shift` to every template."""
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {}
    context = {"me": shell_context(user)}
    profile = getattr(user, "profile", None)
    if in_group(user, CLINIC_STAFF) and profile and profile.shift_label:
        context["shift"] = profile.shift_label  # only shown when the person's shift has actually been set
    return context


def demo(request):
    from django.conf import settings

    return {"demo_mode": settings.DEMO_MODE}
