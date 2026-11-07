"""DEMO ONLY: move a handover's deadline into the past so the escalation can be shown.

Refused when IS_PRODUCTION is set. Usage: manage.py demo_expire_handover <external_ref>
"""

from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from care_maternal.models import MaternalReferral


class Command(BaseCommand):
    help = "Demo only: expire a sent handover's deadline."

    def add_arguments(self, parser):
        parser.add_argument("external_ref")

    def handle(self, *args, **options):
        if settings.IS_PRODUCTION:
            raise CommandError("Refused: IS_PRODUCTION is set.")
        ref = MaternalReferral.objects.filter(external_ref=options["external_ref"], direction="out").first()
        if ref is None:
            raise CommandError("No outbound referral with that id.")
        ref.deadline_at = timezone.now() - timedelta(minutes=1)
        ref.save(update_fields=["deadline_at", "modified_date"])
        self.stdout.write(f"deadline expired for {ref.external_ref}; run the sweep to mark it incomplete")
