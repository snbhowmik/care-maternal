"""Business rules. Views call these; nothing here knows about HTTP."""

import uuid
from datetime import date, timedelta

from django.utils import timezone
from rest_framework.exceptions import ValidationError

from care.utils.sms.message import TextMessage
from care_maternal.check_templates import active_templates
from care_maternal.models import (
    MaternalAlert,
    MaternalCheckTemplate,
    MaternalPregnancy,
    MaternalScheduleItem,
)
from care_maternal.utils.schedule import edd, ga_date, item_state, items_from_templates

# Proposed wording from spec open question Q1. Not clinically approved. Demo only.
EMERGENCY_PATIENT_TEXT = (
    "[DEMO] Please come to the clinic now. "
    "This is a test message; wording pending clinician review."
)


def link_care_team(patient, user) -> None:
    """Enroll the registering clinician on the patient, so the record is visible in CARE's own views."""
    from care.security.models import RoleModel
    from care.emr.models.patient import PatientUser

    if user is None or PatientUser.objects.filter(patient=patient, user=user).exists():
        return
    role = RoleModel.objects.filter(name="Doctor").first() or RoleModel.objects.filter(name="Staff").first()
    if role is None:
        return
    PatientUser.objects.create(patient=patient, user=user, role=role)


def create_pregnancy(patient, lmp: date, user, **obstetric) -> MaternalPregnancy:
    pregnancy = MaternalPregnancy.objects.create(
        patient=patient, lmp=lmp, edd=edd(lmp), created_by=user, **obstetric
    )
    MaternalScheduleItem.objects.bulk_create(
        [MaternalScheduleItem(pregnancy=pregnancy, **item) for item in items_from_templates(lmp, active_templates())]
    )
    return pregnancy


def complete_item(item: MaternalScheduleItem, on: date, user) -> MaternalScheduleItem:
    item.done_on = on
    item.done_by = user
    item.save(update_fields=["done_on", "done_by", "modified_date"])
    # Checks that fall due a set number of days after this one (for example Td-2, 28 days after Td-1).
    pregnancy = item.pregnancy
    for template in MaternalCheckTemplate.objects.filter(relative_to=item.spec_id, active=True, deleted=False):
        MaternalScheduleItem.objects.filter(
            pregnancy=pregnancy, spec_id=template.spec_id, done_on__isnull=True, resolution=""
        ).update(
            due_from=on + timedelta(days=template.after_days or 0),
            due_to=ga_date(pregnancy.lmp, template.to_weeks) if template.to_weeks else None,
            waiting_on="",
        )
    return item


def _release_booking(item: MaternalScheduleItem) -> None:
    """A check that is closed without a visit gives its appointment slot back."""
    booking = item.booking
    if booking is not None and booking.status == "booked":
        booking.status = "cancelled"
        booking.save(update_fields=["status", "modified_date"])
        slot = booking.token_slot
        slot.allocated = max(slot.allocated - 1, 0)
        slot.save(update_fields=["allocated", "modified_date"])
    item.booking = None


def resolve_item(item: MaternalScheduleItem, resolution: str, note: str, on_date, user) -> MaternalScheduleItem:
    """Close a check without doing it here: the patient had it elsewhere, or it is not needed for her.

    This is the doctor's decision, recorded with who made it. Nothing is deleted, and it can be reopened.
    """
    if resolution not in ("elsewhere", "not_needed"):
        raise ValidationError({"resolution": "Choose done elsewhere or not needed."})
    if item.done_on:
        raise ValidationError("This check is already done.")
    note = (note or "").strip()
    if resolution == "not_needed" and not note:
        raise ValidationError({"note": "Write why this check is not needed for this patient."})
    if on_date and on_date > timezone.localdate():
        raise ValidationError({"on_date": "The date cannot be in the future."})
    _release_booking(item)
    item.resolution = resolution
    item.resolution_note = note[:2000]
    item.resolved_on = on_date if resolution == "elsewhere" else None
    item.resolved_by = user
    item.save(update_fields=[
        "resolution", "resolution_note", "resolved_on", "resolved_by", "booking", "modified_date",
    ])
    return item


def reopen_item(item: MaternalScheduleItem) -> MaternalScheduleItem:
    """Undo a resolution: the check is open again."""
    item.resolution = ""
    item.resolution_note = ""
    item.resolved_on = None
    item.resolved_by = None
    item.overdue_alerted = False
    item.save(update_fields=[
        "resolution", "resolution_note", "resolved_on", "resolved_by", "overdue_alerted", "modified_date",
    ])
    return item


def add_custom_item(pregnancy, label: str, kind: str, due_from, due_to, user) -> MaternalScheduleItem:
    """A check added for this patient only, for example a repeat scan the doctor wants."""
    label = (label or "").strip()
    if not label:
        raise ValidationError({"label": "Write what the check is."})
    if due_from and due_to and due_to < due_from:
        raise ValidationError({"due_to": "The end date cannot be before the start date."})
    return MaternalScheduleItem.objects.create(
        pregnancy=pregnancy,
        spec_id=f"CUSTOM-{uuid.uuid4().hex[:8]}",
        kind=(kind or "visit_check").strip().lower().replace(" ", "_")[:32],
        label=label[:500],
        due_from=due_from,
        due_to=due_to,
        waiting_on="" if due_from else "clinician sets the date",
        created_by=user,
    )


def raise_alert(pregnancy, audience: str, kind: str, message: str, send_sms=False):
    alert = MaternalAlert.objects.create(
        pregnancy=pregnancy, audience=audience, kind=kind, message=message
    )
    if send_sms and pregnancy.patient.phone_number:
        sent = TextMessage(
            content=message, recipients=[pregnancy.patient.phone_number], fail_silently=True
        ).dispatch(fail_silently=True)
        alert.sms_sent = bool(sent)
        alert.save(update_fields=["sms_sent"])
    return alert


def sweep_overdue(pregnancy, today: date | None = None) -> int:
    """Create one clinician alert per newly overdue item. Returns how many were raised."""
    today = today or timezone.localdate()
    raised = 0
    for item in pregnancy.items.filter(done_on__isnull=True, resolution="", overdue_alerted=False):
        if item_state(item.due_from, item.due_to, None, today) == "overdue":
            raise_alert(
                pregnancy,
                "clinician",
                "overdue",
                f"Overdue: {item.label} (due by {item.due_to:%d %b %Y}).",
            )
            item.overdue_alerted = True
            item.save(update_fields=["overdue_alerted"])
            raised += 1
    return raised


def report_emergency(pregnancy, symptoms: list[str]) -> MaternalAlert:
    raise_alert(
        pregnancy,
        "clinician",
        "emergency",
        f"Emergency symptoms reported: {', '.join(symptoms)}. Assess now.",
    )
    return raise_alert(
        pregnancy, "patient", "emergency", EMERGENCY_PATIENT_TEXT, send_sms=True
    )


def gestational_age_on(pregnancy, on: date) -> tuple[int, int]:
    weeks, days = divmod((on - pregnancy.lmp).days, 7)
    return weeks, days
