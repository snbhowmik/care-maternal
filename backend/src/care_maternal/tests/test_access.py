"""All staff at the hospital can see patients registered here, through a role on each state."""

from django.test import TestCase

from care.emr.models.organization import (
    FacilityOrganization,
    FacilityOrganizationUser,
    Organization,
    OrganizationUser,
)
from care.facility.models.facility import Facility
from care.security.models import RoleModel
from care.users.models import User
from care_maternal.access import grant_all_staff


class StaffAccessTests(TestCase):
    def setUp(self):
        self.doctor_role, _ = RoleModel.objects.get_or_create(
            name="Doctor", defaults={"is_system": True, "contexts": ["FACILITY", "GOVT_ORG"]}
        )
        self.staff_role, _ = RoleModel.objects.get_or_create(
            name="Staff", defaults={"is_system": True, "contexts": ["FACILITY", "GOVT_ORG"]}
        )
        self.owner = User.objects.create(username="maternal-access-owner")
        self.facility = Facility.objects.create(
            name="Access test facility", facility_type=1, address="x", created_by=self.owner
        )
        self.org = FacilityOrganization.objects.filter(facility=self.facility).first()
        self.states = [
            Organization.objects.create(name=n, org_type="govt") for n in ("Tamil Nadu", "Kerala")
        ]

    def test_existing_staff_get_a_role_on_every_state(self):
        doctor = User.objects.create(username="maternal-access-doctor")
        FacilityOrganizationUser.objects.create(organization=self.org, user=doctor, role=self.doctor_role)
        grant_all_staff()
        for state in self.states:
            link = OrganizationUser.objects.get(organization=state, user=doctor)
            self.assertEqual(link.role, self.doctor_role)

    def test_facility_admin_gets_staff_role_on_states(self):
        grant_all_staff()  # the facility owner was made Facility Admin when the facility was created
        link = OrganizationUser.objects.get(organization=self.states[0], user=self.owner)
        self.assertEqual(link.role, self.staff_role)

    def test_staff_added_later_get_access(self):
        nurse = User.objects.create(username="maternal-access-nurse")
        with self.captureOnCommitCallbacks(execute=True):
            FacilityOrganizationUser.objects.create(organization=self.org, user=nurse, role=self.doctor_role)
        self.assertEqual(OrganizationUser.objects.filter(user=nurse).count(), len(self.states))

    def test_running_twice_adds_nothing_new(self):
        grant_all_staff()
        self.assertEqual(grant_all_staff(), 0)
