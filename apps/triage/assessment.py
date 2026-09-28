"""Age-aware reference ranges and a suggested priority for triage vitals.

These are simplified screening ranges to help a nurse notice a problem quickly. They are NOT a diagnosis
and never decide anything on their own: the nurse chooses the priority (and explains any lower choice).
Sources: common paediatric advanced-life-support reference tables and adult early-warning-score bands.
"""
from datetime import date

OK, WARN, BAD = "ok", "warn", "bad"
RANK = {"normal": 0, "priority": 1, "urgent": 2}

# (upper age limit in months, low, high) for awake, resting children and adults.
HEART_RATE = [(1, 100, 205), (12, 100, 160), (36, 90, 150), (72, 80, 120), (144, 70, 110), (216, 60, 100), (10**6, 60, 100)]
RESP_RATE = [(1, 30, 60), (12, 30, 53), (36, 22, 37), (72, 20, 28), (144, 18, 25), (216, 12, 20), (10**6, 12, 20)]


def age_in_months(dob, today=None):
    today = today or date.today()
    return (today.year - dob.year) * 12 + (today.month - dob.month) - (1 if today.day < dob.day else 0)


def _band(table, months):
    for limit, low, high in table:
        if months < limit:
            return low, high
    return table[-1][1], table[-1][2]


def _range_hint(value, low, high):
    if low <= value <= high:
        return "Normal", OK
    if value < low * 0.75 or value > high * 1.25:
        return "Abnormal", BAD
    return ("Low" if value < low else "Elevated"), WARN


def _temp(v, months):
    if v < 35.0:
        return "Low", BAD
    if v < 36.1:
        return "Slightly Low", WARN
    if v <= 37.2:
        return "Optimal", OK
    if v < 38.0:
        return "Elevated", WARN
    if months < 3 or v >= 39.5:  # any fever in a baby under 3 months is treated as serious
        return ("Fever (infant)" if months < 3 else "High Fever"), BAD
    return "Fever", WARN


def _spo2(v):
    if v >= 95:
        return "Optimal", OK
    return ("Low", WARN) if v >= 90 else ("Critical", BAD)


def _bp(systolic, diastolic, months):
    years = months / 12
    if years >= 13:
        # Triage bands: escalate what matters in the next hours. Long-term hypertension staging is a doctor's call,
        # so readings like 120/80 or 135/85 are only labelled, not escalated (too many false alarms train people to ignore alarms).
        if systolic >= 180 or diastolic >= 120:
            return "Crisis", BAD
        if systolic >= 140 or diastolic >= 90:
            return "High", WARN
        if systolic < 80:
            return "Very Low", BAD
        if systolic < 90 or diastolic < 60:
            return "Low", WARN
        if systolic < 120 and diastolic < 80:
            return "Optimal", OK
        return "Borderline", OK
    # children: only screen for low pressure and very high pressure (full centile tables need a growth chart)
    low = 60 if months < 1 else 70 if years < 1 else 70 + 2 * int(years) if years <= 10 else 90
    if systolic < low - 10:
        return "Very Low", BAD
    if systolic < low:
        return "Low", WARN
    if systolic >= 140:
        return "High", BAD
    return "Normal", OK


def _pain(v):
    if v == 0:
        return "None", OK
    if v <= 3:
        return "Mild", OK
    return ("Moderate", WARN) if v <= 6 else ("Severe", BAD)


def _bmi(weight, height, months):
    if months < 216 or not height:  # under 18: needs a growth chart, not an adult BMI
        return None
    bmi = weight / (height / 100) ** 2
    if bmi < 18.5:
        return f"Underweight", WARN, bmi
    if bmi < 25:
        return "Healthy", OK, bmi
    return ("Overweight", WARN, bmi) if bmi < 30 else ("Obese", BAD, bmi)


def assess(vitals, dob, today=None):
    """vitals: dict with optional numeric keys temp, systolic, diastolic, pulse, spo2, resp, pain, weight, height.

    Returns {"hints": {key: [label, tone]}, "suggested": "normal|priority|urgent", "reasons": [str, ...]}.
    """
    months = age_in_months(dob, today)
    hints, reasons = {}, []

    def note(key, label, tone, text):
        hints[key] = [label, tone]
        if tone != OK:
            reasons.append(f"{text} ({label.lower()})")

    v = vitals
    if v.get("temp") is not None:
        note("temp", *_temp(v["temp"], months), f"Temperature {v['temp']:g} °C")
    if v.get("systolic") is not None and v.get("diastolic") is not None:
        note("bp", *_bp(v["systolic"], v["diastolic"], months), f"Blood pressure {v['systolic']:g}/{v['diastolic']:g}")
    if v.get("pulse") is not None:
        note("pulse", *_range_hint(v["pulse"], *_band(HEART_RATE, months)), f"Heart rate {v['pulse']:g} bpm")
    if v.get("spo2") is not None:
        note("spo2", *_spo2(v["spo2"]), f"Oxygen saturation {v['spo2']:g}%")
    if v.get("resp") is not None:
        note("resp", *_range_hint(v["resp"], *_band(RESP_RATE, months)), f"Respiratory rate {v['resp']:g}/min")
    if v.get("pain") is not None:
        note("pain", *_pain(v["pain"]), f"Pain {v['pain']:g}/10")
    if v.get("weight") and v.get("height"):
        result = _bmi(v["weight"], v["height"], months)
        if result:
            label, tone, bmi = result
            hints["weight"] = [label, tone]
            hints["height"] = ["Healthy BMI" if tone == OK else f"BMI {bmi:.1f}", tone]

    tones = [tone for _, tone in hints.values()]
    suggested = "urgent" if BAD in tones else "priority" if WARN in tones else "normal"
    return {"hints": hints, "suggested": suggested, "reasons": reasons, "age_months": months}
