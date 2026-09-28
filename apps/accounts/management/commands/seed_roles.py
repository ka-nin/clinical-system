from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand

ROLES = ["ClinicStaff", "Administrator", "Student"]


class Command(BaseCommand):
    help = "Create the three user roles (groups). Safe to run repeatedly."

    def handle(self, *args, **options):
        for name in ROLES:
            _, created = Group.objects.get_or_create(name=name)
            self.stdout.write(f"{'Created' if created else 'Exists '} {name}")
