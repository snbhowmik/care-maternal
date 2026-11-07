"""The Maternal patient tag: set while a patient has open maternal checks, removed after the last one.

The tag is a facility tag (CARE's PatientFacilityTagManager), so each hospital sees it on its own
patients list next to its other tags. Tags are written without CARE's per-user tag permission
check, because enrolment is already authorised by the pregnancy endpoints.
"""

from care.emr.models.patient import Patient
from care.emr.models.tag_config import TagConfig
from care.emr.tagging.base import PatientFacilityTagManager
from care_maternal.models import MaternalPregnancy

MATERNAL_TAG_DISPLAY = "Maternal"


def ensure_tag(facility) -> TagConfig:
    tag, _ = TagConfig.objects.get_or_create(
        facility=facility,
        display=MATERNAL_TAG_DISPLAY,
        defaults={
            "resource": "patient",
            "category": "clinical",
            "status": "active",
            "description": "Pregnancy or postpartum checks are open for this patient.",
        },
    )
    return tag


def _has_open_checks(patient) -> bool:
    return MaternalPregnancy.objects.filter(
        patient=patient, deleted=False, items__done_on__isnull=True, items__deleted=False
    ).exists()


def tag_patient(patient, facility) -> None:
    patient.refresh_from_db(fields=["facility_tags"])  # CARE stores the facility key as an int in memory, a string in the DB
    tag = ensure_tag(facility)
    manager = PatientFacilityTagManager(facility)
    tags = manager.get_resource_tag(patient)
    if tag.id not in tags:
        manager.set_instance_tag(patient, [*tags, tag.id])
        patient.save(update_fields=["facility_tags"])


def untag_patient(patient, facility) -> None:
    tag = TagConfig.objects.filter(facility=facility, display=MATERNAL_TAG_DISPLAY).first()
    if tag is None:
        return
    patient.refresh_from_db(fields=["facility_tags"])
    manager = PatientFacilityTagManager(facility)
    tags = manager.get_resource_tag(patient)
    if tag.id in tags:
        manager.set_instance_tag(patient, [t for t in tags if t != tag.id])
        patient.save(update_fields=["facility_tags"])


def sync_tag(patient, facility) -> None:
    """Keep the tag exactly while the patient has an open check."""
    if _has_open_checks(patient):
        tag_patient(patient, facility)
    else:
        untag_patient(patient, facility)


def tagged_patients(facility):
    """Patients at this facility carrying the Maternal tag."""
    tag = TagConfig.objects.filter(facility=facility, display=MATERNAL_TAG_DISPLAY).first()
    if tag is None:
        return Patient.objects.none()
    manager = PatientFacilityTagManager(facility)
    candidates = Patient.objects.filter(
        deleted=False, facility_tags__has_key=str(facility.id)
    )
    return [p for p in candidates if tag.id in manager.get_resource_tag(p)]
