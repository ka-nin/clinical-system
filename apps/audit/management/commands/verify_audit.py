from django.core.management.base import BaseCommand, CommandError

from apps.audit.services import verify_chain


class Command(BaseCommand):
    help = "Check the audit log for edits, deletions or gaps. Each entry is fingerprinted together with the one before it."

    def handle(self, *args, **options):
        checked, problems = verify_chain()
        if problems:
            for line in problems:
                self.stderr.write(self.style.ERROR(line))
            raise CommandError(f"Audit log check FAILED: {len(problems)} problem(s) in {checked} entries.")
        self.stdout.write(self.style.SUCCESS(f"Audit log OK: {checked} chained entries verified."))
