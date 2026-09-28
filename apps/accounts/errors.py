"""Friendly handling for the moments people most often hit an error page."""
from django.contrib import messages
from django.shortcuts import redirect, render


class FriendlyErrorsMiddleware:
    """
    * Back button or refresh on a button's address (e.g. /triage/5/start/): those only accept a button press, so
      instead of a bare "405 Method Not Allowed", go to the person's home page with a short explanation.
    * "You don't have access" messages written as plain text: show them on the styled error page with a way back.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if response.status_code == 405 and request.method in ("GET", "HEAD") and not _wants_json(request):
            messages.info(request, "That address only works from its button, so you were taken back here.")
            return redirect("dashboard" if request.user.is_authenticated else "home")
        if response.status_code == 403 and not response.streaming and _is_plain_text(response) and not _wants_json(request):
            return render(request, "403.html", {"reason": response.content.decode(errors="ignore")[:300]}, status=403)
        return response


def _wants_json(request):
    return request.headers.get("X-Requested-With") == "fetch" or "application/json" in request.headers.get("Accept", "")


def _is_plain_text(response):
    body = response.content[:200].lstrip().lower()
    return bool(body) and not body.startswith((b"<!doctype", b"<html", b"<h1>"))


def page_not_found(request, exception=None):
    return render(request, "404.html", status=404)


def permission_denied(request, exception=None):
    return render(request, "403.html", {"reason": str(exception or "")}, status=403)


def server_error(request):
    return render(request, "500.html", status=500)


def csrf_failure(request, reason=""):
    return render(request, "403.html", {"reason": "Your page was open too long or your session ended, so the form expired. "
                                                  "Go back, refresh the page, and try again.", "title": "Please try that again"},
                  status=403)
