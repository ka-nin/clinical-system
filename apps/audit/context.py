"""Remembers the address of the request being handled, so every audit entry can record where it came from."""
from contextvars import ContextVar

from django.conf import settings

_ip = ContextVar("audit_ip", default=None)


def client_ip(request):
    """The caller's address. Behind a trusted proxy (TRUST_PROXY_HEADERS) the first X-Forwarded-For value is used."""
    if getattr(settings, "TRUST_PROXY_HEADERS", False):
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip()
        if forwarded:
            return forwarded
    return request.META.get("REMOTE_ADDR") or None


def current_ip():
    return _ip.get()


class AuditContextMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        token = _ip.set(client_ip(request))
        try:
            return self.get_response(request)
        finally:
            _ip.reset(token)
