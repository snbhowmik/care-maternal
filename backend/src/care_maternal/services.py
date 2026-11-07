"""Business rules. Views call these; nothing here knows about HTTP."""

from datetime import date, timedelta

from django.utils import timezone

from care.utils.sms.message import TextMessage
from care_maternal.models import MaternalAlert, MaternalPregnancy, MaternalScheduleItem
from care_maternal.utils.schedule import build_items, edd, ga_date, item_state

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
        [MaternalScheduleItem(pregnancy=pregnancy, **item) for item in build_items(lmp)]
    )
    return pregnancy


def complete_item(item: MaternalScheduleItem, on: date, user) -> MaternalScheduleItem:
    item.done_on = on
    item.done_by = user
    item.save(update_fields=["done_on", "done_by", "modified_date"])
    if item.spec_id == "V-TD1":
        # Spec: Td-2 is four weeks after Td-1, ideally before 36 weeks.
        pregnancy = item.pregnancy
        MaternalScheduleItem.objects.filter(
            pregnancy=pregnancy, spec_id="V-TD2"
        ).update(
            due_from=on + timedelta(days=28),
            due_to=ga_date(pregnancy.lmp, "40"),
            waiting_on="",
        )
    return item


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
    for item in pregnancy.items.filter(done_on__isnull=True, overdue_alerted=False):
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
