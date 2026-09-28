from django import forms

from .models import Consultation, LabResult, Prescription

PLACEHOLDERS = {
    "patient_summary": "Optional. A short, plain-language summary the patient will see in their portal (no jargon).",
    "subjective": "What the patient reports: symptoms, onset, history…",
    "objective": "Examination findings and observations…",
    "assessment": "Diagnosis and clinical impression…",
    "plan": "Treatment, prescriptions and follow-up…",
}


class ConsultationForm(forms.ModelForm):
    class Meta:
        model = Consultation
        fields = [*Consultation.SECTIONS, "patient_summary"]
        widgets = {name: forms.Textarea(attrs={"placeholder": PLACEHOLDERS[name], "rows": 6}) for name in fields}


class PrescriptionForm(forms.ModelForm):
    override_allergy = forms.BooleanField(required=False, label="I have reviewed the allergy warning and still want to prescribe this")

    class Meta:
        model = Prescription
        fields = ["medication", "dose", "frequency", "duration", "instructions"]
        widgets = {
            "medication": forms.TextInput(attrs={"placeholder": "e.g. Albuterol HFA inhaler"}),
            "dose": forms.TextInput(attrs={"placeholder": "e.g. 90 mcg, 2 puffs"}),
            "frequency": forms.TextInput(attrs={"placeholder": "e.g. every 4-6 hours as needed"}),
            "duration": forms.TextInput(attrs={"placeholder": "e.g. 10 days (optional)"}),
            "instructions": forms.TextInput(attrs={"placeholder": "Extra instructions (optional)"}),
        }


class LabResultForm(forms.ModelForm):
    class Meta:
        model = LabResult
        fields = ["test_name", "value", "unit", "reference_range", "flag", "comment"]
        labels = {"test_name": "Test", "reference_range": "Reference range"}
        widgets = {
            "test_name": forms.TextInput(attrs={"placeholder": "e.g. Hemoglobin"}),
            "value": forms.TextInput(attrs={"placeholder": "e.g. 13.8"}),
            "unit": forms.TextInput(attrs={"placeholder": "e.g. g/dL"}),
            "reference_range": forms.TextInput(attrs={"placeholder": "e.g. 12.0-15.5"}),
            "comment": forms.TextInput(attrs={"placeholder": "optional, e.g. correction of the result above"}),
        }
