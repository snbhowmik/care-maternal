"""Three synthetic maternal patients for the two-hospital escalation demo. Idempotent. Synthetic only.

1. Anita   : routine antenatal care at the rural hospital (no referral).
2. Lakshmi : referred to the district hospital; the district hospital acknowledges and examines.
3. Meena   : referred; the district hospital never acknowledges, so the handover becomes incomplete
             and the rural hospital escalates (refer again).
"""

from datetime import date, timedelta

from django.core.management.base import BaseCommand

from care.emr.models.patient import Patient, PatientUser
from care.security.models import RoleModel
from care.users.models import User
from care_maternal import services
from care_maternal.models import MaternalPregnancy

PATIENTS = [
    {"name": "SYNTHETIC Anita (routine)", "phone": "+919999100001", "weeks": 20, "gravida": 1, "para": 0, "td1_done": True},
    {"name": "SYNTHETIC Lakshmi (handover)", "phone": "+919999100002", "weeks": 28, "gravida": 3, "para": 2, "td1_done": True},
    {"name": "SYNTHETIC Meena (escalation)", "phone": "+919999100003", "weeks": 34, "gravida": 2, "para": 1, "td1_done": True},
]


class Command(BaseCommand):
    help = "Create three synthetic maternal patients for the handover demo (idempotent)."

    def handle(self, *args, **options):
        doctor = User.objects.get(username="care-doctor")
        role = RoleModel.objects.get(name="Doctor")
        for spec in PATIENTS:
            patient, created = Patient.objects.get_or_create(
                name=spec["name"],
                defaults={"phone_number": spec["phone"], "gender": 2, "date_of_birth": date(1995, 5, 5)},
            )
            PatientUser.objects.get_or_create(patient=patient, user=doctor, role=role)
            pregnancy = MaternalPregnancy.objects.filter(patient=patient, deleted=False).first()
            if pregnancy is None:
                lmp = date.today() - timedelta(weeks=spec["weeks"])
                pregnancy = services.create_pregnancy(
                    patient, lmp, doctor, gravida=spec["gravida"], para=spec["para"]
                )
                if spec["td1_done"]:
                    pregnancy.items.filter(spec_id="V-TD1").update(done_on=date.today() - timedelta(days=5))
            self.stdout.write(f"{spec['name']}: {'created' if created else 'exists'}, pregnancy {pregnancy.external_id}")
