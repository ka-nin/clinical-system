import re

from django import forms

from apps.history.models import Visit

from .assessment import RANK, assess
from .models import Triage

BP_PATTERN = re.compile(r"^\s*(\d{2,3})\s*/\s*(\d{2,3})\s*$")


def parse_blood_pressure(text):
    """'118 / 74' -> (118, 74), or raises ValidationError with a message the nurse can act on."""
    match = BP_PATTERN.match(text or "")
    if not match:
        raise forms.ValidationError("Enter as systolic / diastolic, e.g. 118 / 74.")
    systolic, diastolic = int(match[1]), int(match[2])
    if not 50 <= systolic <= 260 or not 30 <= diastolic <= 160:
        raise forms.ValidationError("Blood pressure is outside the possible range. Please re-check the reading.")
    if diastolic >= systolic:
        raise forms.ValidationError("Systolic must be higher than diastolic.")
    return systolic, diastolic


def _num(value):
    return None if value in (None, "") else float(value)


def vitals_from(cleaned):
    """The numbers the assessment needs, taken from cleaned form data."""
    return {
        "temp": _num(cleaned.get("temperature_c")), "systolic": cleaned.get("systolic"), "diastolic": cleaned.get("diastolic"),
        "pulse": _num(cleaned.get("pulse")), "spo2": _num(cleaned.get("oxygen_sat")), "resp": _num(cleaned.get("respiratory_rate")),
        "pain": _num(cleaned.get("pain_score")), "weight": _num(cleaned.get("weight_kg")), "height": _num(cleaned.get("height_cm")),
    }


class VitalsFieldsMixin(forms.ModelForm):
    """The vitals boxes shared by the triage form and the amendment form."""

    blood_pressure = forms.CharField(
        label="Blood Pressure", max_length=9,
        widget=forms.TextInput(attrs={"placeholder": "118 / 74", "inputmode": "numeric", "autocomplete": "off", "data-vital": "bp"}),
    )

    VITAL_ORDER = ["temperature_c", "blood_pressure", "pulse", "respiratory_rate", "oxygen_sat", "pain_score", "weight_kg", "height_cm"]

    class Meta:
        model = Triage
        fields = ["temperature_c", "pulse", "respiratory_rate", "oxygen_sat", "pain_score", "weight_kg", "height_cm", "chief_complaint"]
        labels = {"temperature_c": "Temperature", "pulse": "Heart Rate", "respiratory_rate": "Respiratory Rate", "oxygen_sat": "Oxygen Saturation",
                  "pain_score": "Pain Score", "weight_kg": "Weight", "height_cm": "Height", "chief_complaint": "Chief Complaint & Nurse Assessment"}
        widgets = {
            "temperature_c": forms.NumberInput(attrs={"placeholder": "36.8", "step": "0.1", "data-vital": "temp"}),
            "pulse": forms.NumberInput(attrs={"placeholder": "72", "data-vital": "pulse"}),
            "respiratory_rate": forms.NumberInput(attrs={"placeholder": "16", "data-vital": "resp"}),
            "oxygen_sat": forms.NumberInput(attrs={"placeholder": "99", "data-vital": "spo2"}),
            "pain_score": forms.NumberInput(attrs={"placeholder": "0-10", "min": "0", "max": "10", "data-vital": "pain"}),
            "weight_kg": forms.NumberInput(attrs={"placeholder": "62", "step": "0.1", "data-vital": "weight"}),
            "height_cm": forms.NumberInput(attrs={"placeholder": "168", "data-vital": "height"}),
            "chief_complaint": forms.Textarea(attrs={"rows": 3, "placeholder": "Why is the patient here today? Add your assessment."}),
        }

    def clean_blood_pressure(self):
        systolic, diastolic = parse_blood_pressure(self.cleaned_data["blood_pressure"])
        self.cleaned_data["systolic"], self.cleaned_data["diastolic"] = systolic, diastolic
        return f"{systolic} / {diastolic}"


class TriageForm(VitalsFieldsMixin):
    priority = forms.ChoiceField(label="Assigned Priority Level", choices=Visit.Priority.choices,
                                 initial=Visit.Priority.NORMAL, widget=forms.RadioSelect)
    allergies = forms.CharField(
        label="Allergies", max_length=255, required=False,
        widget=forms.TextInput(attrs={"placeholder": "List allergies, or type NKDA if none"}),
    )

    class Meta(VitalsFieldsMixin.Meta):
        fields = VitalsFieldsMixin.Meta.fields + ["identity_verified", "override_reason"]
        labels = {**VitalsFieldsMixin.Meta.labels, "identity_verified": "I confirmed the patient's identity (full name and date of birth)",
                  "override_reason": "Why is the priority lower than suggested?"}
        widgets = {**VitalsFieldsMixin.Meta.widgets,
                   "override_reason": forms.TextInput(attrs={"placeholder": "Required when you choose a lower level than suggested"})}

    def __init__(self, *args, patient=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.patient = patient
        self.suggestion = {"suggested": "normal", "reasons": [], "hints": {}}
        self.fields["identity_verified"].required = True
        self.fields["identity_verified"].error_messages["required"] = "Please confirm you checked the patient's identity."
        if patient is None or patient.allergy_status != "unknown":
            del self.fields["allergies"]  # already recorded: change it from the patient's details instead
        else:
            self.fields["allergies"].required = True
        self.order_fields(self.VITAL_ORDER + ["chief_complaint", "allergies", "priority", "override_reason", "identity_verified"])

    def clean(self):
        cleaned = super().clean()
        if self.patient is not None:
            self.suggestion = assess(vitals_from(cleaned), self.patient.date_of_birth)
        chosen, suggested = cleaned.get("priority"), self.suggestion["suggested"]
        if chosen and RANK[chosen] < RANK[suggested] and not (cleaned.get("override_reason") or "").strip():
            self.add_error("override_reason", "The vitals suggest a higher level. Please say why you chose a lower one.")
        return cleaned

    def save(self, commit=True):
        triage = super().save(commit=False)
        triage.systolic = self.cleaned_data["systolic"]
        triage.diastolic = self.cleaned_data["diastolic"]
        triage.suggested_priority = self.suggestion["suggested"]
        if RANK[self.cleaned_data["priority"]] >= RANK[self.suggestion["suggested"]]:
            triage.override_reason = ""  # only keep an override reason when it was actually an override
        if commit:
            triage.save()
        return triage


class TriageAmendForm(VitalsFieldsMixin):
    """Correct a recorded vital. The original value stays on file."""

    reason = forms.CharField(label="Reason for the correction", max_length=255,
                             widget=forms.TextInput(attrs={"placeholder": "e.g. typing mistake, re-measured"}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        instance = kwargs.get("instance")
        if instance is not None and not self.is_bound:
            self.initial["blood_pressure"] = f"{instance.systolic} / {instance.diastolic}"
        self.order_fields(self.VITAL_ORDER + ["chief_complaint", "reason"])

    def save(self, commit=True):
        triage = super().save(commit=False)
        triage.systolic = self.cleaned_data["systolic"]
        triage.diastolic = self.cleaned_data["diastolic"]
        if commit:
            triage.save()
        return triage
