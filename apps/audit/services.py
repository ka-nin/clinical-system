from .models import AuditEntry


def log(user, kind, text, patient=None, ip=None):
    """Write one audit entry. The address of the current request is added automatically."""
    return AuditEntry.objects.create(user=user, kind=kind, text=text[:255], patient=patient, ip_address=ip)


def verify_chain():
    """Check every chained entry against its fingerprint and the entry before it. Returns (checked, problems)."""
    problems, previous, checked = [], None, 0
    for entry in AuditEntry.objects.order_by("id").iterator():
        if not entry.entry_hash:
            previous = None  # written before the chain existed
            continue
        if entry.entry_hash != entry.compute_hash():
            problems.append(f"#{entry.pk} ({entry.created_at:%Y-%m-%d %H:%M}): contents do not match its fingerprint (edited?)")
        if previous is not None and entry.prev_hash != previous:
            problems.append(f"#{entry.pk} ({entry.created_at:%Y-%m-%d %H:%M}): the entry before it is missing or was changed")
        previous = entry.entry_hash
        checked += 1
    return checked, problems
