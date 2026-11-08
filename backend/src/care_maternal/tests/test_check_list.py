"""Late enrolment (done elsewhere / not needed) and the clinician-editable check list."""

from datetime import date, time, timedelta

from django.test import TestCase
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.test import APIClient

from care.emr.models.organization import FacilityOrganizationUser
from care.emr.models.patient import Patient
from care.facility.models.facility import Facility
from care.security.models import RoleModel
from care.users.models import User
from care_maternal import check_templates, services, tags
from care_maternal.models import MaternalCheckTemplate


class Base(TestCase):
    def setUp(self):
        self.doctor_role, _ = RoleModel.objects.get_or_create(
            name="Doctor", defaults={"is_system": True, "contexts": ["FACILITY", "GOVT_ORG"]}
        )
        self.nurse_role, _ = RoleModel.objects.get_or_create(
            name="Nurse", defaults={"is_system": True, "contexts": ["FACILITY", "GOVT_ORG"]}
        )
        self.owner = User.objects.create(username="check-list-owner")
        self.facility = Facility.objects.create(
            name="Check list facility", facility_type=1, address="x", created_by=self.owner
        )
        self.org = self.facility.default_internal_organization
        self.doctor = self._staff("check-list-doctor", self.doctor_role)
        self.nurse = self._staff("check-list-nurse", self.nurse_role)
        self.patient = Patient.objects.create(
            name="Check List", phone_number="+919999000666", gender=2,
            date_of_birth=date(1995, 1, 1), created_by=self.doctor,
        )
        self.lmp = date.today() - timedelta(weeks=20)

    def _staff(self, username, role):
        user = User.objects.create(username=username)
        FacilityOrganizationUser.objects.create(organization=self.org, user=user, role=role)
        return user


class LateEnrolmentTests(Base):
    def setUp(self):
        super().setUp()
        self.pregnancy = services.create_pregnancy(self.patient, self.lmp, self.doctor)
        self.overdue = self.pregnancy.items.filter(due_to__lt=date.today(), done_on__isnull=True).first()

    def test_a_late_patient_starts_with_overdue_checks(self):
        self.assertIsNotNone(self.overdue)

    def test_done_elsewhere_closes_the_check_without_a_done_date(self):
        services.resolve_item(self.overdue, "elsewhere", "Done at the district hospital", None, self.doctor)
        self.overdue.refresh_from_db()
        self.assertEqual(self.overdue.resolution, "elsewhere")
        self.assertIsNone(self.overdue.done_on)
        self.assertEqual(self.overdue.resolved_by, self.doctor)

    def test_not_needed_needs_a_reason(self):
        with self.assertRaises(ValidationError):
            services.resolve_item(self.overdue, "not_needed", "  ", None, self.doctor)
        services.resolve_item(self.overdue, "not_needed", "Booked scan covers this", None, self.doctor)
        self.overdue.refresh_from_db()
        self.assertEqual(self.overdue.resolution, "not_needed")

    def test_resolved_checks_are_not_swept_as_overdue(self):
        for item in self.pregnancy.items.filter(due_to__lt=date.today()):
            services.resolve_item(item, "elsewhere", "", None, self.doctor)
        self.assertEqual(services.sweep_overdue(self.pregnancy), 0)

    def test_a_future_done_date_is_refused(self):
        with self.assertRaises(ValidationError):
            services.resolve_item(self.overdue, "elsewhere", "", date.today() + timedelta(days=2), self.doctor)

    def test_reopen_brings_the_check_back(self):
        services.resolve_item(self.overdue, "elsewhere", "", None, self.doctor)
        services.reopen_item(self.overdue)
        self.overdue.refresh_from_db()
        self.assertEqual(self.overdue.resolution, "")
        self.assertIsNone(self.overdue.resolved_by)

    def test_the_tag_goes_only_when_every_check_is_closed(self):
        tags.sync_tag(self.patient, self.facility)
        for item in self.pregnancy.items.all():
            if item.spec_id != "S-36-READY":
                services.resolve_item(item, "not_needed", "closing for test", None, self.doctor)
        tags.sync_tag(self.patient, self.facility)
        self.assertIn(self.patient, list(tags.tagged_patients(self.facility)))
        services.resolve_item(self.pregnancy.items.get(spec_id="S-36-READY"), "elsewhere", "", None, self.doctor)
        tags.sync_tag(self.patient, self.facility)
        self.assertNotIn(self.patient, list(tags.tagged_patients(self.facility)))

    def test_a_check_added_for_this_patient_only(self):
        item = services.add_custom_item(self.pregnancy, "Repeat anomaly scan", "scan", date.today(), date.today() + timedelta(days=14), self.doctor)
        self.assertTrue(item.spec_id.startswith("CUSTOM-"))
        self.assertEqual(self.pregnancy.items.count(), 44)
        other = Patient.objects.create(name="Other", phone_number="+919999000667", gender=2,
                                       date_of_birth=date(1995, 1, 1), created_by=self.doctor)
        self.assertEqual(services.create_pregnancy(other, self.lmp, self.doctor).items.count(), 43)

    def test_api_resolves_and_returns_the_state(self):
        client = APIClient()
        client.force_authenticate(self.doctor)
        response = client.post(
            f"/api/care_maternal/pregnancies/{self.pregnancy.external_id}/items/{self.overdue.spec_id}/resolve/",
            {"resolution": "elsewhere", "note": "Private lab", "on_date": str(date.today() - timedelta(days=30))},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["state"], "elsewhere")
        self.assertEqual(response.json()["resolved_on"], str(date.today() - timedelta(days=30)))


class CheckListEditorTests(Base):
    def test_the_list_is_seeded_from_the_spec_once(self):
        check_templates.ensure_templates()
        check_templates.ensure_templates()
        self.assertEqual(MaternalCheckTemplate.objects.filter(deleted=False).count(), 43)

    def test_a_retired_check_is_not_created_for_new_pregnancies(self):
        check_templates.ensure_templates()
        template = MaternalCheckTemplate.objects.get(spec_id="S-GROWTH-SCAN")
        check_templates.update_template(template, {"active": False}, self.doctor)
        pregnancy = services.create_pregnancy(self.patient, self.lmp, self.doctor)
        self.assertFalse(pregnancy.items.filter(spec_id="S-GROWTH-SCAN").exists())
        self.assertEqual(pregnancy.items.count(), 42)

    def test_a_new_check_is_created_with_its_window(self):
        template = check_templates.create_template(
            {"label": "Iron tablets review", "kind": "medication", "from_weeks": "20", "to_weeks": "24"}, self.doctor
        )
        item = services.create_pregnancy(self.patient, self.lmp, self.doctor).items.get(spec_id=template.spec_id)
        self.assertEqual(item.due_from, self.lmp + timedelta(weeks=20))
        self.assertEqual(item.due_to, self.lmp + timedelta(weeks=24))

    def test_a_check_due_after_another_follows_it(self):
        later = check_templates.create_template(
            {"label": "Review after scan", "kind": "visit_check", "relative_to": "S-ANOMALY-SCAN", "after_days": 7,
             "to_weeks": "30"}, self.doctor)
        pregnancy = services.create_pregnancy(self.patient, self.lmp, self.doctor)
        waiting = pregnancy.items.get(spec_id=later.spec_id)
        self.assertIsNone(waiting.due_from)
        services.complete_item(pregnancy.items.get(spec_id="S-ANOMALY-SCAN"), date(2026, 9, 1), self.doctor)
        waiting.refresh_from_db()
        self.assertEqual(waiting.due_from, date(2026, 9, 8))

    def test_td_two_still_follows_td_one(self):
        pregnancy = services.create_pregnancy(self.patient, self.lmp, self.doctor)
        services.complete_item(pregnancy.items.get(spec_id="V-TD1"), date(2026, 9, 1), self.doctor)
        self.assertEqual(pregnancy.items.get(spec_id="V-TD2").due_from, date(2026, 9, 29))

    def test_a_check_with_no_weeks_waits_for_the_clinician(self):
        pregnancy = services.create_pregnancy(self.patient, self.lmp, self.doctor)
        boost = pregnancy.items.get(spec_id="V-TDBOOST")
        self.assertIsNone(boost.due_from)
        self.assertIn("clinician", boost.waiting_on)

    def test_bad_weeks_and_missing_label_are_refused(self):
        with self.assertRaises(ValidationError):
            check_templates.create_template({"label": "x", "from_weeks": "20", "to_weeks": "10"}, self.doctor)
        with self.assertRaises(ValidationError):
            check_templates.create_template({"label": "x", "from_weeks": "abc"}, self.doctor)
        with self.assertRaises(ValidationError):
            check_templates.create_template({"label": "  "}, self.doctor)

    def test_a_nurse_can_read_but_not_change_the_list(self):
        client = APIClient()
        client.force_authenticate(self.nurse)
        listing = client.get("/api/care_maternal/check-templates/").json()
        self.assertFalse(listing["can_edit"])
        self.assertEqual(len(listing["results"]), 43)
        with self.assertRaises(PermissionDenied):
            check_templates.create_template({"label": "Nope"}, self.nurse)
        response = client.post("/api/care_maternal/check-templates/", {"label": "Nope"}, format="json")
        self.assertEqual(response.status_code, 403)

    def test_a_doctor_can_change_the_list_through_the_api(self):
        client = APIClient()
        client.force_authenticate(self.doctor)
        created = client.post("/api/care_maternal/check-templates/",
                              {"label": "Dental check", "kind": "visit_check", "from_weeks": "12", "to_weeks": "28"}, format="json")
        self.assertEqual(created.status_code, 201)
        patched = client.patch(f"/api/care_maternal/check-templates/{created.json()['id']}/", {"active": False}, format="json")
        self.assertEqual(patched.status_code, 200)
        self.assertFalse(patched.json()["active"])
