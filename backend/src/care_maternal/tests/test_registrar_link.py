"""A newly registered patient is linked to the staff member who registered them."""

from datetime import date

from django.test import TestCase

from care.emr.models.patient import Patient, PatientUser
from care.security.models import RoleModel
from care.users.models import User


class RegistrarLinkTests(TestCase):
    def setUp(self):
        RoleModel.objects.get_or_create(name="Doctor", defaults={"is_system": True})
        self.user = User.objects.create(username="maternal-registrar")

    def test_registering_links_the_registrar(self):
        with self.captureOnCommitCallbacks(execute=True):
            patient = Patient.objects.create(
                name="Registrar Link", phone_number="+919999000555", gender=2,
                date_of_birth=date(1995, 1, 1), created_by=self.user,
            )
        self.assertTrue(PatientUser.objects.filter(patient=patient, user=self.user).exists())

    def test_saving_again_does_not_duplicate_the_link(self):
        with self.captureOnCommitCallbacks(execute=True):
            patient = Patient.objects.create(
                name="Registrar Link", phone_number="+919999000556", gender=2,
                date_of_birth=date(1995, 1, 1), created_by=self.user,
            )
        with self.captureOnCommitCallbacks(execute=True):
            patient.save()
        self.assertEqual(PatientUser.objects.filter(patient=patient, user=self.user).count(), 1)
