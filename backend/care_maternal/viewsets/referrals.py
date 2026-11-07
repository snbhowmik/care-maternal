import hmac
from datetime import datetime

from django.shortcuts import get_object_or_404
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import GenericViewSet

from care_maternal import referrals as svc
from care_maternal import tags
from care_maternal.models import MaternalPregnancy, MaternalReferral
from care_maternal.settings import plugin_settings
from care_maternal.viewsets.pregnancy import (
    _facility_from,
    _visible_patient,
    _writable_patient,
)
from config.patient_otp_authentication import (
    JWTTokenPatientAuthentication,
    OTPAuthenticatedPermission,
)


def referral_json(ref: MaternalReferral) -> dict:
    return {
        "id": str(ref.external_ref),
        "direction": ref.direction,
        "status": ref.status,
        "from_facility": ref.from_facility,
        "to_facility": ref.to_facility,
        "reason": ref.reason,
        "consent_by": ref.consent_by,
        "consent_at": ref.consent_at,
        "sent_at": ref.sent_at,
        "deadline_at": ref.deadline_at,
        "acknowledged_at": ref.acknowledged_at,
        "examined_at": ref.examined_at,
        "outcome_note": ref.outcome_note,
        "patient_name": ref.pregnancy.patient.name,
        "pregnancy_id": str(ref.pregnancy.external_id),
        "previous": str(ref.previous.external_ref) if ref.previous else None,
        "events": [
            {"action": e.action, "note": e.note, "actor": e.actor, "at": e.at}
            for e in ref.events.order_by("at", "id")
        ],
    }


def _ref_for_staff(request, ref_uuid, direction="out"):
    """Find a referral and check the caller may see its patient. 404 if they may not."""
    qs = MaternalReferral.objects.filter(deleted=False)
    if direction:
        qs = qs.filter(direction=direction)
    ref = get_object_or_404(qs, external_ref=ref_uuid)
    _visible_patient(request, ref.pregnancy.patient.external_id)
    return ref


class ReferralViewSet(GenericViewSet):
    """Staff API for the sending hospital (and the inbox at the receiving hospital)."""

    permission_classes = [IsAuthenticated]
    lookup_field = "external_id"

    def get_queryset(self):
        return MaternalReferral.objects.filter(deleted=False)

    @action(detail=False, methods=["get"])
    def peers(self, request):
        return Response({"facility": svc.facility_name(), "peers": sorted(svc.peers().keys())})

    def list(self, request):
        pregnancy_id = request.query_params.get("pregnancy")
        if not pregnancy_id:
            raise PermissionDenied("Pass ?pregnancy=<pregnancy id>.")
        pregnancy = MaternalPregnancy.objects.filter(external_id=pregnancy_id, deleted=False).first()
        if pregnancy is None:
            return Response([])
        _visible_patient(request, pregnancy.patient.external_id)
        refs = pregnancy.referrals.filter(deleted=False).order_by("-created_date")
        return Response([referral_json(r) for r in refs])

    def create(self, request):
        pregnancy_id = request.data.get("pregnancy")
        pregnancy = get_object_or_404(MaternalPregnancy, external_id=pregnancy_id, deleted=False)
        _visible_patient(request, pregnancy.patient.external_id)
        _writable_patient(request, pregnancy.patient)
        ref = svc.create_referral(
            pregnancy, request.data.get("peer", ""), request.data.get("reason", ""), request.user
        )
        return Response(referral_json(ref), status=201)

    def retrieve(self, request, external_id=None):
        return Response(referral_json(_ref_for_staff(request, external_id)))

    @action(detail=True, methods=["post"])
    def consent(self, request, external_id=None):
        ref = _ref_for_staff(request, external_id)
        _writable_patient(request, ref.pregnancy.patient)
        svc.record_consent(ref, request.data.get("by", ""), request.user)
        return Response(referral_json(ref))

    @action(detail=True, methods=["post"])
    def send(self, request, external_id=None):
        ref = _ref_for_staff(request, external_id)
        _writable_patient(request, ref.pregnancy.patient)
        svc.send_referral(ref, request.user)
        return Response(referral_json(ref))

    @action(detail=True, methods=["post"], url_path="check-patient")
    def check_patient(self, request, external_id=None):
        ref = _ref_for_staff(request, external_id)
        _writable_patient(request, ref.pregnancy.patient)
        svc.check_patient(ref, request.data.get("note", ""), request.user)
        return Response(referral_json(ref))

    @action(detail=True, methods=["post"], url_path="refer-again")
    def refer_again(self, request, external_id=None):
        ref = _ref_for_staff(request, external_id)
        _writable_patient(request, ref.pregnancy.patient)
        new_ref = svc.refer_again(ref, request.data.get("peer", ""), request.data.get("reason", ""), request.user)
        return Response(referral_json(new_ref), status=201)

    @action(detail=True, methods=["post"], url_path="manage-here")
    def manage_here(self, request, external_id=None):
        ref = _ref_for_staff(request, external_id)
        _writable_patient(request, ref.pregnancy.patient)
        svc.manage_here(ref, request.data.get("note", ""), request.user)
        return Response(referral_json(ref))

    # ---- receiving hospital's inbox (staff at this hospital)

    @action(detail=False, methods=["get"])
    def inbox(self, request):
        refs = MaternalReferral.objects.filter(direction="in", deleted=False).order_by("-created_date")
        return Response([referral_json(r) for r in refs])

    @action(detail=True, methods=["post"])
    def acknowledge(self, request, external_id=None):
        ref = get_object_or_404(MaternalReferral, external_ref=external_id, direction="in", deleted=False)
        svc.acknowledge_inbound(ref, request.user)
        self._tag_receiving(ref, request)
        return Response(referral_json(ref))

    @action(detail=True, methods=["post"])
    def examined(self, request, external_id=None):
        ref = get_object_or_404(MaternalReferral, external_ref=external_id, direction="in", deleted=False)
        svc.examine_inbound(ref, request.data.get("note", ""), request.user)
        self._tag_receiving(ref, request)
        return Response(referral_json(ref))

    @staticmethod
    def _tag_receiving(ref, request):
        """The receiving hospital shows the patient under its Maternal tag while checks are open."""
        facility = _facility_from(request.data.get("facility"))
        if facility:
            tags.tag_patient(ref.pregnancy.patient, facility)

    @action(detail=False, methods=["post"])
    def sweep(self, request):
        return Response({"incomplete_marked": svc.sweep_deadlines()})


class PeerTokenMixin:
    """Server-to-server calls. The token must match this hospital's inbound token exactly."""

    authentication_classes: list = []
    permission_classes = [AllowAny]

    def check_peer_token(self, request):
        expected = plugin_settings.MATERNAL_INBOUND_TOKEN
        header = request.headers.get("Authorization", "")
        given = header[7:] if header.startswith("Bearer ") else ""
        if not expected or not given or not hmac.compare_digest(given, expected):
            raise PermissionDenied("Invalid hospital token.")


class InboundReferralView(PeerTokenMixin, APIView):
    def post(self, request):
        self.check_peer_token(request)
        ref = svc.receive_referral(request.data)
        return Response(referral_json(ref), status=201)


class InboundStatusView(PeerTokenMixin, APIView):
    def post(self, request):
        self.check_peer_token(request)
        ref = MaternalReferral.objects.filter(
            external_ref=request.data.get("external_ref"), direction="out", deleted=False
        ).first()
        if ref is None:
            return Response({"detail": "No such referral here."}, status=404)
        at = request.data.get("at")
        at = datetime.fromisoformat(at) if at else None
        svc.apply_status_from_peer(ref, request.data.get("status", ""), at, request.data.get("note", ""))
        return Response(referral_json(ref))


class OTPReferralViewSet(GenericViewSet):
    """Patient portal: see referrals for her pregnancies and give consent. Read-mostly."""

    authentication_classes = [JWTTokenPatientAuthentication]
    permission_classes = [OTPAuthenticatedPermission]
    lookup_field = "external_id"

    def _mine(self):
        return MaternalReferral.objects.filter(
            pregnancy__patient__phone_number=self.request.user.phone_number,
            direction="out",
            deleted=False,
        )

    def list(self, request):
        return Response([referral_json(r) for r in self._mine().order_by("-created_date")])

    @action(detail=True, methods=["post"])
    def consent(self, request, external_id=None):
        ref = get_object_or_404(self._mine(), external_ref=external_id)
        svc.record_consent(ref, "patient (OTP login)", None)
        return Response(referral_json(ref))
