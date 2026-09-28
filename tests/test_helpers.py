from datetime import date

import pytest

from apps.history import allergy
from apps.patients.matching import possible_matches, similarity
from apps.patients.models import Patient


def P(allergies):
    return Patient(first_name="A", last_name="B", date_of_birth=date(1990, 1, 1), allergies=allergies)


@pytest.mark.parametrize("allergies,med,expect_warning", [
    ("Penicillin", "Amoxicillin 500 mg", True), ("Penicillin, Tree Nuts", "Paracetamol", False),
    ("Sulfa drugs", "Co-trimoxazole", True), ("NSAIDs", "Ibuprofen 400", True), ("Ibuprofen", "Naproxen", True),
    ("Latex", "Amoxicillin", False), ("NKDA", "Amoxicillin", False), ("None", "anything", False),
    ("", "Paracetamol", True),  # never asked -> must be recorded or overridden
    ("penicillin allergy; egg", "Augmentin", True), ("Cephalosporins", "Cefalexin", True),
])
def test_allergy_check(allergies, med, expect_warning):
    assert bool(allergy.check(P(allergies), med)) == expect_warning


def test_allergy_status():
    assert P("").allergy_status == "unknown" and P("NKDA").allergy_status == "none"
    assert P("No known allergies.").allergy_status == "none" and P("Penicillin").allergy_status == "listed"


@pytest.mark.django_db
def test_possible_matches_finds_typos_but_not_strangers():
    jon = Patient.objects.create(first_name="Jon", last_name="Smith", date_of_birth=date(1985, 5, 5), phone="111", address="x")
    Patient.objects.create(first_name="Maria", last_name="Cruz", date_of_birth=date(1985, 5, 5), phone="222", address="x")
    assert possible_matches("John", "Smith", date(1985, 5, 5), "999") == [jon]      # same DOB, one letter off
    assert possible_matches("John", "Smith", date(1970, 1, 1), "111") == [jon]      # same phone, similar name
    assert possible_matches("Peter", "Jones", date(1985, 5, 5), "999") == []        # same DOB but a different person
    assert possible_matches("Jon", "Smith", date(1985, 5, 5), "111") == []          # exact record: handled elsewhere
    assert similarity("Ana  Lopez", "ana lopez") == 1.0
