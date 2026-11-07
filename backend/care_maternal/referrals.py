"""Handover between hospitals: consent, send, acknowledge, examine, deadline and escalation.

Two CARE instances talk over HTTPS with a shared token per hospital pair. Every step is written to
MaternalReferralEvent, which is append-only. Nothing is deleted or merged. A referred patient is
created as a new patient record at the receiving hospital, even if one with the same name exists
(the no-deduplication rule).
"""

import json
import uuid
from datetime import date, datetime, timedelta

import requests
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from care.emr.models.patient import Patient
from care_maternal import services
from care_maternal.models import (
    MaternalAlert,
    MaternalPregnancy,
    MaternalReferral,
    MaternalReferralEvent,
)
from care_maternal.settings import plugin_settings

TIMEOUT_SECONDS = 15
BASE = "/api/care_maternal/referrals"


def peers() -> dict:
    raw = plugin_settings.MATERNAL_PEERS
    data = json.loads(raw) if isinstance(raw, str) else (raw or {})
    return data


def facility_name() -> str:
    return plugin_settings.MATERNAL_FACILITY_NAME


def _actor(user) -> str:
    return getattr(user, "username", "") or "system"


def _event(ref, action, actor="system", note=""):
    MaternalReferralEvent.objects.create(referral=ref, action=action, actor=actor, note=note)


def _peer(name):
    peer = peers().get(name)
    if not peer:
        raise ValidationError(f"Unknown receiving hospital: {name}")
    return peer


def _post(url, token, body):
    return requests.post(
        url,
        json=body,
        headers={"Authorization": f"Bearer {token}"},
        timeout=TIMEOUT_SECONDS,
    )


def build_summary(pregnancy: MaternalPregnancy) -> dict:
    """The maternal workspace only: patient identity, obstetric history, and the visit schedule."""
    p = pregnancy.patient
    return {
        "patient": {
            "name": p.name,
            "phone": p.phone_number,
            "date_of_birth": str(p.date_of_birth) if p.date_of_birth else None,
        },
        "pregnancy": {
            "lmp": str(pregnancy.lmp),
            "edd": str(pregnancy.edd),
            "gravida": pregnancy.gravida,
            "para": pregnancy.para,
            "abortions": pregnancy.abortions,
            "living": pregnancy.living,
        },
        "schedule": [
            {
                "spec_id": i.spec_id,
                "label": i.label,
                "due_from": str(i.due_from) if i.due_from else None,
                "due_to": str(i.due_to) if i.due_to else None,
                "done_on": str(i.done_on) if i.done_on else None,
            }
            for i in pregnancy.items.filter(deleted=False).order_by("due_from", "spec_id")
        ],
        "emergency_messages": list(
            pregnancy.alerts.filter(kind="emergency", deleted=False).values_list("message", flat=True)
        ),
    }


# ---------------------------------------------------------------- sending hospital

def create_referral(pregnancy, peer_name, reason, user) -> MaternalReferral:
    _peer(peer_name)
    if not reason or not reason.strip():
        raise ValidationError("Write why the patient is being referred.")
    ref = MaternalReferral.objects.create(
        external_ref=uuid.uuid4(),
        direction="out",
        pregnancy=pregnancy,
        from_facility=facility_name(),
        to_facility=peer_name,
        peer=peer_name,
        reason=reason.strip(),
        status="draft",
        created_by=user,
    )
    _event(ref, "created", _actor(user), reason.strip())
    return ref


def record_consent(ref, by: str, user=None) -> MaternalReferral:
    """Consent is needed before any send. `by` says who gave it (the patient, or a family member)."""
    if ref.status != "draft":
        raise ValidationError("Consent can be recorded only on a new referral.")
    if not by or not by.strip():
        raise ValidationError("Say who gave consent.")
    ref.consent_by = by.strip()
    ref.consent_at = timezone.now()
    ref.status = "ready"
    ref.save(update_fields=["consent_by", "consent_at", "status", "modified_date"])
    _event(ref, "consent_recorded", _actor(user) if user else by.strip(), f"Consent by {by.strip()}")
    return ref


def send_referral(ref, user) -> MaternalReferral:
    if ref.status != "ready":
        raise ValidationError("Record the patient's consent before sending.")
    peer = _peer(ref.peer)
    summary = build_summary(ref.pregnancy)
    payload = {
        "external_ref": str(ref.external_ref),
        "from_facility": ref.from_facility,
        "reason": ref.reason,
        "consent_by": ref.consent_by,
        "consent_at": ref.consent_at.isoformat(),
        "summary": summary,
    }
    try:
        resp = _post(f"{peer['url'].rstrip('/')}{BASE}/inbound/", peer["token"], payload)
    except requests.RequestException as exc:
        _event(ref, "send_failed", _actor(user), str(exc)[:300])
        raise ValidationError(
            "Could not reach the receiving hospital. The referral is still ready. Try again."
        ) from exc
    if resp.status_code not in (200, 201):
        _event(ref, "send_rejected", _actor(user), f"HTTP {resp.status_code}: {resp.text[:300]}")
        raise ValidationError(f"The receiving hospital did not accept the referral (HTTP {resp.status_code}).")
    now = timezone.now()
    ref.summary = summary
    ref.status = "sent"
    ref.sent_at = now
    ref.deadline_at = now + timedelta(hours=plugin_settings.MATERNAL_HANDOVER_HOURS)
    ref.save(update_fields=["summary", "status", "sent_at", "deadline_at", "modified_date"])
    _event(ref, "sent", _actor(user), f"Deadline {ref.deadline_at.isoformat()}")
    return ref


def apply_status_from_peer(ref, status: str, at: datetime | None, note: str) -> MaternalReferral:
    """A status update from the receiving hospital (received, acknowledged or examined)."""
    if status not in ("received", "acknowledged", "examined"):
        raise ValidationError("Unknown status.")
    at = at or timezone.now()
    if status in ("received",) and ref.status in ("sent",):
        ref.status = "received"
    elif status == "acknowledged":
        ref.status = "acknowledged"
        ref.acknowledged_at = ref.acknowledged_at or at
    elif status == "examined":
        ref.status = "examined"
        ref.acknowledged_at = ref.acknowledged_at or at
        ref.examined_at = ref.examined_at or at
    ref.save(update_fields=["status", "acknowledged_at", "examined_at", "modified_date"])
    late = " (after the deadline)" if ref.deadline_at and at > ref.deadline_at else ""
    _event(ref, f"peer_{status}", ref.to_facility, (note or "") + late)
    return ref


def check_patient(ref, note: str, user) -> MaternalReferral:
    if not note or not note.strip():
        raise ValidationError("Write what you found when you checked on the patient.")
    _event(ref, "status_check", _actor(user), note.strip())
    return ref


def refer_again(ref, peer_name: str, reason: str, user) -> MaternalReferral:
    if ref.status != "incomplete":
        raise ValidationError("Only an incomplete handover can be referred again.")
    new_ref = create_referral(ref.pregnancy, peer_name, reason or ref.reason, user)
    new_ref.previous = ref
    new_ref.save(update_fields=["previous", "modified_date"])
    ref.status = "referred_again"
    ref.save(update_fields=["status", "modified_date"])
    _event(ref, "referred_again", _actor(user), f"New referral to {peer_name}")
    _event(new_ref, "continues", _actor(user), f"Follows incomplete referral to {ref.to_facility}")
    return new_ref


def manage_here(ref, note: str, user) -> MaternalReferral:
    if ref.status != "incomplete":
        raise ValidationError("Only an incomplete handover can be managed here.")
    if not note or not note.strip():
        raise ValidationError("Write the plan for managing the patient here.")
    ref.status = "self_managed"
    ref.outcome_note = note.strip()
    ref.save(update_fields=["status", "outcome_note", "modified_date"])
    _event(ref, "self_managed", _actor(user), note.strip())
    MaternalAlert.objects.create(
        pregnancy=ref.pregnancy,
        audience="clinician",
        kind="handover",
        message=f"Managing here after the handover to {ref.to_facility} stalled: {note.strip()}",
    )
    return ref


def sweep_deadlines(now=None) -> int:
    """Mark sent handovers past their deadline as incomplete, and tell the clinician. Returns count."""
    now = now or timezone.now()
    raised = 0
    for ref in MaternalReferral.objects.filter(
        direction="out", status__in=["sent", "received"], deadline_at__lt=now, deleted=False
    ):
        ref.status = "incomplete"
        ref.save(update_fields=["status", "modified_date"])
        _event(ref, "deadline_passed", "system", f"No acknowledgement by {ref.deadline_at.isoformat()}")
        MaternalAlert.objects.create(
            pregnancy=ref.pregnancy,
            audience="clinician",
            kind="handover",
            message=(
                f"Handover incomplete: {ref.to_facility} has not acknowledged the referral "
                f"sent {ref.sent_at:%d %b %Y %H:%M}. Check on the patient, refer again, or manage here."
            ),
        )
        raised += 1
    return raised


# ---------------------------------------------------------------- receiving hospital

def receive_referral(payload: dict) -> MaternalReferral:
    """Create the referred patient and pregnancy here. Idempotent on external_ref."""
    try:
        ext = uuid.UUID(str(payload["external_ref"]))
    except (KeyError, ValueError) as exc:
        raise ValidationError("A valid external_ref is required.") from exc
    existing = MaternalReferral.objects.filter(external_ref=ext, direction="in").first()
    if existing:
        return existing
    summary = payload.get("summary") or {}
    pt = summary.get("patient") or {}
    pg = summary.get("pregnancy") or {}
    if not pt.get("name") or not pg.get("lmp"):
        raise ValidationError("The referral needs the patient's name and LMP.")
    dob = pt.get("date_of_birth")
    patient = Patient.objects.create(
        name=pt["name"],
        phone_number=pt.get("phone") or "",
        gender=2,
        date_of_birth=date.fromisoformat(dob) if dob else None,
    )
    lmp = date.fromisoformat(pg["lmp"])
    pregnancy = services.create_pregnancy(
        patient,
        lmp,
        None,
        gravida=pg.get("gravida", 1),
        para=pg.get("para", 0),
        abortions=pg.get("abortions", 0),
        living=pg.get("living", 0),
    )
    for item in summary.get("schedule", []):
        if item.get("done_on"):
            pregnancy.items.filter(spec_id=item["spec_id"]).update(done_on=date.fromisoformat(item["done_on"]))
    ref = MaternalReferral.objects.create(
        external_ref=ext,
        direction="in",
        pregnancy=pregnancy,
        from_facility=payload.get("from_facility", "unknown"),
        to_facility=facility_name(),
        peer=payload.get("from_facility", ""),
        reason=payload.get("reason", ""),
        status="received",
        consent_by=payload.get("consent_by", ""),
        consent_at=payload.get("consent_at"),
        summary=summary,
    )
    _event(ref, "received", "system", f"From {ref.from_facility}")
    MaternalAlert.objects.create(
        pregnancy=pregnancy,
        audience="clinician",
        kind="handover",
        message=f"Referral received from {ref.from_facility}. Acknowledge it and examine the patient.",
    )
    notify_peer(ref, "received", "")
    return ref


def notify_peer(ref, status: str, note: str, actor: str = "system") -> bool:
    """Tell the referring hospital what happened here. A failure is logged, never blocks care."""
    peer = peers().get(ref.from_facility)
    if not peer:
        _event(ref, "notify_skipped", actor, f"No peer configured for {ref.from_facility}")
        return False
    body = {
        "external_ref": str(ref.external_ref),
        "status": status,
        "at": timezone.now().isoformat(),
        "note": note,
    }
    try:
        resp = _post(f"{peer['url'].rstrip('/')}{BASE}/status/", peer["token"], body)
    except requests.RequestException as exc:
        _event(ref, "notify_failed", actor, str(exc)[:300])
        return False
    if resp.status_code not in (200, 201):
        _event(ref, "notify_failed", actor, f"HTTP {resp.status_code}")
        return False
    _event(ref, "notified_peer", actor, status)
    return True


def _take_on(ref, user):
    """The receiving doctor who acknowledges becomes the patient's doctor here (logged in PatientUser)."""
    from care.security.models import RoleModel
    from care.emr.models.patient import PatientUser

    role = RoleModel.objects.filter(name="Doctor").first()
    if user is None or role is None:
        raise ValidationError("A receiving doctor with the Doctor role must acknowledge the referral.")
    PatientUser.objects.get_or_create(patient=ref.pregnancy.patient, user=user, role=role)


def acknowledge_inbound(ref, user) -> MaternalReferral:
    if ref.direction != "in":
        raise ValidationError("Only referrals received here can be acknowledged here.")
    if ref.status not in ("received",):
        raise ValidationError("This referral is already acknowledged.")
    _take_on(ref, user)
    now = timezone.now()
    ref.status = "acknowledged"
    ref.acknowledged_at = now
    ref.save(update_fields=["status", "acknowledged_at", "modified_date"])
    _event(ref, "acknowledged", _actor(user), "")
    notify_peer(ref, "acknowledged", "", _actor(user))
    return ref


def examine_inbound(ref, note: str, user) -> MaternalReferral:
    if ref.direction != "in":
        raise ValidationError("Only referrals received here can be examined here.")
    if ref.status not in ("received", "acknowledged"):
        raise ValidationError("Acknowledge the referral before recording the examination.")
    _take_on(ref, user)
    if not note or not note.strip():
        raise ValidationError("Write the examination findings and plan.")
    now = timezone.now()
    ref.status = "examined"
    ref.acknowledged_at = ref.acknowledged_at or now
    ref.examined_at = now
    ref.outcome_note = note.strip()
    ref.save(update_fields=["status", "acknowledged_at", "examined_at", "outcome_note", "modified_date"])
    _event(ref, "examined", _actor(user), note.strip())
    notify_peer(ref, "examined", note.strip(), _actor(user))
    return ref
