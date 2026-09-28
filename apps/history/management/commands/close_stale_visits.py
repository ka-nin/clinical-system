from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.audit.services import log
from apps.history.models import Visit


class Command(BaseCommand):
    help = (
        "Close visits that were never seen: patients still 'Registered' or 'In Triage' many hours after arriving. "
        "They are marked 'Left Without Being Seen' (nothing is deleted). Visits already with a doctor are left alone. "
        "Run it every night, for example with cron."
    )

    def add_arguments(self, parser):
        parser.add_argument("--hours", type=int, default=16, help="Close waiting visits older than this many hours (default 16).")
        parser.add_argument("--dry-run", action="store_true", help="Only list what would be closed.")

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(hours=options["hours"])
        stale = Visit.objects.waiting().filter(registered_at__lt=cutoff).select_related("patient")
        count = 0
        for visit in stale:
            self.stdout.write(f"{'Would close' if options['dry_run'] else 'Closing'}: {visit.patient.full_name} ({visit.patient.code}), waiting since {visit.registered_at:%Y-%m-%d %H:%M}")
            if options["dry_run"]:
                continue
            visit.status = Visit.Status.LEFT
            visit.closed_reason = f"Closed automatically: still waiting after {options['hours']} hours."
            visit.save(update_fields=["status", "closed_reason"])
            log(None, "SYSTEM", f"closed the stale visit of {visit.patient.full_name} (waiting over {options['hours']} hours)", visit.patient)
            count += 1
        self.stdout.write(self.style.SUCCESS(f"{count} visit(s) closed."))
