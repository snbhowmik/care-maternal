from django.core.management.base import BaseCommand

from care.emr.models import Organization
from care_maternal.access import grant_all_staff
from care.emr.resources.organization.spec import OrganizationTypeChoices

# The 28 states and 8 union territories of India (2026).
STATES_AND_UTS = [
    "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh", "Goa", "Gujarat",
    "Haryana", "Himachal Pradesh", "Jharkhand", "Karnataka", "Kerala", "Madhya Pradesh",
    "Maharashtra", "Manipur", "Meghalaya", "Mizoram", "Nagaland", "Odisha", "Punjab", "Rajasthan",
    "Sikkim", "Tamil Nadu", "Telangana", "Tripura", "Uttar Pradesh", "Uttarakhand", "West Bengal",
    "Andaman and Nicobar Islands", "Chandigarh", "Dadra and Nagar Haveli and Daman and Diu",
    "Delhi", "Jammu and Kashmir", "Ladakh", "Lakshadweep", "Puducherry",
]


class Command(BaseCommand):
    help = (
        "Add every Indian state and union territory as a top-level government geo organization, "
        "so the address state list is complete. Idempotent. Districts need the LGD CSV loader."
    )

    def handle(self, *args, **options):
        created = 0
        for name in STATES_AND_UTS:
            _, was_created = Organization.objects.get_or_create(
                name=name,
                org_type=OrganizationTypeChoices.govt.value,
                parent=None,
                defaults={"active": True},
            )
            created += was_created
        self.stdout.write(f"States and UTs: {len(STATES_AND_UTS)} listed, {created} added.")
        # Staff see patients through their role on each state, so new states need the same roles.
        self.stdout.write(f"Staff region roles added: {grant_all_staff()}")
