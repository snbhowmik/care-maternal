from django.db import models

from care.emr.models.base import EMRBaseModel


class MaternalPregnancy(EMRBaseModel):
    """One pregnancy for one CARE patient. Dates come from the clinician-reviewed spec."""

    patient = models.ForeignKey(
        "emr.Patient", on_delete=models.CASCADE, related_name="maternal_pregnancies"
    )
    lmp = models.DateField()
    edd = models.DateField()
    gravida = models.PositiveSmallIntegerField(default=1)
    para = models.PositiveSmallIntegerField(default=0)
    abortions = models.PositiveSmallIntegerField(default=0)
    living = models.PositiveSmallIntegerField(default=0)
    high_risk = models.BooleanField(default=False)  # set by a clinician, never automatically
    status = models.CharField(
        max_length=16,
        default="active",
        choices=[("active", "Active"), ("delivered", "Delivered"), ("closed", "Closed")],
    )


class MaternalScheduleItem(EMRBaseModel):
    """One spec item (visit, test, vaccine, scan) for one pregnancy."""

    pregnancy = models.ForeignKey(
        MaternalPregnancy, on_delete=models.CASCADE, related_name="items"
    )
    spec_id = models.CharField(max_length=64)
    kind = models.CharField(max_length=32)
    label = models.TextField()
    due_from = models.DateField(null=True, blank=True)
    due_to = models.DateField(null=True, blank=True)
    waiting_on = models.CharField(max_length=255, blank=True, default="")
    done_on = models.DateField(null=True, blank=True)
    done_by = models.ForeignKey(
        "users.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    overdue_alerted = models.BooleanField(default=False)
    # Appointments where the patient did not come. Counts every no-show for this check.
    no_show_count = models.PositiveSmallIntegerField(default=0)
    # CARE appointment created for this visit (core TokenBooking). Null until booked.
    booking = models.ForeignKey(
        "emr.TokenBooking", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="maternal_items",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["pregnancy", "spec_id"], name="unique_maternal_item_per_pregnancy"
            )
        ]


class MaternalAlert(EMRBaseModel):
    """Clinician alert or patient SMS record. Patient SMS is sent through CARE's SMS backend."""

    pregnancy = models.ForeignKey(
        MaternalPregnancy, on_delete=models.CASCADE, related_name="alerts"
    )
    audience = models.CharField(
        max_length=16, choices=[("clinician", "Clinician"), ("patient", "Patient")]
    )
    kind = models.CharField(max_length=32)
    message = models.TextField()
    sms_sent = models.BooleanField(default=False)
    acknowledged_on = models.DateTimeField(null=True, blank=True)
    acknowledged_by = models.ForeignKey(
        "users.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )


class MaternalReferral(EMRBaseModel):
    """A pregnancy handed over to another hospital. Outbound (we refer) or inbound (we receive).

    Both hospitals hold a row with the same `external_ref`, so each side can see the other's status.
    """

    DIRECTION = [("out", "Out"), ("in", "In")]
    STATUS = [
        ("draft", "Draft"),
        ("ready", "Consent recorded, ready to send"),
        ("sent", "Sent"),
        ("received", "Received"),
        ("acknowledged", "Acknowledged"),
        ("examined", "Patient examined"),
        ("incomplete", "Handover incomplete"),
        ("referred_again", "Referred again"),
        ("self_managed", "Managed by this hospital"),
        ("closed", "Closed"),
    ]

    external_ref = models.UUIDField(db_index=True)
    direction = models.CharField(max_length=3, choices=DIRECTION)
    pregnancy = models.ForeignKey(
        MaternalPregnancy, on_delete=models.CASCADE, related_name="referrals"
    )
    from_facility = models.CharField(max_length=255)
    to_facility = models.CharField(max_length=255)
    peer = models.CharField(max_length=64, blank=True, default="")
    reason = models.TextField()
    status = models.CharField(max_length=24, choices=STATUS, default="draft")
    consent_by = models.CharField(max_length=255, blank=True, default="")
    consent_at = models.DateTimeField(null=True, blank=True)
    summary = models.JSONField(default=dict, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    deadline_at = models.DateTimeField(null=True, blank=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    examined_at = models.DateTimeField(null=True, blank=True)
    outcome_note = models.TextField(blank=True, default="")
    previous = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True, related_name="next_referrals"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["external_ref", "direction"], name="unique_maternal_referral_ref"
            )
        ]


class MaternalReferralEvent(EMRBaseModel):
    """Append-only log of every referral step. Never edited or deleted."""

    referral = models.ForeignKey(
        MaternalReferral, on_delete=models.CASCADE, related_name="events"
    )
    action = models.CharField(max_length=40)
    note = models.TextField(blank=True, default="")
    actor = models.CharField(max_length=255, blank=True, default="")
    at = models.DateTimeField(auto_now_add=True)


class MaternalHomeVisit(EMRBaseModel):
    """An ASHA worker's visit to the patient's home, raised after repeated missed appointments."""

    pregnancy = models.ForeignKey(
        MaternalPregnancy, on_delete=models.CASCADE, related_name="home_visits"
    )
    spec_id = models.CharField(max_length=64)
    reason = models.TextField()
    address = models.TextField(blank=True, default="")
    due_on = models.DateField()
    assigned_to = models.ForeignKey(
        "users.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    visited_on = models.DateField(null=True, blank=True)
    visit_note = models.TextField(blank=True, default="")
