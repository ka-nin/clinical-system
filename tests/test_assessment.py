from datetime import date

import pytest

from apps.triage.assessment import age_in_months, assess

TODAY = date(2026, 9, 28)
ADULT = date(1990, 1, 1)
INFANT = date(2026, 3, 1)      # 7 months
TODDLER = date(2024, 9, 1)     # 2 years
TEEN = date(2011, 1, 1)        # 15 years


def hint(vitals, dob, key):
    return assess(vitals, dob, TODAY)["hints"][key]


def test_age_in_months():
    assert age_in_months(date(2026, 8, 28), TODAY) == 1 and age_in_months(date(2026, 8, 29), TODAY) == 0
    assert age_in_months(date(1990, 1, 1), TODAY) == 36 * 12 + 8


@pytest.mark.parametrize("pulse,dob,expected", [
    (72, ADULT, "Normal"), (130, ADULT, "Abnormal"), (105, ADULT, "Elevated"), (55, ADULT, "Low"),
    (130, INFANT, "Normal"),          # normal for a baby, alarming in an adult
    (130, TODDLER, "Normal"), (165, TODDLER, "Elevated"), (108, TEEN, "Elevated"), (75, TEEN, "Normal"),
])
def test_heart_rate_depends_on_age(pulse, dob, expected):
    assert hint({"pulse": pulse}, dob, "pulse")[0] == expected


def test_respiratory_rate_depends_on_age():
    assert hint({"resp": 40}, INFANT, "resp") == ["Normal", "ok"]
    assert hint({"resp": 40}, ADULT, "resp")[1] == "bad"
    assert hint({"resp": 16}, ADULT, "resp") == ["Normal", "ok"]


def test_fever_in_a_young_baby_is_serious():
    newborn = date(2026, 8, 20)  # ~1 month
    assert hint({"temp": 38.1}, newborn, "temp")[1] == "bad"
    assert hint({"temp": 38.1}, ADULT, "temp") == ["Fever", "warn"]
    assert hint({"temp": 36.8}, ADULT, "temp") == ["Optimal", "ok"]
    assert hint({"temp": 39.6}, ADULT, "temp")[1] == "bad"


@pytest.mark.parametrize("spo2,tone", [(99, "ok"), (95, "ok"), (92, "warn"), (89, "bad")])
def test_oxygen_saturation(spo2, tone):
    assert hint({"spo2": spo2}, ADULT, "spo2")[1] == tone


@pytest.mark.parametrize("s,d,dob,tone", [
    (118, 74, ADULT, "ok"), (120, 80, ADULT, "ok"), (135, 85, ADULT, "ok"), (150, 95, ADULT, "warn"), (185, 100, ADULT, "bad"),
    (85, 55, ADULT, "warn"), (75, 50, ADULT, "bad"), (100, 60, TODDLER, "ok"), (72, 40, TODDLER, "warn"), (55, 30, TODDLER, "bad"),
])
def test_blood_pressure_bands(s, d, dob, tone):
    assert hint({"systolic": s, "diastolic": d}, dob, "bp")[1] == tone


def test_ordinary_readings_do_not_trigger_a_priority_suggestion():
    assert hint({"systolic": 120, "diastolic": 80}, ADULT, "bp") == ["Borderline", "ok"]
    assert assess({"systolic": 120, "diastolic": 80, "temp": 36.8, "pulse": 72}, ADULT, TODAY)["suggested"] == "normal"


def test_bmi_only_for_adults():
    assert hint({"weight": 62, "height": 168}, ADULT, "weight") == ["Healthy", "ok"]
    assert hint({"weight": 62, "height": 168}, ADULT, "height") == ["Healthy BMI", "ok"]
    assert hint({"weight": 80, "height": 168}, ADULT, "weight") == ["Overweight", "warn"]
    assert hint({"weight": 95, "height": 168}, ADULT, "weight")[1] == "bad"
    assert "weight" not in assess({"weight": 20, "height": 115}, TODDLER, TODAY)["hints"]


def test_suggested_priority_follows_the_worst_finding():
    normal = {"temp": 36.8, "systolic": 118, "diastolic": 74, "pulse": 72, "spo2": 99, "resp": 16, "pain": 2}
    assert assess(normal, ADULT, TODAY)["suggested"] == "normal"
    assert assess({**normal, "temp": 38.4}, ADULT, TODAY)["suggested"] == "priority"
    result = assess({**normal, "spo2": 88}, ADULT, TODAY)
    assert result["suggested"] == "urgent" and any("Oxygen saturation 88" in r for r in result["reasons"])
    assert assess({}, ADULT, TODAY)["suggested"] == "normal"


def test_partial_data_does_not_crash():
    assert assess({"systolic": 120}, ADULT, TODAY)["hints"] == {}
