"""Database tests for the business rules and the staff API permission checks."""

from datetime import date, timedelta

from django.test import TestCase
from rest_framework.test import APIClient

from care.emr.models.patient import Patient
from care.users.models import User
from care_maternal import services
from care_maternal.models import MaternalAlert, MaternalScheduleItem


class ServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create(username="maternal-test-staff")
        self.patient = Patient.objects.create(
            name="SYNTHETIC Test", phone_number="+919999000111",
            gender=2, date_of_birth=date(1995, 1, 1),
        )
        self.lmp = date.today() - timedelta(weeks=20)

    def test_creates_all_spec_items(self):
        p = services.create_pregnancy(self.patient, self.lmp, self.user, gravida=1)
        self.assertEqual(p.items.count(), 43)
        self.assertEqual(p.edd, self.lmp + timedelta(days=280))

    def test_completing_td1_sets_td2_four_weeks_later(self):
        p = services.create_pregnancy(self.patient, self.lmp, self.user)
        td1 = p.items.get(spec_id="V-TD1")
        services.complete_item(td1, date(2026, 9, 1), self.user)
        td2 = p.items.get(spec_id="V-TD2")
        self.assertEqual(td2.due_from, date(2026, 9, 29))
        self.assertEqual(td2.waiting_on, "")

    def test_sweep_raises_alerts_once(self):
        p = services.create_pregnancy(self.patient, self.lmp - timedelta(days=400), self.user)
        first = services.sweep_overdue(p)
        second = services.sweep_overdue(p)
        self.assertGreater(first, 0)
        self.assertEqual(second, 0)
        self.assertEqual(p.alerts.filter(kind="overdue").count(), first)

    def test_emergency_alerts_clinician_and_patient(self):
        p = services.create_pregnancy(self.patient, self.lmp, self.user)
        patient_alert = services.report_emergency(p, ["vaginal_bleeding"])
        self.assertEqual(patient_alert.audience, "patient")
        self.assertTrue(patient_alert.message.startswith("[DEMO]"))
        self.assertTrue(p.alerts.filter(audience="clinician", kind="emergency").exists())

    def test_completed_items_are_not_swept(self):
        p = services.create_pregnancy(self.patient, self.lmp - timedelta(days=400), self.user)
        for item in p.items.filter(due_to__isnull=False):
            services.complete_item(item, date.today(), self.user)
        self.assertEqual(services.sweep_overdue(p), 0)


class StaffApiPermissionTests(TestCase):
    def setUp(self):
        self.patient = Patient.objects.create(
            name="SYNTHETIC Perm", phone_number="+919999000222",
            gender=2, date_of_birth=date(1995, 1, 1),
        )
        self.outsider = User.objects.create(username="maternal-outsider")
        self.admin = User.objects.create(username="maternal-super", is_superuser=True)

    def test_user_without_link_gets_404(self):
        client = APIClient()
        client.force_authenticate(self.outsider)
        r = client.get(f"/api/care_maternal/pregnancies/?patient={self.patient.external_id}")
        self.assertEqual(r.status_code, 404)

    def test_superuser_can_create_and_read(self):
        client = APIClient()
        client.force_authenticate(self.admin)
        r = client.post("/api/care_maternal/pregnancies/", {
            "patient": str(self.patient.external_id), "lmp": "2026-08-01",
        }, format="json")
        self.assertEqual(r.status_code, 201)
        pid = r.json()["id"]
        self.assertEqual(client.get(f"/api/care_maternal/pregnancies/{pid}/items/").status_code, 200)
        self.assertEqual(MaternalScheduleItem.objects.filter(pregnancy__external_id=pid).count(), 43)

    def test_patient_alerts_hide_clinician_alerts(self):
        client = APIClient()
        client.force_authenticate(self.admin)
        r = client.post("/api/care_maternal/pregnancies/", {
            "patient": str(self.patient.external_id), "lmp": "2026-08-01",
        }, format="json")
        pid = r.json()["id"]
        client.post(f"/api/care_maternal/pregnancies/{pid}/emergency/",
                    {"symptoms": ["vaginal_bleeding"]}, format="json")
        staff_alerts = client.get(f"/api/care_maternal/pregnancies/{pid}/alerts/").json()
        self.assertEqual({a["audience"] for a in staff_alerts}, {"clinician", "patient"})
        self.assertGreaterEqual(MaternalAlert.objects.filter(audience="clinician").count(), 1)


class RegistrarAccessTests(TestCase):
    def setUp(self):
        from care.security.models import RoleModel
        RoleModel.objects.create(name="Doctor", is_system=True)
        self.registrar = User.objects.create(username="maternal-registrar")
        self.other = User.objects.create(username="maternal-other")
        self.patient = Patient.objects.create(
            name="SYNTHETIC Registrar", phone_number="+919999000444", gender=2,
            date_of_birth=date(1999, 1, 1), created_by=self.registrar,
        )

    def test_registrar_can_enroll_own_patient_and_is_linked(self):
        client = APIClient()
        client.force_authenticate(self.registrar)
        r = client.post("/api/care_maternal/pregnancies/", {
            "patient": str(self.patient.external_id), "lmp": "2026-08-01",
        }, format="json")
        self.assertEqual(r.status_code, 201)
        from care.emr.models.patient import PatientUser
        self.assertTrue(PatientUser.objects.filter(patient=self.patient, user=self.registrar).exists())

    def test_other_user_still_cannot_see_patient(self):
        client = APIClient()
        client.force_authenticate(self.other)
        r = client.get(f"/api/care_maternal/pregnancies/?patient={self.patient.external_id}")
        self.assertEqual(r.status_code, 404)
