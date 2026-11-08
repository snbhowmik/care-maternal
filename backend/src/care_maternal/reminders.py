"""Reminders for open checks. Priority decides how early, how often, and how long.

  high      reminded 3 days before it is due, up to 3 times a day (4 hours apart), until it is recorded
            (for 14 days past the due date). Staff on duty also get an SMS.
  medium    reminded 1 day before it is due, twice a day (6 hours apart), for 7 days past the due date.
  low       reminded once, on the due date. Never earlier, never again.
  optional  never reminded. The record is not mandatory.

Everyone on duty (doctors, nurses and the other notify roles) and the patient are reminded.
These numbers are defaults awaiting clinician review. Reminders go out between 08:00 and 20:00.
A patient who has a booked appointment for the check is not reminded to come.
"""

from datetime import timedelta

from django.utils import timezone

from care.utils.sms.message import TextMessage
from care_maternal import duty
from care_maternal.models import MaternalAlert, MaternalScheduleItem
from care_maternal.settings import plugin_settings

RULES = {
    "high": {"lead_days": 3, "per_day": 3, "gap_hours": 4, "max_total": None, "overdue_days": 14, "staff_sms": True},
    "medium": {"lead_days": 1, "per_day": 2, "gap_hours": 6, "max_total": None, "overdue_days": 7, "staff_sms": False},
    "low": {"lead_days": 0, "per_day": 1, "gap_hours": 24, "max_total": 1, "overdue_days": 0, "staff_sms": False},
}
ORDER = ("high", "medium", "low")
WINDOW_START, WINDOW_END = 8, 20  # local hours; shortcut: fixed, make a plugin setting if hospitals differ

PATIENT_TEXT = "[DEMO] Reminder from {facility}: you have {n} health check(s) due. Please visit the clinic. Wording pending clinician review."


def _booked(item) -> bool:
    return bool(item.booking_id and item.booking and item.booking.status == "booked")


def _eligible(item, now, today) -> bool:
    rule = RULES.get(item.priority)
    if rule is None or item.due_from is None or _booked(item):
        return False
    if today < item.due_from - timedelta(days=rule["lead_days"]):
        return False
    if item.due_to and today > item.due_to + timedelta(days=rule["overdue_days"]):
        return False
    if rule["max_total"] is not None and item.reminders_sent >= rule["max_total"]:
        return False
    sent_today = item.reminders_today if item.reminders_today_on == today else 0
    if sent_today >= rule["per_day"]:
        return False
    if item.last_reminded_at and now - item.last_reminded_at < timedelta(hours=rule["gap_hours"]):
        return False
    return True


def _staff_message(pregnancy, items, nobody_on_duty: bool) -> str:
    top = min((i.priority for i in items), key=ORDER.index)
    parts = "; ".join(f"{i.label} ({i.priority})" for i in items[:6])
    more = f" and {len(items) - 6} more" if len(items) > 6 else ""
    name = pregnancy.patient.name
    note = " Nobody is marked on duty, so the whole team is told." if nobody_on_duty else ""
    return f"{top.capitalize()} priority: {name} has {len(items)} check(s) due: {parts}{more}.{note}"


def _send(phone, content) -> bool:
    if not phone:
        return False
    return bool(TextMessage(content=content, recipients=[phone], fail_silently=True).dispatch(fail_silently=True))


def _remind(pregnancy, items, now) -> int:
    """One message per person for this pregnancy, covering all its due checks. Returns alerts raised."""
    staff, nobody_on_duty = duty.recipients(now)
    message = _staff_message(pregnancy, items, nobody_on_duty)
    sms_staff = any(RULES[i.priority]["staff_sms"] for i in items)
    raised = 0
    for person in staff:
        alert = MaternalAlert.objects.create(
            pregnancy=pregnancy, audience="staff", recipient=person, kind="reminder", message=message,
        )
        if sms_staff and _send(person.phone_number, message):
            alert.sms_sent = True
            alert.save(update_fields=["sms_sent"])
        raised += 1
    patient_alert = MaternalAlert.objects.create(
        pregnancy=pregnancy, audience="patient", kind="reminder",
        message=PATIENT_TEXT.format(facility=plugin_settings.MATERNAL_FACILITY_NAME, n=len(items)),
    )
    if _send(pregnancy.patient.phone_number, patient_alert.message):
        patient_alert.sms_sent = True
        patient_alert.save(update_fields=["sms_sent"])
    return raised + 1


def sweep_reminders(now=None) -> int:
    """Send the reminders that are due. Safe to run often: each check keeps its own count and timing."""
    now = now or timezone.now()
    local = timezone.localtime(now)
    if not WINDOW_START <= local.hour < WINDOW_END:
        return 0
    today = local.date()
    open_items = (
        MaternalScheduleItem.objects.filter(
            deleted=False, done_on__isnull=True, resolution="", priority__in=ORDER,
            pregnancy__deleted=False, pregnancy__status="active",
        )
        .select_related("pregnancy__patient", "booking")
        .order_by("pregnancy_id", "due_from")
    )
    by_pregnancy: dict = {}
    for item in open_items:
        if _eligible(item, now, today):
            by_pregnancy.setdefault(item.pregnancy_id, []).append(item)
    sent = 0
    for items in by_pregnancy.values():
        sent += _remind(items[0].pregnancy, items, now)
        for item in items:
            item.reminders_today = (item.reminders_today if item.reminders_today_on == today else 0) + 1
            item.reminders_today_on = today
            item.reminders_sent += 1
            item.last_reminded_at = now
            item.save(update_fields=[
                "reminders_today", "reminders_today_on", "reminders_sent", "last_reminded_at", "modified_date",
            ])
    return sent
