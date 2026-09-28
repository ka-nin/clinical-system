from difflib import SequenceMatcher

from django.db.models import Q

from .models import Patient


def _norm(text):
    return " ".join((text or "").lower().split())


def similarity(a, b):
    return SequenceMatcher(None, _norm(a), _norm(b)).ratio()


def possible_matches(first_name, last_name, dob, phone="", limit=5):
    """Existing patients who might be the same person, so a typo doesn't create a second record.

    Same date of birth with a similar name, or the same phone number with a similar name.
    (An exact name + date of birth match is handled separately: that record is simply reused.)
    """
    query = Q(date_of_birth=dob)
    if phone:
        query |= Q(phone=phone)
    full = f"{first_name} {last_name}"
    scored = []
    for patient in Patient.objects.filter(query):
        ratio = similarity(full, patient.full_name)
        same_dob = patient.date_of_birth == dob
        if ratio >= (0.72 if same_dob else 0.85) and not (same_dob and ratio == 1.0):
            scored.append((ratio, patient))
    scored.sort(key=lambda pair: -pair[0])
    return [p for _, p in scored[:limit]]
