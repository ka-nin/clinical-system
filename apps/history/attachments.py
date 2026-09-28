"""PDF attachments: checking what is uploaded, deciding who may see it, and serving it safely."""
import hashlib
import re

from django import forms
from django.http import HttpResponse
from django.utils import timezone
from django.utils.http import content_disposition_header

from apps.accounts.dashboard import CLINICAL_ROLES, role_of

from .models import Attachment

MAX_BYTES = 5 * 1024 * 1024
MAX_PENDING_PER_PATIENT = 5

# PDF features that can run code or smuggle other files. Legitimate clinic reports don't use them.
ACTIVE_CONTENT = (b"/JavaScript", b"/JS", b"/Launch", b"/EmbeddedFile", b"/RichMedia", b"/XFA", b"/AA", b"/SubmitForm", b"/ImportData")


def clean_filename(name):
    base = (name or "document.pdf").replace("\\", "/").split("/")[-1]
    base = re.sub(r"[^A-Za-z0-9._ -]", "_", base).strip(" .") or "document.pdf"
    if not base.lower().endswith(".pdf"):
        base += ".pdf"
    return base[:150]


def _unhide_names(raw):
    """PDF names can be written with #hex escapes (/J#61vaScript); undo that before looking for keywords."""
    return re.sub(rb"#([0-9A-Fa-f]{2})", lambda m: bytes([int(m.group(1), 16)]), raw)


def read_pdf(upload):
    """Return (bytes, filename) for a real, reasonably safe PDF, or raise ValidationError."""
    if upload.size > MAX_BYTES:
        raise forms.ValidationError(f"That file is too large. The limit is {MAX_BYTES // (1024 * 1024)} MB.")
    if not (upload.name or "").lower().endswith(".pdf"):
        raise forms.ValidationError("Only PDF files (.pdf) can be uploaded.")
    data = upload.read()
    if not data.startswith(b"%PDF-") or b"%%EOF" not in data[-2048:]:
        raise forms.ValidationError("That doesn't look like a valid PDF file.")
    visible = _unhide_names(data)
    if any(marker in visible for marker in ACTIVE_CONTENT):
        raise forms.ValidationError("That PDF contains scripts or embedded files, which aren't allowed. Export a plain copy and try again.")
    return data, clean_filename(upload.name)


class AttachmentForm(forms.Form):
    file = forms.FileField(label="PDF file", widget=forms.ClearableFileInput(attrs={"accept": "application/pdf,.pdf"}))
    category = forms.ChoiceField(label="Type", choices=Attachment.Category.choices, initial=Attachment.Category.LAB)
    description = forms.CharField(label="Short description", max_length=200, required=False,
                                  widget=forms.TextInput(attrs={"placeholder": "optional, e.g. Blood test, Sept 2026"}))
    visible_to_patient = forms.BooleanField(label="Show this in the patient's portal", required=False, initial=True)

    def __init__(self, *args, from_patient=False, **kwargs):
        super().__init__(*args, **kwargs)
        if from_patient:
            del self.fields["visible_to_patient"]

    def clean_file(self):
        self.pdf_bytes, self.pdf_name = read_pdf(self.cleaned_data["file"])
        return self.cleaned_data["file"]


def store(form, patient, user, *, source, visit=None):
    """Save a validated upload. Files from staff are accepted at once; a patient's wait for review."""
    from_patient = source == Attachment.Source.PATIENT
    return Attachment.objects.create(
        patient=patient, visit=visit, category=form.cleaned_data["category"], description=form.cleaned_data["description"].strip(),
        filename=form.pdf_name, size=len(form.pdf_bytes), sha256=hashlib.sha256(form.pdf_bytes).hexdigest(), content=form.pdf_bytes,
        source=source, uploaded_by=user,
        review_status=Attachment.Review.PENDING if from_patient else Attachment.Review.ACCEPTED,
        visible_to_patient=True if from_patient else form.cleaned_data.get("visible_to_patient", True),
    )


def can_view(user, attachment):
    """Who may open a file: clinical staff, or the student it belongs to (never a withdrawn file)."""
    if attachment.is_withdrawn or not user.is_authenticated:
        return False
    if role_of(user) in CLINICAL_ROLES:
        return True
    from apps.patients.models import Patient

    mine = Patient.objects.filter(user=user).values_list("pk", flat=True).first()
    if mine is None or attachment.patient_id != mine:
        return False
    if attachment.source == Attachment.Source.PATIENT:
        return True
    return attachment.visible_to_patient and attachment.review_status == Attachment.Review.ACCEPTED


def serve(attachment, *, inline=False):
    response = HttpResponse(bytes(attachment.content), content_type="application/pdf")
    response["Content-Disposition"] = content_disposition_header(not inline, attachment.filename)
    response["X-Content-Type-Options"] = "nosniff"
    response["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'self'"
    response["Cache-Control"] = "private, no-store"
    return response


def mark_reviewed(attachment, user, accepted, note=""):
    attachment.review_status = Attachment.Review.ACCEPTED if accepted else Attachment.Review.REJECTED
    attachment.reviewed_by, attachment.reviewed_at, attachment.review_note = user, timezone.now(), note[:255]
    attachment.save(update_fields=["review_status", "reviewed_by", "reviewed_at", "review_note"])
