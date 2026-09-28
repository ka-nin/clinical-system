# CareBoard / CuraRecord: clinic record system

Django app: patient intake, triage and vitals, consultation notes (SOAP), prescriptions, lab results,
and role-based access with an audit trail. Roles: receptionist, nurse, physician, administrator, student (patient).

## Run it locally
    python -m venv .venv && source .venv/bin/activate
    pip install -r requirements-dev.txt   # local; requirements.txt is for the server (needs MySQL libraries)
    python manage.py migrate
    python manage.py seed_demo          # demo accounts + a sample queue (development only)
    python manage.py runserver
Demo logins are in `demo-accounts.txt`. Run the tests with `python -m pytest`.

## What each role can do
| | Receptionist | Nurse | Physician | Administrator | Student |
|---|---|---|---|---|---|
| Register patients, edit contact details, close a visit | yes | yes | yes | no | no |
| See vitals, notes, lab results, attachments | **no** | yes | yes | no | own record only, via the student portal |
| Attach PDFs, review files students send | no | yes | yes | no | students can send a PDF (held for review) |
| Triage pre-check, correct vitals, add lab results | no | yes | yes | no | no |
| Write consultation notes, prescribe | no | no | yes | no | no |
| Open a patient who is not in today's queue | needs a stated reason (logged) | same | same | n/a | n/a |
| Approve/deny staff, add/edit/deactivate users, reset 2FA, unlock accounts, read and export the audit log | no | no | no | yes (`/manage/`) | no |

## Safety features to know about
- **Allergies** are required at intake, shown as a banner on every clinical screen, and checked when prescribing.
- **Vitals** are recorded once. Mistakes are corrected with a reason; the original value is kept.
- **Reference hints and a suggested priority** come from age-based ranges in `apps/triage/assessment.py`. They are simplified
  screening aids, not a diagnosis; a clinician should review the ranges before real use. Choosing a lower level than suggested needs a reason.
- **Audit log** records who, what, when and from which IP address, including sign-ins and failed sign-ins (never what was typed). Entries are chained (each includes a fingerprint of the previous one). `python manage.py verify_audit` detects edits and gaps.
- **Nightly job:** `python manage.py close_stale_visits` closes patients who were never seen (run it from cron).

## Hosted demo (Wasmer Edge)
See **DEPLOY.md**. The database is Wasmer's MySQL; tests pass on SQLite and MySQL 8.

## Production checklist
1. Set the environment variables in `.env.example` (the app refuses to start without a real secret key, host list and PostgreSQL `DATABASE_URL`).
2. `python manage.py migrate` and `python manage.py collectstatic --noinput`.
3. `DJANGO_SETTINGS_MODULE=config.settings.prod python manage.py check --deploy`
4. Set up SMTP (`EMAIL_HOST`...) so password resets and account approvals can be emailed.
5. Staff must set up an authenticator app at first sign-in (`REQUIRE_2FA`, on by default in production).
6. Do **not** run `seed_demo` in production (it refuses unless forced).

## Known limits (be honest with your users)
- IP addresses in the audit log are the connection's address. Behind a proxy they are the proxy's, unless you set `TRUST_PROXY_HEADERS=1` (only do that if you control the proxy, otherwise visitors can fake their address).
- 'Active sessions' on the admin overview means people active in the last 5 minutes, worked out from session expiry. It is not real-time presence.
- Not certified for HIPAA/GDPR or as a medical device. Nothing here replaces a legal/compliance review.
- Data is encrypted in transit (HTTPS) only if the host serves it that way; encryption at rest depends on your database host.
- Two-step sign-in secrets and unfinished form drafts are stored in the database in plain form (drafts expire after 12 hours).
- PDF attachments are stored in the database (a disk would be lost on redeploy). Uploads are checked for size, PDF format and obvious scripts, but there is no antivirus scan: scripts hidden inside compressed PDF data would not be caught.
- Wasmer Edge deployment is rehearsed locally (same files, gunicorn, MySQL 8) but not yet run on Wasmer itself.
- The audit chain detects tampering; it does not prevent someone with database access from making it.

## Layout
- `config/`: settings (`base`, `dev`, `prod`, `test`), URLs
- `apps/accounts`: sign-in, two-step sign-in, registration, roles, dashboard, student portal, system admin (`manage_views.py`)
- `apps/patients`: directory, intake, record view, details editing
- `apps/triage`: waiting list, pre-check, corrections, reference ranges
- `apps/history`: visits, consultation notes, prescriptions, lab results
- `apps/audit`: activity log
- `tools/build_dashboard_css.py`: rebuilds `static/css/dashboard.css` (see the file header)
