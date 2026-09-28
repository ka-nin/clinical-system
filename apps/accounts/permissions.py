from functools import wraps

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden

from .dashboard import CLINICAL_ROLES, landing_for, role_of
from .forms import CLINIC_STAFF


def clinic_staff_required(view):
    """Signed-in members of the ClinicStaff role only (receptionist, nurse, doctor)."""

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.groups.filter(name=CLINIC_STAFF).exists():
            return HttpResponseForbidden("This page is for clinic staff only.")
        return view(request, *args, **kwargs)

    return login_required(wrapper)


def role_required(*roles, message="You do not have permission to do that."):
    """Clinic staff whose job title is one of `roles` (e.g. 'nurse', 'physician')."""

    def decorator(view):
        @wraps(view)
        @clinic_staff_required
        def wrapper(request, *args, **kwargs):
            if role_of(request.user) not in roles:
                return HttpResponseForbidden(message)
            return view(request, *args, **kwargs)

        return wrapper

    return decorator


# Front desk registers patients and manages the queue. Clinical pages (vitals, notes) need one of these:
clinical_required = role_required(*CLINICAL_ROLES, message="Vitals and clinical notes are for nurses and physicians only.")


def admin_required(view):
    """System administrators only. They manage accounts and read the audit trail; they do not do clinical work."""

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if landing_for(request.user) != "admin":
            return HttpResponseForbidden("This page is for system administrators only.")
        return view(request, *args, **kwargs)

    return login_required(wrapper)
