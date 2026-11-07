from django.core.management.base import BaseCommand

from care_maternal.access import grant_all_staff


class Command(BaseCommand):
    help = "Give every staff member at this hospital access to all patients registered here. Idempotent."

    def handle(self, *args, **options):
        self.stdout.write(f"Region roles added: {grant_all_staff()}")
