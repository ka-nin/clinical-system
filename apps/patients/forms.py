from django import forms
from django.utils import timezone

from apps.accounts.formats import DATE_ATTRS, DATE_FORMATS

from .models import Patient


class PatientRegistrationForm(forms.ModelForm):
    full_name = forms.CharField(
        label="Full Legal Name", max_length=200,
        widget=forms.TextInput(attrs={"placeholder": "Elizabeth Hughes", "autocomplete": "off"}),
    )
    date_of_birth = forms.DateField(
        label="Date of Birth", input_formats=DATE_FORMATS, widget=forms.TextInput(attrs=DATE_ATTRS),
        error_messages={"invalid": "Enter a date as MM/DD/YYYY."},
    )

    class Meta:
        model = Patient
        fields = [
            "date_of_birth", "sex", "civil_status", "blood_type", "allergies", "phone", "email", "address",
            "emergency_contact_name", "emergency_relationship", "emergency_phone",
        ]
        labels = {
            "sex": "Biological Sex", "civil_status": "Civil Status", "blood_type": "Blood Type",
            "phone": "Contact Number", "email": "Email Address", "address": "Home Address",
            "allergies": "Allergies", "emergency_contact_name": "Contact Name", "emergency_relationship": "Relationship",
            "emergency_phone": "Phone Number",
        }
        widgets = {
            "allergies": forms.TextInput(attrs={"placeholder": "e.g. Penicillin, Latex — or type NKDA if none"}),
            "phone": forms.TextInput(attrs={"placeholder": "+1 (555) 019-2831", "type": "tel"}),
            "email": forms.EmailInput(attrs={"placeholder": "name@example.com"}),
            "address": forms.TextInput(attrs={"placeholder": "842 Hilltop Dr, Apt 4C, New York, NY, 10001"}),
            "emergency_contact_name": forms.TextInput(attrs={"placeholder": "Full name"}),
            "emergency_relationship": forms.TextInput(attrs={"placeholder": "e.g. Spouse, Parent"}),
            "emergency_phone": forms.TextInput(attrs={"placeholder": "+1 (555) 919-4820", "type": "tel"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        f = self.fields
        f["sex"].choices = [("", "Select…")] + list(Patient.SEXES)
        f["civil_status"].choices = [("", "Select…")] + list(Patient.CIVIL_STATUSES)
        f["blood_type"].choices = [("", "Not known")] + list(Patient.BLOOD_TYPES)
        for name in ("sex", "allergies", "emergency_contact_name", "emergency_relationship", "emergency_phone"):
            f[name].required = True
        self.order_fields(["full_name"] + self.Meta.fields)

    def clean_full_name(self):
        parts = self.cleaned_data["full_name"].split(None, 1)
        if len(parts) < 2:
            raise forms.ValidationError("Enter the patient's first and last name.")
        self.cleaned_data["first_name"], self.cleaned_data["last_name"] = parts
        return " ".join(parts)

    def clean_date_of_birth(self):
        dob = self.cleaned_data["date_of_birth"]
        if dob >= timezone.localdate():
            raise forms.ValidationError("Date of birth must be in the past.")
        return dob

    def save(self, commit=True):
        patient = super().save(commit=False)
        patient.first_name = self.cleaned_data["first_name"]
        patient.last_name = self.cleaned_data["last_name"]
        if commit:
            patient.save()
        return patient


class PatientEditForm(forms.ModelForm):
    """Contact details, allergies and emergency contact. Name, date of birth and sex are identity: changed by an administrator only."""

    reason = forms.CharField(label="Reason for change", max_length=255, required=False,
                             widget=forms.TextInput(attrs={"placeholder": "optional, e.g. patient moved"}))

    EDITABLE = ["phone", "email", "address", "civil_status", "blood_type", "allergies",
                "emergency_contact_name", "emergency_relationship", "emergency_phone"]

    class Meta:
        model = Patient
        fields = ["phone", "email", "address", "civil_status", "blood_type", "allergies",
                  "emergency_contact_name", "emergency_relationship", "emergency_phone"]
        labels = {"phone": "Contact Number", "email": "Email Address", "address": "Home Address", "civil_status": "Civil Status",
                  "blood_type": "Blood Type", "allergies": "Allergies", "emergency_contact_name": "Emergency Contact Name",
                  "emergency_relationship": "Relationship", "emergency_phone": "Emergency Contact Phone"}
        widgets = {"allergies": forms.TextInput(attrs={"placeholder": "Penicillin, Latex — or NKDA if none"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        f = self.fields
        f["civil_status"].choices = [("", "Select…")] + list(Patient.CIVIL_STATUSES)
        f["blood_type"].choices = [("", "Not known")] + list(Patient.BLOOD_TYPES)
        for name in ("allergies", "phone", "address"):
            f[name].required = True
