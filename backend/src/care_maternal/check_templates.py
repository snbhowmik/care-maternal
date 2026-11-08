"""The hospital's check list: which checks every new pregnancy gets, editable by clinicians.

The list is seeded from the clinician spec the first time it is needed. After that, doctors and
facility admins add, change and retire checks themselves, with no code change. A check is never
deleted, only retired, so every pregnancy keeps its history. Changes apply to pregnancies enrolled
afterwards. A single patient's list is adjusted on the patient (add a check, mark one not needed).
"""

import uuid

from rest_framework.exceptions import PermissionDenied, ValidationError

from care.emr.models.organization import FacilityOrganizationUser
from care_maternal.models import MaternalCheckTemplate
from care_maternal.utils.schedule import parse_ga, templates_from_spec

EDITOR_ROLES = ("Doctor", "Facility Admin", "Administrator", "Admin")
MAX_WEEKS = 45
EDITABLE = (
    "label", "kind", "from_weeks", "to_weeks", "relative_to", "after_days",
    "waiting_note", "active", "sort_order",
)


def can_edit(user) -> bool:
    if user.is_superuser:
        return True
    return FacilityOrganizationUser.objects.filter(user=user, role__name__in=EDITOR_ROLES, deleted=False).exists()


def require_editor(user) -> None:
    if not can_edit(user):
        raise PermissionDenied("Only doctors and facility admins can change the check list.")


def ensure_templates() -> None:
    """Seed the check list from the clinician spec the first time. Idempotent."""
    if MaternalCheckTemplate.objects.filter(deleted=False).exists():
        return
    MaternalCheckTemplate.objects.bulk_create(
        MaternalCheckTemplate(sort_order=index * 10, source="spec", **row)
        for index, row in enumerate(templates_from_spec())
    )


def all_templates():
    ensure_templates()
    return MaternalCheckTemplate.objects.filter(deleted=False).order_by("sort_order", "id")


def active_templates() -> list[dict]:
    """What a new pregnancy is built from."""
    return [
        {
            "spec_id": t.spec_id, "label": t.label, "kind": t.kind,
            "from_weeks": t.from_weeks, "to_weeks": t.to_weeks,
            "relative_to": t.relative_to, "after_days": t.after_days, "waiting_note": t.waiting_note,
        }
        for t in all_templates().filter(active=True)
    ]


def _weeks(value, field) -> str:
    value = str(value or "").strip()
    if not value:
        return ""
    try:
        days = parse_ga(value)
    except ValueError:
        raise ValidationError({field: "Use weeks, or weeks+days, for example 13 or 13+6."}) from None
    if days > MAX_WEEKS * 7:
        raise ValidationError({field: f"Gestational age cannot be more than {MAX_WEEKS} weeks."})
    return value


def _clean(data: dict, own_spec_id: str = "") -> dict:
    clean = {}
    if "label" in data:
        label = str(data["label"] or "").strip()
        if not label:
            raise ValidationError({"label": "Write what the check is."})
        clean["label"] = label[:500]
    if "kind" in data:
        kind = str(data["kind"] or "").strip().lower().replace(" ", "_")
        if not kind:
            raise ValidationError({"kind": "Choose a kind."})
        clean["kind"] = kind[:32]
    for field in ("from_weeks", "to_weeks"):
        if field in data:
            clean[field] = _weeks(data[field], field)
    if "from_weeks" in clean or "to_weeks" in clean:
        start, end = clean.get("from_weeks"), clean.get("to_weeks")
        if start and end and parse_ga(start) > parse_ga(end):
            raise ValidationError({"to_weeks": "The end of the window cannot be before the start."})
    if "relative_to" in data:
        target = str(data["relative_to"] or "").strip()
        if target:
            if target == own_spec_id:
                raise ValidationError({"relative_to": "A check cannot depend on itself."})
            if not MaternalCheckTemplate.objects.filter(spec_id=target, deleted=False).exists():
                raise ValidationError({"relative_to": "That check does not exist."})
        clean["relative_to"] = target
    if "after_days" in data:
        days = data["after_days"]
        clean["after_days"] = None if days in (None, "") else int(days)
    if "waiting_note" in data:
        clean["waiting_note"] = str(data["waiting_note"] or "").strip()[:255]
    if "active" in data:
        clean["active"] = bool(data["active"])
    if "sort_order" in data:
        clean["sort_order"] = int(data["sort_order"])
    return clean


def create_template(data: dict, user) -> MaternalCheckTemplate:
    require_editor(user)
    ensure_templates()
    clean = _clean({"kind": "visit_check", "from_weeks": "0", "to_weeks": "40", **data})
    if "label" not in clean:
        raise ValidationError({"label": "Write what the check is."})
    if clean.get("relative_to") and clean.get("after_days") is None:
        raise ValidationError({"after_days": "Say how many days after that check."})
    last = all_templates().last()
    return MaternalCheckTemplate.objects.create(
        spec_id=f"CUSTOM-{uuid.uuid4().hex[:8]}",
        source="custom",
        sort_order=(last.sort_order + 10) if last else 0,
        created_by=user,
        updated_by=user,
        **clean,
    )


def update_template(template: MaternalCheckTemplate, data: dict, user) -> MaternalCheckTemplate:
    require_editor(user)
    clean = _clean({k: v for k, v in data.items() if k in EDITABLE}, own_spec_id=template.spec_id)
    for field, value in clean.items():
        setattr(template, field, value)
    if template.relative_to and template.after_days is None:
        raise ValidationError({"after_days": "Say how many days after that check."})
    template.updated_by = user
    template.save()
    return template
