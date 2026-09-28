from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.urls import reverse_lazy
from django.views.generic import FormView

from apps.audit.services import log

from . import dashboard as dash
from . import twofactor
from .permissions import clinic_staff_required
from .forms import StaffRegistrationForm, StudentRegistrationForm
from .models import TwoFactor

User = get_user_model()


PENDING_2FA = "pending_2fa"
PENDING_MINUTES = 5


def landing(request):
    from .public import snapshot

    return render(request, "landing.html", {"live": snapshot()})


class CareLoginView(LoginView):
    template_name = "login.html"

    def form_valid(self, form):
        user = form.get_user()
        device = getattr(user, "two_factor", None)
        if device is not None and device.is_confirmed:
            # Password was right, but don't sign in yet: ask for the authenticator code first.
            self.request.session[PENDING_2FA] = {
                "uid": user.pk, "backend": user.backend, "next": self.get_success_url(),
                "remember": bool(self.request.POST.get("remember_me")), "at": timezone.now().timestamp(), "tries": 0,
            }
            return redirect("login_verify")
        response = super().form_valid(form)
        response["Location"] = dash.safe_next(user, response["Location"])
        # Without "Remember this computer", the session ends when the browser closes.
        if not self.request.POST.get("remember_me"):
            self.request.session.set_expiry(0)
        return response


def login_verify(request):
    """Second sign-in step: a code from the authenticator app, or a one-time recovery code."""
    pending = request.session.get(PENDING_2FA)
    expired = pending and timezone.now().timestamp() - pending["at"] > PENDING_MINUTES * 60
    if not pending or expired:
        request.session.pop(PENDING_2FA, None)
        messages.info(request, "Please sign in again.")
        return redirect("login")

    user = get_object_or_404(User, pk=pending["uid"])
    error = ""
    if request.method == "POST":
        code = request.POST.get("code", "")
        device = user.two_factor
        if twofactor.check_code(device, code) or twofactor.use_recovery_code(device, code):
            login(request, user, backend=pending["backend"])
            if not pending["remember"]:
                request.session.set_expiry(0)
            request.session.pop(PENDING_2FA, None)
            return redirect(dash.safe_next(user, pending["next"]))
        pending["tries"] += 1
        request.session[PENDING_2FA] = pending
        if pending["tries"] >= 5:
            request.session.pop(PENDING_2FA, None)
            messages.error(request, "Too many wrong codes. Please sign in again.")
            return redirect("login")
        error = "That code didn't work. Check your authenticator app and try again."
    return render(request, "accounts/verify.html", {"error": error})


@login_required
def security_2fa(request):
    """Set up, or review, the authenticator app for the signed-in account."""
    device = getattr(request.user, "two_factor", None)
    if device is not None and device.is_confirmed:
        return render(request, "accounts/security_2fa.html", {"enabled": True, "left": len(device.recovery_hashes), "required": settings.REQUIRE_2FA})
    if request.method == "POST":
        device = TwoFactor.objects.filter(user=request.user).first()
        if device and twofactor.check_code(device, request.POST.get("code", "")):
            twofactor.confirm(device)
            codes = twofactor.new_recovery_codes(device)
            messages.success(request, "Two-step sign-in is on.")
            return render(request, "accounts/security_2fa.html", {"enabled": True, "new_codes": codes, "left": len(codes), "required": settings.REQUIRE_2FA})
        error = "That code didn't match. Wait for the next code and try again."
    else:
        device, error = twofactor.get_or_start(request.user), ""
    return render(request, "accounts/security_2fa.html", {"enabled": False, "qr": twofactor.qr_svg(device), "secret": device.secret, "error": error})


class StudentRegisterView(FormView):
    template_name = "accounts/register_student.html"
    form_class = StudentRegistrationForm
    success_url = reverse_lazy("login")

    def form_valid(self, form):
        user = form.save()
        log(None, "SYSTEM", f"student account created for {user.get_full_name()} (self-service registration)")
        messages.success(self.request, "Your account was created. Sign in to view your records.")
        return super().form_valid(form)


class StaffRegisterView(FormView):
    template_name = "accounts/register_staff.html"
    form_class = StaffRegistrationForm
    success_url = reverse_lazy("login")

    def form_valid(self, form):
        user = form.save()
        log(None, "SYSTEM", f"staff access requested by {user.get_full_name()} ({user.profile.get_role_display()})")
        messages.success(
            self.request,
            "Credentials requested. A system administrator will review your request before you can sign in.",
        )
        return super().form_valid(form)


@login_required
def dashboard(request):
    """Send each role to its own dashboard."""
    user = request.user
    landing = dash.landing_for(user)
    if landing == "admin":
        return redirect("manage_dashboard")
    if landing not in ("staff", "student"):
        return HttpResponseForbidden("Your account has no role assigned yet. Ask an administrator.")

    context = {"greeting": dash.greeting_for(user)}
    if landing == "student":
        return redirect("portal_profile")
    context.update(dash.staff_dashboard_context(user))
    return render(request, "app/staff_dashboard.html", context)


@clinic_staff_required
def dashboard_live(request):
    """Just the changing parts of the dashboard, fetched every few seconds by the page."""
    context = {"greeting": dash.greeting_for(request.user)}
    context.update(dash.staff_dashboard_context(request.user))
    return render(request, "app/_staff_live.html", context)
