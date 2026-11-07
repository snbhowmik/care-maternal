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


@current_app.on_after_finalize.connect
def _setup_periodic_tasks(sender, **kwargs):
    sender.add_periodic_task(300.0, sweep_handovers.s(), name="care_maternal: sweep handover deadlines")
    sender.add_periodic_task(300.0, sweep_no_shows.s(), name="care_maternal: sweep no-shows")
