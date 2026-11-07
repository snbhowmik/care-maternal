"""The Maternal tag: set at enrolment, kept while checks are open, removed after the last one."""

from datetime import date, timedelta

from django.test import TestCase
from rest_framework.test import APIClient

from care.emr.models.patient import Patient
from care.facility.models.facility import Facility
from care.users.models import User
from care_maternal import services, tags


class MaternalTagTests(TestCase):
    def setUp(self):
        self.user = User.objects.create(username="maternal-tag-staff")
        self.facility = Facility.objects.create(
            name="Tag test facility", facility_type=1, address="x", created_by=self.user
        )
        self.patient = Patient.objects.create(
            name="SYNTHETIC Tag", phone_number="+919999000222",
            gender=2, date_of_birth=date(1995, 1, 1), created_by=self.user,
        )
        self.lmp = date.today() - timedelta(weeks=20)

    def _has_tag(self):
        return self.patient in list(tags.tagged_patients(self.facility))

    def test_enrolment_tags_patient_while_checks_open(self):
        services.create_pregnancy(self.patient, self.lmp, self.user)
        tags.sync_tag(self.patient, self.facility)
        self.assertTrue(self._has_tag())

    def test_tag_removed_after_last_check(self):
        p = services.create_pregnancy(self.patient, self.lmp, self.user)
        tags.sync_tag(self.patient, self.facility)
        for item in p.items.all():
            services.complete_item(item, date.today(), self.user)
        tags.sync_tag(self.patient, self.facility)
        self.assertFalse(self._has_tag())

    def test_tag_kept_while_one_check_remains(self):
        p = services.create_pregnancy(self.patient, self.lmp, self.user)
        for item in list(p.items.all())[:-1]:
            services.complete_item(item, date.today(), self.user)
        tags.sync_tag(self.patient, self.facility)
        self.assertTrue(self._has_tag())

    def test_worklist_lists_tagged_patients_with_open_checks(self):
        services.create_pregnancy(self.patient, self.lmp, self.user)
        tags.sync_tag(self.patient, self.facility)
        client = APIClient()
        client.force_authenticate(self.user)
        response = client.get(
            "/api/care_maternal/pregnancies/worklist/",
            {"facility": str(self.facility.external_id)},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)
        row = response.json()[0]
        self.assertEqual(row["patient_name"], "SYNTHETIC Tag")
        self.assertGreater(row["open_checks"], 0)
