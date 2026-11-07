"""Create a synthetic demo patient, link the demo doctor, and add one pregnancy.

Idempotent: running it again changes nothing. Synthetic data only.
"""

from datetime import date, timedelta

from django.core.management.base import BaseCommand

from care.emr.models.patient import Patient, PatientUser
from care.security.models import RoleModel
from care.users.models import User
from care_maternal import services
from care_maternal.models import MaternalPregnancy

DEMO_NAME = "SYNTHETIC Demo Patient"
DEMO_PHONE = "+919999000001"
DEMO_DOCTOR = "care-doctor"


class Command(BaseCommand):
    help = "Seed a synthetic demo patient, linked doctor, and one pregnancy (idempotent)."

    def handle(self, *args, **options):
        patient, created = Patient.objects.get_or_create(
            name=DEMO_NAME,
            defaults={
                "phone_number": DEMO_PHONE,
                "gender": 2,
                "date_of_birth": date(1995, 5, 5),
            },
        )
        self.stdout.write(f"patient {'created' if created else 'exists'}: {patient.external_id}")

        doctor = User.objects.get(username=DEMO_DOCTOR)
        role = RoleModel.objects.get(name="Doctor")
        PatientUser.objects.get_or_create(patient=patient, user=doctor, role=role)
        self.stdout.write(f"doctor linked: {DEMO_DOCTOR}")

        if MaternalPregnancy.objects.filter(patient=patient, deleted=False).exists():
            self.stdout.write("pregnancy exists: nothing to add")
            return
        lmp = date.today() - timedelta(weeks=14)  # keeps the demo current on any day
        pregnancy = services.create_pregnancy(
            patient, lmp, doctor, gravida=2, para=1, abortions=0, living=1
        )
        self.stdout.write(f"pregnancy created: {pregnancy.external_id} (LMP {lmp})")
