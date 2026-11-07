"""No-show: the visit is due again, three misses raise a home visit, and the sweep marks missed visits."""

from datetime import date, time, timedelta

from django.test import TestCase
from django.utils import timezone

from care.emr.models.patient import Patient
from care.emr.models.scheduling.schedule import Availability, Schedule, SchedulableResource
from care.facility.models.facility import Facility
from care.users.models import User
from care_maternal import booking, no_show, services
from care_maternal.models import MaternalAlert, MaternalHomeVisit


class NoShowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create(username="maternal-noshow-doctor")
        self.facility = Facility.objects.create(
            name="No-show test facility", facility_type=1, address="x", created_by=self.user
        )
        self.resource = SchedulableResource.objects.create(
            facility=self.facility, resource_type="practitioner", user=self.user
        )
        schedule = Schedule.objects.create(
            resource=self.resource, name="OPD", valid_from=date.today(),
            valid_to=date.today() + timedelta(days=365),
        )
        Availability.objects.create(
            schedule=schedule, name="OPD hours", slot_type="appointment",
            slot_size_in_minutes=15, tokens_per_slot=1,
        )
        self.patient = Patient.objects.create(
            name="No-show Test", phone_number="+919999000444", gender=2,
            date_of_birth=date(1995, 1, 1), created_by=self.user, address="12 Test Road",
        )
        self.pregnancy = services.create_pregnancy(self.patient, date.today() - timedelta(weeks=20), self.user)
        self.item = self.pregnancy.items.get(spec_id="V-TD1")
        self.day = date.today() + timedelta(days=1)

    def _book(self, item, at=time(10, 0)):
        booking.book_visit(item, self.day, at, self.user)
        item.refresh_from_db()
        return item

    def test_manual_no_show_makes_visit_due_again(self):
        item = self._book(self.item)
        no_show.mark_no_show(item)
        item.refresh_from_db()
        self.assertEqual(item.no_show_count, 1)
        self.assertIsNone(item.booking_id)
        self.assertEqual(item.due_from, timezone.localdate())
        self.assertTrue(MaternalAlert.objects.filter(pregnancy=self.pregnancy, kind="no_show").exists())

    def test_third_no_show_raises_home_visit_with_address(self):
        for n in range(3):
            item = self.pregnancy.items.get(spec_id="V-TD1")
            self._book(item, time(9 + n, 0))
            no_show.mark_no_show(item)
        visits = MaternalHomeVisit.objects.filter(pregnancy=self.pregnancy)
        self.assertEqual(visits.count(), 1)
        self.assertIn("12 Test Road", visits.get().address)
        self.assertTrue(MaternalAlert.objects.filter(pregnancy=self.pregnancy, kind="home_visit").exists())

    def test_sweep_marks_missed_visit_after_grace_period(self):
        item = self._book(self.item)
        slot_end = item.booking.token_slot.end_datetime
        self.assertEqual(no_show.sweep_no_shows(now=slot_end + timedelta(minutes=5)), 0)
        self.assertEqual(no_show.sweep_no_shows(now=slot_end + timedelta(minutes=45)), 1)
        item.refresh_from_db()
        self.assertEqual(item.no_show_count, 1)
