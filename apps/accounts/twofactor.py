"""Small helpers around pyotp: enrolment, code checks and recovery codes."""
import secrets
import time

import pyotp
import segno
from django.contrib.auth.hashers import check_password, make_password
from django.utils import timezone

from .models import TwoFactor

ISSUER = "CareBoard"


def get_or_start(user):
    """The user's 2FA record, creating an unconfirmed one (with a fresh secret) if needed."""
    device, created = TwoFactor.objects.get_or_create(user=user, defaults={"secret": pyotp.random_base32()})
    if not created and not device.is_confirmed:
        device.secret = pyotp.random_base32()  # restarting enrolment: never reuse an unconfirmed secret
        device.save(update_fields=["secret"])
    return device


def provisioning_uri(device):
    return pyotp.TOTP(device.secret).provisioning_uri(name=device.user.get_username(), issuer_name=ISSUER)


def qr_svg(device):
    return segno.make(provisioning_uri(device), error="m").svg_inline(scale=4, dark="#161b28", light="#ffffff", omitsize=True)


def check_code(device, code):
    """True for a fresh, valid 6-digit code. Each 30-second step can only be used once."""
    code = "".join(ch for ch in (code or "") if ch.isdigit())
    if len(code) != 6:
        return False
    totp = pyotp.TOTP(device.secret)
    now = int(time.time())
    for offset in (-1, 0, 1):  # allow a little clock drift
        step = now // 30 + offset
        if step > device.last_step and secrets.compare_digest(totp.at(step * 30), code):
            device.last_step = step
            device.save(update_fields=["last_step"])
            return True
    return False


def new_recovery_codes(device, count=8):
    codes = [f"{secrets.token_hex(2)}-{secrets.token_hex(2)}" for _ in range(count)]
    device.recovery_hashes = [make_password(c) for c in codes]
    device.save(update_fields=["recovery_hashes"])
    return codes


def use_recovery_code(device, code):
    code = (code or "").strip().lower()
    for i, hashed in enumerate(device.recovery_hashes):
        if check_password(code, hashed):
            device.recovery_hashes.pop(i)
            device.save(update_fields=["recovery_hashes"])
            return True
    return False


def confirm(device):
    device.confirmed_at = timezone.now()
    device.save(update_fields=["confirmed_at"])
