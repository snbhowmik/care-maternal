"""Who is on duty. Reminders for checks go to the people on duty.

CARE has no duty roster, so staff switch themselves on and off. A forgotten switch expires after
DUTY_HOURS, so a reminder never goes to someone who went home yesterday.
"""

from datetime import timedelta

from django.utils import timezone

from care.emr.models.organization import FacilityOrganizationUser
from care.users.models import User
from care_maternal.models import MaternalDuty
from care_maternal.settings import plugin_settings

DUTY_HOURS = 12


def notify_roles() -> list[str]:
    return [r.strip() for r in plugin_settings.MATERNAL_NOTIFY_ROLES.split(",") if r.strip()]


def team() -> list[User]:
    """Everyone at this hospital who can be reminded: the notify roles, regardless of duty."""
    ids = (
        FacilityOrganizationUser.objects.filter(role__name__in=notify_roles(), deleted=False)
        .values_list("user_id", flat=True)
        .distinct()
    )
    return list(User.objects.filter(id__in=ids, is_active=True, deleted=False).order_by("username"))


def _open(now):
    return MaternalDuty.objects.filter(deleted=False, ended_at__isnull=True, since__lte=now, until__gt=now)


def on_duty_now(now=None) -> list[User]:
    """People in the team who are on duty right now."""
    now = now or timezone.now()
    on = set(_open(now).values_list("user_id", flat=True))
    return [u for u in team() if u.id in on]


def is_on_duty(user, now=None) -> bool:
    return _open(now or timezone.now()).filter(user=user).exists()


def go_on_duty(user, now=None) -> MaternalDuty:
    now = now or timezone.now()
    existing = _open(now).filter(user=user).first()
    if existing:
        return existing
    return MaternalDuty.objects.create(user=user, since=now, until=now + timedelta(hours=DUTY_HOURS), created_by=user)


def go_off_duty(user, now=None) -> int:
    now = now or timezone.now()
    return _open(now).filter(user=user).update(ended_at=now)


def recipients(now=None) -> tuple[list[User], bool]:
    """Who to remind: people on duty. If nobody is marked on duty, the whole team, so a reminder is never lost.

    Returns (users, nobody_on_duty).
    """
    on = on_duty_now(now)
    if on:
        return on, False
    return team(), True
