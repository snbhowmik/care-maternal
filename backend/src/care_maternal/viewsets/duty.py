from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import GenericViewSet

from care_maternal import duty
from care_maternal.models import MaternalAlert


def _name(user) -> str:
    return user.get_full_name().strip() or user.username


class DutyView(APIView):
    """Who is on duty, and a switch for the signed-in person. Reminders go to people on duty."""

    permission_classes = [IsAuthenticated]

    def _state(self, request):
        team_ids = {u.id for u in duty.team()}
        return {
            "mine": duty.is_on_duty(request.user),
            "in_team": request.user.id in team_ids,
            "hours": duty.DUTY_HOURS,
            "roles": duty.notify_roles(),
            "on_duty": [{"id": str(u.external_id), "name": _name(u)} for u in duty.on_duty_now()],
        }

    def get(self, request):
        return Response(self._state(request))

    def post(self, request):
        if request.data.get("on"):
            duty.go_on_duty(request.user)
        else:
            duty.go_off_duty(request.user)
        return Response(self._state(request))


class ReminderViewSet(GenericViewSet):
    """The signed-in person's own check reminders."""

    permission_classes = [IsAuthenticated]
    lookup_field = "external_id"
    queryset = MaternalAlert.objects.filter(deleted=False, audience="staff")

    def list(self, request):
        alerts = (
            self.get_queryset().filter(recipient=request.user, kind="reminder")
            .select_related("pregnancy__patient").order_by("-created_date")[:50]
        )
        return Response([
            {
                "id": str(a.external_id),
                "message": a.message,
                "created": a.created_date,
                "acknowledged": a.acknowledged_on is not None,
                "patient_id": str(a.pregnancy.patient.external_id),
                "patient_name": a.pregnancy.patient.name,
                "sms_sent": a.sms_sent,
            }
            for a in alerts
        ])

    @action(detail=True, methods=["post"])
    def acknowledge(self, request, external_id=None):
        alert = get_object_or_404(self.get_queryset(), external_id=external_id, recipient=request.user)
        if alert.acknowledged_on is None:
            alert.acknowledged_on = timezone.now()
            alert.acknowledged_by = request.user
            alert.save(update_fields=["acknowledged_on", "acknowledged_by", "modified_date"])
        return Response({"acknowledged": True})
