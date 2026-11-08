from celery import shared_task
from celery import current_app


@shared_task(name="care_maternal.sweep_handovers")
def sweep_handovers() -> int:
    """Mark handovers past their deadline as incomplete and alert the clinician."""
    from care_maternal.referrals import sweep_deadlines

    return sweep_deadlines()


@shared_task(name="care_maternal.sweep_no_shows")
def sweep_no_shows() -> int:
    """Mark booked visits as no-show once the appointment time has passed without a record."""
    from care_maternal.no_show import sweep_no_shows as run

    return run()


@shared_task(name="care_maternal.sweep_reminders")
def sweep_reminders() -> int:
    """Remind staff on duty and patients about checks that are due, by priority."""
    from care_maternal.reminders import sweep_reminders as run

    return run()


@current_app.on_after_finalize.connect
def _setup_periodic_tasks(sender, **kwargs):
    sender.add_periodic_task(300.0, sweep_handovers.s(), name="care_maternal: sweep handover deadlines")
    sender.add_periodic_task(300.0, sweep_no_shows.s(), name="care_maternal: sweep no-shows")
    sender.add_periodic_task(900.0, sweep_reminders.s(), name="care_maternal: send check reminders")
