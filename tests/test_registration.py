import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.accounts.models import Profile

User = get_user_model()
PW = "Str0ng-Passw0rd!"


def student_data(**kw):
    d = {"full_name": "Jane Doe", "email": "Jane.Doe@university.edu", "date_of_birth": "04/12/2003",
         "phone": "+1 (555) 000-0000", "student_id": "STU-120491-X", "password1": PW, "password2": PW}
    d.update(kw)
    return d


def staff_data(**kw):
    d = {"full_name": "Nurse Henderson", "email": "staff@hospital.org", "employee_id": "NUR-98104",
         "department": "Triage", "role": "nurse", "password1": PW, "password2": PW}
    d.update(kw)
    return d


@pytest.mark.django_db
def test_student_registers_and_can_sign_in(client):
    r = client.post(reverse("register_student"), student_data())
    assert r.status_code == 302
    user = User.objects.get(username="jane.doe@university.edu")
    assert user.is_active and user.groups.filter(name="Student").exists()
    assert user.profile.role == Profile.Role.STUDENT
    # login is case-insensitive on the email
    assert client.login(username="JANE.DOE@university.edu", password=PW)


@pytest.mark.django_db
def test_staff_request_is_inactive_until_approved(client):
    assert client.post(reverse("register_staff"), staff_data()).status_code == 302
    user = User.objects.get(username="staff@hospital.org")
    assert not user.is_active and user.groups.filter(name="ClinicStaff").exists()
    assert not client.login(username="staff@hospital.org", password=PW)
    user.is_active = True
    user.save()
    assert client.login(username="staff@hospital.org", password=PW)


@pytest.mark.django_db
def test_validation_errors(client):
    client.post(reverse("register_student"), student_data())
    r = client.post(reverse("register_student"), student_data(email="jane.doe@university.edu", student_id="stu-120491-x",
                                                             password2="nope", date_of_birth="2003-04-12"))
    assert r.status_code == 200
    f = r.context["form"]
    assert {"email", "student_id", "password2", "date_of_birth"} <= set(f.errors)
    assert User.objects.count() == 1
