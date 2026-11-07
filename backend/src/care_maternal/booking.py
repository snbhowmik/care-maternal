"""Book a maternal visit at a chosen time as a real CARE appointment (core TokenBooking).

The clinician picks a day, then a time from the day's slots. The patient then sees the booking
in CARE's own Appointments list, with its date and time.
"""

from datetime import datetime, time, timedelta

from django.utils import timezone
from rest_framework.exceptions import ValidationError

from care.emr.models.scheduling.booking import TokenBooking, TokenSlot
from care.emr.models.scheduling.schedule import Availability, SchedulableResource

DAY_START = time(9, 0)
DAY_END = time(17, 0)
SLOT_MINUTES = 15


def _practitioner_resource(user):
    resource = SchedulableResource.objects.filter(
        user=user, resource_type="practitioner", deleted=False
    ).first()
    if resource is None:
        raise ValidationError("You are not set up as a practitioner who takes appointments.")
    return resource


def _capacity(availability):
    return availability.tokens_per_slot if availability and availability.tokens_per_slot else 1


def _candidate_starts(on_date):
    """Every bookable start time on the day, 09:00 to the last slot before 17:00, local time."""
    start = timezone.make_aware(datetime.combine(on_date, DAY_START))
    end = timezone.make_aware(datetime.combine(on_date, DAY_END))
    step = timedelta(minutes=SLOT_MINUTES)
    starts = []
    while start + step <= end:
        starts.append(start)
        start += step
    return starts


def available_slots(user, on_date) -> list[dict]:
    """The day's slots with whether each one still has room."""
    resource = _practitioner_resource(user)
    availability = Availability.objects.filter(schedule__resource=resource, deleted=False).first()
    cap = _capacity(availability)
    day_start = timezone.make_aware(datetime.combine(on_date, time.min))
    booked = {
        slot.start_datetime: slot.allocated
        for slot in TokenSlot.objects.filter(
            resource=resource,
            deleted=False,
            start_datetime__gte=day_start,
            start_datetime__lt=day_start + timedelta(days=1),
        )
    }
    return [
        {"start": start.isoformat(), "free": booked.get(start, 0) < cap}
        for start in _candidate_starts(on_date)
    ]


def book_visit(item, on_date, start_time, user) -> TokenBooking:
    if item.booking_id and item.booking and item.booking.status == "booked":
        return item.booking  # already booked: do not create a second appointment
    resource = _practitioner_resource(user)
    availability = Availability.objects.filter(schedule__resource=resource, deleted=False).first()
    cap = _capacity(availability)

    start = timezone.make_aware(datetime.combine(on_date, start_time))
    if start not in _candidate_starts(on_date):
        raise ValidationError("Choose a time between 09:00 and 17:00 in 15-minute steps.")

    slot = TokenSlot.objects.filter(
        resource=resource, deleted=False, start_datetime=start
    ).first()
    if slot is None:
        slot = TokenSlot.objects.create(
            resource=resource,
            availability=availability,
            start_datetime=start,
            end_datetime=start + timedelta(minutes=SLOT_MINUTES),
            allocated=0,
        )
    if slot.allocated >= cap:
        raise ValidationError("That time is already taken. Choose another time.")

    booking = TokenBooking.objects.create(
        token_slot=slot,
        patient=item.pregnancy.patient,
        status="booked",
        booked_by=user,
        note=f"Maternal visit: {item.label}",
    )
    slot.allocated += 1
    slot.save(update_fields=["allocated", "modified_date"])
    item.booking = booking
    item.save(update_fields=["booking", "modified_date"])
    return booking
