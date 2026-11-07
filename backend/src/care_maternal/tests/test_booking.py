"""Booking at a chosen time: the day's slots, a booked time, and a time already taken."""

from datetime import date, time, timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from care.emr.models.patient import Patient
from care.emr.models.scheduling.booking import TokenSlot
from care.emr.models.scheduling.schedule import Availability, Schedule, SchedulableResource
from care.facility.models.facility import Facility
from care.users.models import User
from care_maternal import booking, services


class ChosenTimeBookingTests(TestCase):
    def setUp(self):
        self.user = User.objects.create(username="maternal-booking-doctor")
        self.facility = Facility.objects.create(
            name="Booking test facility", facility_type=1, address="x", created_by=self.user
        )
        self.resource = SchedulableResource.objects.create(
            facility=self.facility, resource_type="practitioner", user=self.user
        )
        self.schedule = Schedule.objects.create(resource=self.resource, name="OPD", valid_from=date.today(), valid_to=date.today() + timedelta(days=365))
        Availability.objects.create(
            schedule=self.schedule, name="OPD hours", slot_type="appointment",
            slot_size_in_minutes=15, tokens_per_slot=1,
        )
        self.patient = Patient.objects.create(
            name="Booking Test", phone_number="+919999000333",
            gender=2, date_of_birth=date(1995, 1, 1), created_by=self.user,
        )
        self.pregnancy = services.create_pregnancy(self.patient, date.today() - timedelta(weeks=20), self.user)
        self.item = self.pregnancy.items.get(spec_id="V-TD1")
        self.day = date.today() + timedelta(days=1)

    def test_day_lists_fifteen_minute_slots_from_nine_to_five(self):
        slots = booking.available_slots(self.user, self.day)
        self.assertEqual(len(slots), 32)
        self.assertTrue(all(s["free"] for s in slots))

    def test_booking_takes_the_chosen_time(self):
        booking.book_visit(self.item, self.day, time(10, 30), self.user)
        self.item.refresh_from_db()
        self.assertEqual(timezone.localtime(self.item.booking.token_slot.start_datetime).hour, 10)
        self.assertEqual(timezone.localtime(self.item.booking.token_slot.start_datetime).minute, 30)
        taken = [s for s in booking.available_slots(self.user, self.day) if not s["free"]]
        self.assertEqual(len(taken), 1)

    def test_taken_time_is_refused(self):
        booking.book_visit(self.item, self.day, time(10, 30), self.user)
        other = self.pregnancy.items.get(spec_id="V-TD2")
        with self.assertRaises(ValidationError):
            booking.book_visit(other, self.day, time(10, 30), self.user)

    def test_time_outside_clinic_hours_is_refused(self):
        with self.assertRaises(ValidationError):
            booking.book_visit(self.item, self.day, time(18, 0), self.user)
