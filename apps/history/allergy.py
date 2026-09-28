"""A simple safety net for prescribing: compare an order against the patient's recorded allergies.

It matches the allergy text against the medication name, plus a small list of common drug families.
It is a reminder to look, not a complete drug-interaction database.
"""
import re

FAMILIES = {
    "penicillin": ["penicillin", "amoxicillin", "ampicillin", "amoxil", "augmentin", "piperacillin", "flucloxacillin", "cloxacillin", "dicloxacillin"],
    "amoxicillin": ["penicillin", "amoxicillin", "amoxil", "augmentin", "ampicillin"],
    "sulfa": ["sulfa", "sulfamethoxazole", "co-trimoxazole", "cotrimoxazole", "bactrim", "trimethoprim"],
    "cephalosporin": ["cef", "ceph", "keflex"],
    "nsaid": ["ibuprofen", "naproxen", "diclofenac", "ketorolac", "mefenamic", "celecoxib", "meloxicam", "aspirin", "indomethacin"],
    "ibuprofen": ["ibuprofen", "advil", "motrin", "naproxen", "diclofenac", "ketorolac", "aspirin"],
    "aspirin": ["aspirin", "acetylsalicylic", "ibuprofen", "naproxen", "diclofenac"],
    "macrolide": ["azithromycin", "clarithromycin", "erythromycin"],
    "codeine": ["codeine", "morphine", "tramadol", "oxycodone", "hydrocodone"],
    "opioid": ["codeine", "morphine", "tramadol", "oxycodone", "hydrocodone", "fentanyl"],
    "quinolone": ["ciprofloxacin", "levofloxacin", "moxifloxacin", "ofloxacin", "floxacin"],
    "tetracycline": ["tetracycline", "doxycycline", "minocycline"],
}


def _tokens(text):
    return [t.strip() for t in re.split(r"[,;/\n]|\band\b", (text or "").lower()) if len(t.strip()) >= 3]


def check(patient, medication):
    """Return a warning string when the order needs a second look, or '' when it looks fine."""
    status = patient.allergy_status
    if status == "unknown":
        return "The patient's allergies have not been recorded."
    if status == "none":
        return ""
    med = (medication or "").lower()
    hits = []
    for allergen in _tokens(patient.allergies):
        # every drug family whose name appears in the allergy text (so "NSAIDs" and "penicillin allergy" both work)
        related = {word for key, words in FAMILIES.items() if key in allergen for word in words}
        words = {w for w in re.findall(r"[a-z\-]{4,}", allergen) if w not in {"allergy", "allergic", "drugs", "drug", "reaction"}}
        if allergen in med or any(w in med for w in words) or any(word in med for word in related):
            hits.append(allergen)
    if hits:
        return f"The patient is recorded as allergic to: {', '.join(sorted(set(hits)))}."
    return ""
