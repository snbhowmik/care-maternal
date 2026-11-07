"""Patient portal API. Read-only, scoped to the phone number in the patient token.

Patients see only their own pregnancies, and only alerts addressed to patients.
Clinician alerts never appear here.
"""

from django.shortcuts import get_object_or_404
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from care_maternal.models import MaternalPregnancy
from care_maternal.serializers import (
    AlertSerializer,
    PregnancySerializer,
    ScheduleItemSerializer,
)
from config.patient_otp_authentication import (
    JWTTokenPatientAuthentication,
    OTPAuthenticatedPermission,
)


class OTPPregnancyViewSet(GenericViewSet):
    authentication_classes = [JWTTokenPatientAuthentication]
    permission_classes = [OTPAuthenticatedPermission]
    lookup_field = "external_id"

    def _mine(self):
        return MaternalPregnancy.objects.filter(
            patient__phone_number=self.request.user.phone_number, deleted=False
        )

    def list(self, request):
        return Response(PregnancySerializer(self._mine().order_by("-lmp"), many=True).data)

    def retrieve(self, request, external_id=None):
        pregnancy = get_object_or_404(self._mine(), external_id=external_id)
        return Response(PregnancySerializer(pregnancy).data)

    @action(detail=True, methods=["get"])
    def items(self, request, external_id=None):
        pregnancy = get_object_or_404(self._mine(), external_id=external_id)
        qs = pregnancy.items.filter(deleted=False).order_by("due_from", "spec_id")
        return Response(ScheduleItemSerializer(qs, many=True).data)

    @action(detail=True, methods=["get"])
    def alerts(self, request, external_id=None):
        pregnancy = get_object_or_404(self._mine(), external_id=external_id)
        qs = pregnancy.alerts.filter(deleted=False, audience="patient").order_by("-created_date")
        return Response(AlertSerializer(qs, many=True).data)
