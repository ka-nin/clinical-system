from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.password_validation import validate_password
from django.db import transaction

from .formats import DATE_ATTRS, DATE_FORMATS
from .models import Profile

User = get_user_model()

CLINIC_STAFF = "ClinicStaff"
STUDENT = "Student"


def _input(placeholder="", **attrs):
    return forms.TextInput(attrs={"placeholder": placeholder, **attrs})


def _password(**attrs):
    return forms.PasswordInput(attrs={"placeholder": "••••••••", "autocomplete": "new-password", **attrs})


class BaseRegistrationForm(forms.Form):
    full_name = forms.CharField(max_length=150, widget=_input(autocomplete="name"))
    email = forms.EmailField(max_length=150, widget=forms.EmailInput(attrs={"autocomplete": "email"}))
    password1 = forms.CharField(widget=_password())
    password2 = forms.CharField(widget=_password())

    group_name = None
    role = None
    activate_immediately = True
    name_placeholder = ""
    email_placeholder = ""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["full_name"].widget.attrs["placeholder"] = self.name_placeholder
        self.fields["email"].widget.attrs["placeholder"] = self.email_placeholder

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(username__iexact=email).exists() or User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def clean(self):
        cleaned = super().clean()
        p1, p2 = cleaned.get("password1"), cleaned.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", "Passwords do not match.")
        elif p1:
            try:
                validate_password(p1)
            except forms.ValidationError as exc:
                self.add_error("password1", exc)
        return cleaned

    def profile_fields(self):
        return {}

    @transaction.atomic
    def save(self):
        data = self.cleaned_data
        first, _, last = data["full_name"].strip().partition(" ")
        user = User(
            username=data["email"], email=data["email"],
            first_name=first[:150], last_name=last[:150],
            is_active=self.activate_immediately,
        )
        user.set_password(data["password1"])
        user.save()
        group, _ = Group.objects.get_or_create(name=self.group_name)
        user.groups.add(group)
        Profile.objects.create(user=user, role=self.role or data["role"], **self.profile_fields())
        return user


class StudentRegistrationForm(BaseRegistrationForm):
    group_name = STUDENT
    role = Profile.Role.STUDENT
    name_placeholder = "Jane Doe"
    email_placeholder = "jane.doe@university.edu"

    date_of_birth = forms.DateField(
        input_formats=DATE_FORMATS, widget=forms.TextInput(attrs=DATE_ATTRS),
        error_messages={"invalid": "Enter a date as MM/DD/YYYY."},
    )
    phone = forms.CharField(max_length=30, widget=_input("+1 (555) 000-0000", autocomplete="tel", type="tel"))
    student_id = forms.CharField(max_length=40, widget=_input("e.g. STU-120491-X"))

    def clean_date_of_birth(self):
        from django.utils import timezone
        dob = self.cleaned_data["date_of_birth"]
        if dob >= timezone.localdate():
            raise forms.ValidationError("Date of birth must be in the past.")
        return dob

    def clean_student_id(self):
        sid = self.cleaned_data["student_id"].strip()
        if Profile.objects.filter(student_id__iexact=sid).exists():
            raise forms.ValidationError("This student ID is already registered.")
        return sid

    def profile_fields(self):
        d = self.cleaned_data
        return {"date_of_birth": d["date_of_birth"], "phone": d["phone"], "student_id": d["student_id"]}


class StaffRegistrationForm(BaseRegistrationForm):
    group_name = CLINIC_STAFF
    activate_immediately = False  # an administrator approves staff before they can sign in
    name_placeholder = "Dr./Nurse Henderson"
    email_placeholder = "staff@hospital.org"

    employee_id = forms.CharField(max_length=40, widget=_input("NUR-98104"))
    department = forms.CharField(max_length=100, widget=_input("e.g. Urgent Care, Triage"))
    role = forms.ChoiceField(
        choices=[c for c in Profile.Role.choices if c[0] != Profile.Role.STUDENT],
        initial=Profile.Role.NURSE, widget=forms.RadioSelect,
    )

    def clean_employee_id(self):
        eid = self.cleaned_data["employee_id"].strip()
        if Profile.objects.filter(employee_id__iexact=eid).exists():
            raise forms.ValidationError("This employee / license ID is already registered.")
        return eid

    def profile_fields(self):
        d = self.cleaned_data
        return {"employee_id": d["employee_id"], "department": d["department"]}
