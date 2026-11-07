"""No-shows: a missed appointment makes the visit due again. Repeated misses send an ASHA home visit.

- A clinician can mark a booked visit as no-show.
- The sweep does it automatically once the appointment time has passed by the grace period and
  the visit is still not recorded. The clinician is alerted, so they can correct it.
- At NO_SHOW_LIMIT misses on the same check, a home visit is raised for the same day and
  assigned to an ASHA worker at the hospital, if one is set up.
"""

from datetime import timedelta

from django.utils import timezone
from rest_framework.exceptions import ValidationError

from care.emr.models.organization import FacilityOrganizationUser
from care_maternal import services
from care_maternal.models import MaternalHomeVisit, MaternalScheduleItem

NO_SHOW_LIMIT = 3
GRACE_MINUTES = 30  # shortcut: a fixed grace period; upgrade: make it a plugin setting per hospital
ASHA_ROLE = "ASHA Worker"


def _asha_link(facility):
    return (
        FacilityOrganizationUser.objects.filter(organization__facility=facility, role__name=ASHA_ROLE)
        .select_related("user")
        .first()
    )


def _patient_address(patient) -> str:
    parts = [patient.address or patient.permanent_address]
    if patient.geo_organization_id:
        parts.append(patient.geo_organization.name)
    if patient.pincode:
        parts.append(str(patient.pincode))
    return ", ".join(p for p in parts if p)


def _assign_home_visit(pregnancy, item, facility, today):
    link = _asha_link(facility)
    visit = MaternalHomeVisit.objects.create(
        pregnancy=pregnancy,
        spec_id=item.spec_id,
        reason=f"{item.no_show_count} missed appointments for {item.label}",
        address=_patient_address(pregnancy.patient),
        due_on=today,
        assigned_to=link.user if link else None,
    )
    if link is None:
        services.raise_alert(
            pregnancy, "clinician", "home_visit",
            "Home visit needed, but no ASHA worker is set up at this hospital. Assign one.",
        )
    else:
        services.raise_alert(
            pregnancy, "clinician", "home_visit",
            f"ASHA home visit raised for today, assigned to {link.user.username}.",
        )
    return visit


def mark_no_show(item, actor=None, automatic=False) -> MaternalScheduleItem:
    """The patient did not come. The visit becomes due today, and the appointment is kept as no-show."""
    booking = item.booking
    if booking is None or booking.status != "booked":
        raise ValidationError("Only a booked visit can be marked as a no-show.")
    facility = booking.token_slot.resource.facility
    today = timezone.localdate()

    booking.status = "noshow"
    booking.save(update_fields=["status", "modified_date"])
    item.no_show_count += 1
    item.booking = None
    item.due_from = today
    item.due_to = today
    item.save(update_fields=["no_show_count", "booking", "due_from", "due_to", "modified_date"])

    who = "Marked as no-show automatically after the appointment time" if automatic else "Marked as no-show"
    services.raise_alert(
        item.pregnancy, "clinician", "no_show",
        f"{who}: {item.label}. The visit is due again.",
    )
    pregnancy = item.pregnancy
    open_visit = pregnancy.home_visits.filter(deleted=False, visited_on__isnull=True).exists()
    if item.no_show_count >= NO_SHOW_LIMIT and not open_visit:
        _assign_home_visit(pregnancy, item, facility, today)
    return item


def sweep_no_shows(now=None) -> int:
    """Mark booked visits as no-show when the appointment time passed and nothing was recorded."""
    now = now or timezone.now()
    cutoff = now - timedelta(minutes=GRACE_MINUTES)
    overdue = MaternalScheduleItem.objects.filter(
        deleted=False,
        done_on__isnull=True,
        booking__status="booked",
        booking__token_slot__end_datetime__lt=cutoff,
    ).select_related("pregnancy__patient", "booking__token_slot__resource__facility")
    count = 0
    for item in overdue:
        mark_no_show(item, automatic=True)
        count += 1
    return count
