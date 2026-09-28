import json
import shutil
import subprocess
from pathlib import Path

import pytest
from django.urls import reverse

from apps.accounts.forms import StudentRegistrationForm
from apps.patients.forms import PatientRegistrationForm
from apps.triage.forms import TriageAmendForm, TriageForm

JS = Path(__file__).resolve().parent.parent / "static" / "js" / "format.js"
node = pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is not installed")

DRIVER = """
const f = require(%r);
const typed = (fn, keys) => { let v = ""; const steps = []; for (const k of keys) { v = fn(v + k, false); steps.push(v); } return steps; };
const erased = (fn, start) => { let v = start; const steps = []; while (v.length) { v = fn(v.slice(0, -1), true); steps.push(v); } return steps; };
console.log(JSON.stringify(%s));
"""


def run(expr):
    out = subprocess.run(["node", "-e", DRIVER % (str(JS), expr)], capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


@node
def test_typing_a_date_adds_the_slashes():
    steps = run('typed(f.fmtDate, "10141988".split(""))')
    assert steps == ["1", "10/", "10/1", "10/14/", "10/14/1", "10/14/19", "10/14/198", "10/14/1988"]


@node
def test_dates_typed_or_pasted_in_other_shapes_are_tidied():
    assert run('[f.fmtDate("10-14-1988"), f.fmtDate("10.14.1988"), f.fmtDate("10/14/1988"), f.fmtDate("10141988"), f.fmtDate("abc10x14y1988z")]') == ["10/14/1988"] * 5
    assert run('[f.fmtDate("101419881234")]') == ["10/14/1988"]                       # nothing past the year


@node
def test_a_single_digit_month_or_day_gets_its_zero():
    assert run('typed(f.fmtDate, ["3"])') == ["03/"]
    assert run('typed(f.fmtDate, "104".split(""))') == ["1", "10/", "10/04/"]
    assert run('typed(f.fmtDate, "1".split(""))') == ["1"]                          # 1 could still be 10, 11 or 12


@node
def test_backspacing_a_date_is_not_blocked_by_the_slashes():
    steps = run('erased(f.fmtDate, "10/14/1988")')
    assert steps == ["10/14/198", "10/14/19", "10/14/1", "10/14", "10/1", "10", "1", ""]


@node
def test_typing_blood_pressure_adds_the_slash():
    assert run('typed(f.fmtBP, "118074".split(""))') == ["1", "11", "118 / ", "118 / 0", "118 / 07", "118 / 07"]
    assert run('typed(f.fmtBP, "11874".split(""))')[-1] == "118 / 74"
    assert run('typed(f.fmtBP, "12080".split(""))')[-1] == "120 / 80"
    assert run('typed(f.fmtBP, "9060".split(""))') == ["9", "90 / ", "90 / 6", "90 / 60"]        # two-digit top number: slash after 2 digits
    assert run('typed(f.fmtBP, "160100".split(""))')[-1] == "160 / 100"                        # three-digit bottom number
    assert run('typed(f.fmtBP, "12090".split(""))')[-1] == "120 / 90"


@node
def test_a_typed_slash_space_or_dash_also_works():
    assert run('[f.fmtBP("90/60"), f.fmtBP("90 60"), f.fmtBP("90-60"), f.fmtBP("120/80"), f.fmtBP("120 / 80"), f.fmtBP("90/")]') == \
        ["90 / 60", "90 / 60", "90 / 60", "120 / 80", "120 / 80", "90 / "]


@node
def test_blood_pressure_cannot_grow_past_sensible_lengths():
    assert run('[f.fmtBP("1201200"), f.fmtBP("12090999"), f.fmtBP("9090999")]') == ["120 / 120", "120 / 90", "90 / 90"]


@node
def test_a_digit_added_inside_the_top_number_shifts_along_instead_of_being_lost():
    assert run('[f.fmtBP("1250 / 7")]') == ["125 / 07"]           # "120 / 7" with a 5 typed after the 2
    assert run('[f.fmtBP("90 / 6")]') == ["90 / 6"]


@node
def test_backspacing_blood_pressure():
    assert run('erased(f.fmtBP, "118 / 74")') == ["118 / 7", "118", "11", "1", ""]
    assert run('erased(f.fmtBP, "90 / 60")') == ["90 / 6", "90", "9", ""]


@node
def test_junk_and_empty_input():
    assert run('[f.fmtBP(""), f.fmtBP("abc"), f.fmtDate(""), f.fmtDate("abc")]') == ["", "", "", ""]


# ---- the forms carry the hooks, and the server accepts the tidy result ----------------------------------------------------------
@pytest.mark.parametrize("field", [PatientRegistrationForm().fields["date_of_birth"], StudentRegistrationForm().fields["date_of_birth"]])
def test_date_of_birth_boxes_are_auto_formatting(field):
    a = field.widget.attrs
    assert a["data-format"] == "date" and a["maxlength"] == "10" and a["inputmode"] == "numeric" and a["autocomplete"] == "off"


def test_blood_pressure_boxes_are_auto_formatting():
    for form in (TriageForm(), TriageAmendForm()):
        a = form.fields["blood_pressure"].widget.attrs
        assert a["data-format"] == "bp" and a["maxlength"] == "9"


@pytest.mark.parametrize("text", ["10/14/1988", "10141988", "10-14-1988", "10.14.1988"])
def test_server_reads_every_common_date_shape(text):
    form = PatientRegistrationForm(data={"date_of_birth": text})
    form.is_valid()
    assert "date_of_birth" not in form.errors and str(form.cleaned_data["date_of_birth"]) == "1988-10-14"


def test_server_still_refuses_impossible_dates():
    for text in ("13/45/1988", "00/00/0000", "10/14/2999"):
        form = PatientRegistrationForm(data={"date_of_birth": text})
        form.is_valid()
        assert "date_of_birth" in form.errors, text


def test_pages_load_the_formatter(as_role):
    for role, url in (("receptionist", reverse("patient_create")), ("nurse", reverse("patient_create"))):
        html = as_role(role).get(url).content.decode()
        assert "js/format.js" in html and 'data-format="date"' in html
    from apps.history.models import Visit

    visit = Visit.objects.filter(status="registered").first()
    nurse = as_role("nurse")
    nurse.post(reverse("triage_start", args=[visit.pk]))
    assert 'data-format="bp"' in nurse.get(reverse("triage_form", args=[visit.pk])).content.decode()
