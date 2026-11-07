from django.core.management.base import BaseCommand, CommandError

from care.facility.models.facility import Facility
from care_maternal import tags
from care_maternal.models import MaternalPregnancy


class Command(BaseCommand):
    help = (
        "Set or clear the Maternal tag at one hospital so it matches open checks. "
        "Use it once after deploying the tag, to cover pregnancies made before it existed."
    )

    def add_arguments(self, parser):
        parser.add_argument("--facility", required=True, help="Facility external id (UUID)")

    def handle(self, *args, **options):
        facility = Facility.objects.filter(external_id=options["facility"]).first()
        if facility is None:
            raise CommandError("No facility with that id.")
        pregnancies = MaternalPregnancy.objects.filter(deleted=False).select_related("patient")
        for pregnancy in pregnancies:
            tags.sync_tag(pregnancy.patient, facility)
        self.stdout.write(f"Synced the Maternal tag for {len(pregnancies)} pregnancies at {facility.name}.")
