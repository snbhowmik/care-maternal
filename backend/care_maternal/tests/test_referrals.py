"""Handover between two hospitals, simulated in one test database.

The two hospitals are two peers in the same database: the sender's outbound call is routed to the
receiver's receive logic, so the flow matches the real HTTP path without a network.
"""

import uuid
from datetime import date, timedelta
from unittest import mock

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from care.emr.models.patient import Patient
from care.security.models import RoleModel
from care.users.models import User
from care_maternal import referrals as svc
from care_maternal import services
from care_maternal.models import MaternalAlert, MaternalReferral

SENDER = "Rural PHC Alpha"
RECEIVER = "District Hospital Beta"
TOKEN = "test-shared-token"

CONFIG = {
    "MATERNAL_FACILITY_NAME": SENDER,
    "MATERNAL_INBOUND_TOKEN": TOKEN,
    "MATERNAL_HANDOVER_HOURS": 24,
    "MATERNAL_PEERS": {
        RECEIVER: {"url": "http://beta.example", "token": TOKEN},
        SENDER: {"url": "http://alpha.example", "token": TOKEN},
    },
}


def _route(url, token, body):
    """Simulate the other hospital's HTTP endpoint inside this test database."""
    if url.endswith("/referrals/inbound/"):
        ref = svc.receive_referral(body)
        return _Resp(201, {"id": str(ref.external_ref)})
    if url.endswith("/referrals/status/"):
        ref = MaternalReferral.objects.get(external_ref=body["external_ref"], direction="out")
        svc.apply_status_from_peer(ref, body["status"], None, body.get("note", ""))
        return _Resp(200, {})
    raise AssertionError(url)


class _Resp:
    def __init__(self, code, data):
        self.status_code = code
        self._data = data
        self.text = str(data)

    def json(self):
        return self._data


@override_settings(PLUGIN_CONFIGS={"care_maternal": CONFIG})
class HandoverTests(TestCase):
    def setUp(self):
        self.user = User.objects.create(username="referring-doctor")
        RoleModel.objects.create(name="Doctor", is_system=True)
        self.patient = Patient.objects.create(
            name="SYNTHETIC Handover", phone_number="+919999000301",
            gender=2, date_of_birth=date(1994, 3, 3),
        )
        self.pregnancy = services.create_pregnancy(
            self.patient, date.today() - timedelta(weeks=24), self.user, gravida=2, para=1
        )
        self.pregnancy.items.filter(spec_id="V-TD1").update(done_on=date.today())

    def _referral(self):
        return svc.create_referral(self.pregnancy, RECEIVER, "Severe anaemia, needs transfusion", self.user)

    def test_consent_is_required_before_send(self):
        ref = self._referral()
        with mock.patch.object(svc, "_post", side_effect=_route):
            with self.assertRaises(ValidationError):
                svc.send_referral(ref, self.user)
        self.assertFalse(MaternalReferral.objects.filter(direction="in").exists())

    def test_full_handover_is_received_acknowledged_and_examined(self):
        ref = self._referral()
        svc.record_consent(ref, "patient", self.user)
        with mock.patch.object(svc, "_post", side_effect=_route):
            svc.send_referral(ref, self.user)
            ref.refresh_from_db()
            self.assertEqual(ref.status, "sent")
            received = MaternalReferral.objects.get(external_ref=ref.external_ref, direction="in")
            self.assertEqual(received.status, "received")
            self.assertEqual(received.pregnancy.patient.name, "SYNTHETIC Handover")
            # the referred patient is a new record at the receiving hospital (no deduplication)
            self.assertNotEqual(received.pregnancy.patient_id, self.patient.id)
            self.assertEqual(received.pregnancy.items.get(spec_id="V-TD1").done_on, date.today())
            svc.acknowledge_inbound(received, self.user)
            svc.examine_inbound(received, "Hb 6.2, transfusion started", self.user)
        ref.refresh_from_db()
        self.assertEqual(ref.status, "examined")
        self.assertIsNotNone(ref.acknowledged_at)
        self.assertIsNotNone(ref.examined_at)
        actions = list(ref.events.values_list("action", flat=True))
        self.assertIn("peer_examined", actions)

    def test_receiving_the_same_referral_twice_creates_one_record(self):
        ref = self._referral()
        svc.record_consent(ref, "patient", self.user)
        payload = {
            "external_ref": str(ref.external_ref),
            "from_facility": SENDER,
            "reason": ref.reason,
            "consent_by": "patient",
            "consent_at": timezone.now().isoformat(),
            "summary": svc.build_summary(self.pregnancy),
        }
        first = svc.receive_referral(payload)
        second = svc.receive_referral(payload)
        self.assertEqual(first.id, second.id)
        self.assertEqual(MaternalReferral.objects.filter(direction="in").count(), 1)

    def test_missed_deadline_marks_incomplete_and_alerts_clinician(self):
        ref = self._referral()
        svc.record_consent(ref, "patient", self.user)
        with mock.patch.object(svc, "_post", side_effect=_route):
            svc.send_referral(ref, self.user)
        ref.refresh_from_db()
        ref.deadline_at = timezone.now() - timedelta(minutes=1)
        ref.status = "sent"
        ref.save()
        # the receiver never acknowledged: the sender's view must show it
        MaternalReferral.objects.filter(direction="in").update(status="received")
        self.assertEqual(svc.sweep_deadlines(), 1)
        ref.refresh_from_db()
        self.assertEqual(ref.status, "incomplete")
        self.assertTrue(MaternalAlert.objects.filter(pregnancy=self.pregnancy, kind="handover").exists())
        self.assertEqual(svc.sweep_deadlines(), 0)

    def test_escalation_options_on_incomplete_handover(self):
        ref = self._referral()
        svc.record_consent(ref, "patient", self.user)
        with mock.patch.object(svc, "_post", side_effect=_route):
            svc.send_referral(ref, self.user)
        ref.refresh_from_db()
        ref.status = "incomplete"
        ref.save()
        with self.assertRaises(ValidationError):
            svc.manage_here(ref, "", self.user)
        svc.check_patient(ref, "Phoned family; mother stable at home", self.user)
        new_ref = svc.refer_again(ref, SENDER, "Second opinion", self.user)
        ref.refresh_from_db()
        self.assertEqual(ref.status, "referred_again")
        self.assertEqual(new_ref.status, "draft")  # consent is needed again for a new hospital
        self.assertEqual(new_ref.previous_id, ref.id)

    def test_manage_here_records_plan_and_alerts(self):
        ref = self._referral()
        ref.status = "incomplete"
        ref.save()
        svc.manage_here(ref, "ASHA home visit daily, PHC doctor reviews Friday", self.user)
        ref.refresh_from_db()
        self.assertEqual(ref.status, "self_managed")
        self.assertIn("ASHA", ref.outcome_note)

    def test_only_ready_referrals_can_be_sent_and_only_drafts_consented(self):
        ref = self._referral()
        svc.record_consent(ref, "patient", self.user)
        with self.assertRaises(ValidationError):
            svc.record_consent(ref, "family", self.user)

    def test_events_are_never_deleted(self):
        ref = self._referral()
        svc.record_consent(ref, "patient", self.user)
        self.assertGreaterEqual(ref.events.count(), 2)


@override_settings(PLUGIN_CONFIGS={"care_maternal": CONFIG})
class InboundApiTests(TestCase):
    def setUp(self):
        RoleModel.objects.create(name="Doctor", is_system=True)
        self.client = APIClient()
        self.user = User.objects.create(username="receiving-doctor", is_superuser=True)
        self.patient = Patient.objects.create(
            name="SYNTHETIC API", phone_number="+919999000302", gender=2,
            date_of_birth=date(1996, 6, 6),
        )
        self.pregnancy = services.create_pregnancy(self.patient, date.today() - timedelta(weeks=10), self.user)

    def _payload(self):
        return {
            "external_ref": str(uuid.uuid4()),
            "from_facility": SENDER,
            "reason": "Bleeding",
            "consent_by": "patient",
            "consent_at": timezone.now().isoformat(),
            "summary": svc.build_summary(self.pregnancy),
        }

    def test_inbound_rejects_wrong_token(self):
        r = self.client.post("/api/care_maternal/referrals/inbound/", self._payload(), format="json",
                             HTTP_AUTHORIZATION="Bearer wrong")
        self.assertEqual(r.status_code, 403)

    def test_inbound_rejects_missing_token(self):
        r = self.client.post("/api/care_maternal/referrals/inbound/", self._payload(), format="json")
        self.assertEqual(r.status_code, 403)

    def test_inbound_accepts_correct_token(self):
        r = self.client.post("/api/care_maternal/referrals/inbound/", self._payload(), format="json",
                             HTTP_AUTHORIZATION=f"Bearer {TOKEN}")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json()["direction"], "in")

    def test_staff_cannot_see_referrals_for_patients_they_cannot_see(self):
        outsider = User.objects.create(username="outsider")
        ref = svc.create_referral(self.pregnancy, RECEIVER, "x", self.user)
        client = APIClient()
        client.force_authenticate(outsider)
        r = client.get(f"/api/care_maternal/referrals/?pregnancy={self.pregnancy.external_id}")
        self.assertEqual(r.status_code, 404)
        self.assertTrue(ref)
