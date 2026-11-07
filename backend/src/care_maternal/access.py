"""Every staff member at this hospital can see every patient registered here.

CARE shows a patient to a user through an open encounter, a direct link, or a role on the
patient's region (organization). Each CARE instance in this deployment is one hospital, so the
plugin gives each staff member their hospital role on every top-level region (state). A patient
registered in any state is then visible to all staff, including staff added later.
"""

from care.emr.models.organization import FacilityOrganizationUser, Organization, OrganizationUser
from care.security.models import RoleModel

GEO_CONTEXT = "GOVT_ORG"


def _region_role(role):
    """The user's own role if CARE allows it on a region; otherwise the Staff role."""
    if GEO_CONTEXT in (role.contexts or []):
        return role
    return RoleModel.objects.filter(name="Staff").first()


def grant_region_access(user, role) -> int:
    role = _region_role(role)
    if role is None:
        return 0
    created = 0
    for region in Organization.objects.filter(org_type="govt", parent__isnull=True, deleted=False):
        _, was_created = OrganizationUser.objects.get_or_create(
            organization=region, user=user, defaults={"role": role}
        )
        created += was_created
    return created


def grant_all_staff() -> int:
    created = 0
    for link in FacilityOrganizationUser.objects.filter(deleted=False).select_related("user", "role"):
        created += grant_region_access(link.user, link.role)
    return created
