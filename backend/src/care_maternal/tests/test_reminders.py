"""Reminders by priority: who, how early, how often, and never for optional checks."""

from datetime import date, datetime, time, timedelta
from unittest import mock
from zoneinfo import ZoneInfo

from django.test import TestCase
from rest_framework.test import APIClient

from care.emr.models.organization import FacilityOrganizationUser
from care.emr.models.patient import Patient
from care.facility.models.facility import Facility
from care.security.models import RoleModel
from care.users.models import User
from care_maternal import duty, reminders, services, tags
from care_maternal.models import MaternalAlert, MaternalDuty

IST = ZoneInfo("Asia/Kolkata")


def at(day: date, hour: int) -> datetime:
    return datetime.combine(day, time(hour, 0), tzinfo=IST)


class Base(TestCase):
    def setUp(self):
        roles = {}
        for name in ("Doctor", "Nurse", "ASHA Worker", "Staff"):
            roles[name], _ = RoleModel.objects.get_or_create(
                name=name, defaults={"is_system": True, "contexts": ["FACILITY", "GOVT_ORG"]}
            )
        self.owner = User.objects.create(username="reminder-owner")
        self.facility = Facility.objects.create(
            name="Reminder facility", facility_type=1, address="x", created_by=self.owner
        )
        org = self.facility.default_internal_organization
        self.doctor = self._staff("rem-doctor", roles["Doctor"], org, "+919999100001")
        self.nurse = self._staff("rem-nurse", roles["Nurse"], org, "+919999100002")
        self.asha = self._staff("rem-asha", roles["ASHA Worker"], org, "+919999100003")
        self.clerk = self._staff("rem-clerk", roles["Staff"], org, "")
        self.patient = Patient.objects.create(
            name="Reminder Patient", phone_number="+919999000888", gender=2,
            date_of_birth=date(1995, 1, 1), created_by=self.doctor,
        )
        self.today = date.today()
        # LMP chosen so nothing is due yet; each test sets the item it cares about.
        self.pregnancy = services.create_pregnancy(self.patient, self.today - timedelta(weeks=5), self.doctor)
        self.pregnancy.items.update(priority="optional")
        self.item = self.pregnancy.items.get(spec_id="V-TD1")

    def on_duty(self, user):
        """On duty for a wide window, so the simulated sweep times fall inside it."""
        now = at(self.today, 12)
        return MaternalDuty.objects.create(user=user, since=now - timedelta(days=1), until=now + timedelta(days=3))

    def _staff(self, username, role, org, phone):
        user = User.objects.create(username=username, phone_number=phone or "")
        FacilityOrganizationUser.objects.create(organization=org, user=user, role=role)
        return user

    def due(self, priority, days_until_due=0, window=14):
        self.item.priority = priority
        self.item.due_from = self.today + timedelta(days=days_until_due)
        self.item.due_to = self.item.due_from + timedelta(days=window)
        self.item.save()
        self.item.refresh_from_db()

    def sweep(self, hour=10, day=None):
        with mock.patch.object(reminders, "_send", return_value=True):
            return reminders.sweep_reminders(at(day or self.today, hour))

    def staff_alerts(self):
        return MaternalAlert.objects.filter(pregnancy=self.pregnancy, audience="staff")

    def patient_alerts(self):
        return MaternalAlert.objects.filter(pregnancy=self.pregnancy, audience="patient", kind="reminder")


class WhoIsRemindedTests(Base):
    def test_everyone_on_duty_is_reminded_and_others_are_not(self):
        self.on_duty(self.doctor)
        self.on_duty(self.nurse)
        self.due("high")
        self.sweep()
        self.assertEqual(set(self.staff_alerts().values_list("recipient__username", flat=True)), {"rem-doctor", "rem-nurse"})
        self.assertEqual(self.patient_alerts().count(), 1)

    def test_other_roles_are_not_in_the_team(self):
        self.on_duty(self.clerk)
        self.assertNotIn(self.clerk, duty.team())

    def test_nobody_on_duty_notifies_the_whole_team_so_it_is_never_lost(self):
        self.due("high")
        self.sweep()
        self.assertEqual(
            set(self.staff_alerts().values_list("recipient__username", flat=True)),
            {"rem-doctor", "rem-nurse", "rem-asha"},
        )
        self.assertIn("Nobody is marked on duty", self.staff_alerts().first().message)

    def test_duty_expires_after_the_shift(self):
        duty.go_on_duty(self.doctor, at(self.today, 8))
        self.assertTrue(duty.is_on_duty(self.doctor, at(self.today, 15)))
        self.assertFalse(duty.is_on_duty(self.doctor, at(self.today, 8) + timedelta(hours=duty.DUTY_HOURS + 1)))

    def test_going_off_duty_stops_reminders_to_that_person(self):
        self.on_duty(self.doctor)
        self.on_duty(self.nurse)
        MaternalDuty.objects.filter(user=self.doctor).update(ended_at=at(self.today, 6))
        self.due("high")
        self.sweep()
        self.assertEqual(set(self.staff_alerts().values_list("recipient__username", flat=True)), {"rem-nurse"})


class HowOftenTests(Base):
    def setUp(self):
        super().setUp()
        self.on_duty(self.doctor)

    def test_high_is_early_and_repeats_up_to_three_times_a_day(self):
        self.due("high", days_until_due=3)
        self.assertEqual(self.sweep(8), 2)       # one for the doctor, one for the patient
        self.assertEqual(self.sweep(10), 0)      # too soon: 4 hours apart
        self.assertEqual(self.sweep(12), 2)
        self.assertEqual(self.sweep(16), 2)
        self.assertEqual(self.sweep(19), 0)      # three a day is the limit
        self.assertEqual(self.sweep(9, self.today + timedelta(days=1)), 2)   # the next day starts again

    def test_high_is_not_sent_before_its_lead_time(self):
        self.due("high", days_until_due=4)
        self.assertEqual(self.sweep(), 0)

    def test_medium_is_sent_twice_a_day_and_one_day_early(self):
        self.due("medium", days_until_due=1)
        self.assertEqual(self.sweep(9), 2)
        self.assertEqual(self.sweep(12), 0)      # 6 hours apart
        self.assertEqual(self.sweep(15), 2)
        self.assertEqual(self.sweep(19), 0)      # twice a day
        self.due("medium", days_until_due=2)
        self.item.reminders_sent = 0; self.item.last_reminded_at = None; self.item.reminders_today = 0
        self.item.save()
        self.assertEqual(self.sweep(9), 0)       # two days early: too soon for medium

    def test_low_is_sent_once_on_the_due_date_and_never_early_or_again(self):
        self.due("low", days_until_due=1)
        self.assertEqual(self.sweep(), 0)        # not earlier
        self.due("low", days_until_due=0)
        self.assertEqual(self.sweep(10), 2)
        self.assertEqual(self.sweep(19), 0)
        self.assertEqual(self.sweep(10, self.today + timedelta(days=1)), 0)
        self.assertEqual(self.patient_alerts().count(), 1)

    def test_optional_is_never_reminded(self):
        self.due("optional", days_until_due=0)
        self.assertEqual(self.sweep(), 0)
        self.assertEqual(MaternalAlert.objects.filter(pregnancy=self.pregnancy, kind="reminder").count(), 0)

    def test_no_reminders_at_night(self):
        self.due("high", days_until_due=0)
        self.assertEqual(self.sweep(2), 0)
        self.assertEqual(self.sweep(21), 0)
        self.assertGreater(self.sweep(9), 0)

    def test_a_check_that_is_done_or_closed_is_not_reminded(self):
        self.due("high", days_until_due=0)
        services.complete_item(self.item, self.today, self.doctor)
        self.assertEqual(self.sweep(), 0)

    def test_a_booked_appointment_stops_the_reminder(self):
        self.due("high", days_until_due=0)
        with mock.patch.object(reminders, "_booked", return_value=True):
            self.assertEqual(self.sweep(), 0)

    def test_reminders_stop_long_after_the_due_date(self):
        self.due("medium", days_until_due=-30, window=3)
        self.assertEqual(self.sweep(), 0)

    def test_one_message_covers_all_of_a_patients_due_checks(self):
        other = self.pregnancy.items.get(spec_id="V-TD2")
        other.priority, other.due_from, other.due_to = "high", self.today, self.today + timedelta(days=10)
        other.save()
        self.due("medium", days_until_due=0)
        self.sweep()
        self.assertEqual(self.staff_alerts().count(), 1)
        self.assertEqual(self.staff_alerts().first().message.count("check(s) due"), 1)
        self.assertIn("2 check(s)", self.staff_alerts().first().message)
        self.assertTrue(self.staff_alerts().first().message.startswith("High priority"))


class OptionalChecksAreNotMandatoryTests(Base):
    def test_open_optional_checks_do_not_keep_the_tag(self):
        self.pregnancy.items.update(priority="optional")
        tags.sync_tag(self.patient, self.facility)
        self.assertNotIn(self.patient, list(tags.tagged_patients(self.facility)))

    def test_a_mandatory_open_check_does_keep_it(self):
        self.pregnancy.items.update(priority="optional")
        self.pregnancy.items.filter(spec_id="V-TD1").update(priority="low")
        tags.sync_tag(self.patient, self.facility)
        self.assertIn(self.patient, list(tags.tagged_patients(self.facility)))

    def test_optional_checks_are_not_swept_as_overdue(self):
        self.pregnancy.items.update(priority="optional", due_from=self.today - timedelta(days=30), due_to=self.today - timedelta(days=10))
        self.assertEqual(services.sweep_overdue(self.pregnancy), 0)


class ApiTests(Base):
    def test_duty_switch_and_feed(self):
        client = APIClient()
        client.force_authenticate(self.doctor)
        self.assertFalse(client.get("/api/care_maternal/duty/").json()["mine"])
        on = client.post("/api/care_maternal/duty/", {"on": True}, format="json").json()
        self.assertTrue(on["mine"])
        self.assertEqual([p["name"] for p in on["on_duty"]], ["rem-doctor"])
        self.due("high")
        self.on_duty(self.doctor)   # the real switch starts now; widen it so the simulated sweep time is inside
        self.sweep()
        feed = client.get("/api/care_maternal/reminders/").json()
        self.assertEqual(len(feed), 1)
        self.assertEqual(feed[0]["patient_name"], "Reminder Patient")
        self.assertFalse(feed[0]["acknowledged"])
        client.post(f"/api/care_maternal/reminders/{feed[0]['id']}/acknowledge/")
        self.assertTrue(client.get("/api/care_maternal/reminders/").json()[0]["acknowledged"])
        off = client.post("/api/care_maternal/duty/", {"on": False}, format="json").json()
        self.assertFalse(off["mine"])

    def test_a_person_only_sees_their_own_reminders(self):
        self.on_duty(self.doctor)
        self.due("high")
        self.sweep()
        client = APIClient()
        client.force_authenticate(self.nurse)
        self.assertEqual(client.get("/api/care_maternal/reminders/").json(), [])

    def test_the_patients_alert_list_has_no_per_person_duplicates(self):
        self.on_duty(self.doctor)
        self.on_duty(self.nurse)
        self.due("high")
        self.sweep()
        client = APIClient()
        client.force_authenticate(self.doctor)
        alerts = client.get(f"/api/care_maternal/pregnancies/{self.pregnancy.external_id}/alerts/").json()
        self.assertTrue(all(a["audience"] != "staff" for a in alerts))

    def test_priority_is_set_and_validated_on_the_check_list(self):
        client = APIClient()
        client.force_authenticate(self.doctor)
        created = client.post("/api/care_maternal/check-templates/",
                              {"label": "Urgent BP", "priority": "high", "from_weeks": "20", "to_weeks": "30"}, format="json")
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.json()["priority"], "high")
        bad = client.post("/api/care_maternal/check-templates/", {"label": "x", "priority": "urgent"}, format="json")
        self.assertEqual(bad.status_code, 400)
        item = services.create_pregnancy(
            Patient.objects.create(name="P2", phone_number="+919999000889", gender=2,
                                   date_of_birth=date(1995, 1, 1), created_by=self.doctor),
            self.today - timedelta(weeks=5), self.doctor,
        ).items.get(spec_id=created.json()["spec_id"])
        self.assertEqual(item.priority, "high")
