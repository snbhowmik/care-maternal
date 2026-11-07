"""Signal receivers.

This is how a plugin reacts to core events without core knowing it exists.
Registered from AppConfig.ready() — never import this module anywhere else.
"""

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from care.emr.models.patient import Patient


@receiver(post_save, sender=Patient)
def link_registrar(sender, instance, created, **kwargs):
    """The staff member who registers a patient can open that patient straight away.

    CARE shows a patient only through an open encounter, a role on the patient's organization,
    or a direct link. A newly registered patient has none, so the registrar would see
    "Patient Not Found". This adds the direct link. It is idempotent.
    """
    if instance.deleted or not instance.created_by_id:
        return
    from care_maternal.services import link_care_team

    transaction.on_commit(lambda: link_care_team(instance, instance.created_by))


@receiver(post_save, sender="emr.FacilityOrganizationUser")
def give_new_staff_region_access(sender, instance, created, **kwargs):
    """Staff added to the hospital later can also see every patient registered here."""
    if not created or instance.deleted:
        return
    from care_maternal.access import grant_region_access

    transaction.on_commit(lambda: grant_region_access(instance.user, instance.role))
