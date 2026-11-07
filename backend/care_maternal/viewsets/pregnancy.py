from datetime import date

from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from care.emr.models.patient import Patient
from care.facility.models.facility import Facility
from care.security.authorization import AuthorizationController
from care_maternal import booking as booking_service
from care_maternal import services
from care_maternal import no_show as no_show_service
from care_maternal import tags
from care_maternal.models import MaternalAlert, MaternalPregnancy, MaternalScheduleItem
from care_maternal.serializers import (
    AlertSerializer,
    BookVisitSerializer,
    CompleteItemSerializer,
    EmergencySerializer,
    PregnancyCreateSerializer,
    PregnancySerializer,
    ScheduleItemSerializer,
)


def _visible_patient(request, patient_uuid):
    """404 when the caller cannot see the patient, so existence is not revealed."""
    patient = get_object_or_404(Patient, external_id=patient_uuid, deleted=False)
    if not (_is_registrar(request.user, patient)
            or AuthorizationController.call("can_view_patient_obj", request.user, patient)):
        raise Http404
    return patient


def _facility_from(external_id):
    """The hospital the staff member is working in, from the request. None when not given."""
    if not external_id:
        return None
    return get_object_or_404(Facility, external_id=external_id)


def _is_registrar(user, patient):
    """The person who registered a patient may see and enroll that patient (CARE records created_by)."""
    return patient.created_by_id is not None and patient.created_by_id == user.id


def _writable_patient(request, patient):
    if not (_is_registrar(request.user, patient)
            or AuthorizationController.call("can_write_patient_obj", request.user, patient)):
        raise PermissionDenied("You do not have write access to this patient.")


class PregnancyViewSet(GenericViewSet):
    """Staff API. Every action checks CARE's patient permissions first."""

    permission_classes = [IsAuthenticated]
    lookup_field = "external_id"
    queryset = MaternalPregnancy.objects.filter(deleted=False)

    def _pregnancy(self, request, pregnancy_uuid):
        pregnancy = get_object_or_404(
            MaternalPregnancy, external_id=pregnancy_uuid, deleted=False
        )
        _visible_patient(request, pregnancy.patient.external_id)
        return pregnancy

    def list(self, request):
        patient_uuid = request.query_params.get("patient")
        if not patient_uuid:
            raise PermissionDenied("Pass ?patient=<patient id>.")
        patient = _visible_patient(request, patient_uuid)
        qs = patient.maternal_pregnancies.filter(deleted=False).order_by("-lmp")
        return Response(PregnancySerializer(qs, many=True).data)

    def create(self, request):
        facility = _facility_from(request.data.get("facility"))
        data = PregnancyCreateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        patient = _visible_patient(request, data.validated_data.pop("patient"))
        _writable_patient(request, patient)
        lmp = data.validated_data.pop("lmp")
        services.link_care_team(patient, request.user)
        pregnancy = services.create_pregnancy(patient, lmp, request.user, **data.validated_data)
        if facility:
            tags.sync_tag(patient, facility)
        return Response(PregnancySerializer(pregnancy).data, status=201)

    @action(detail=False, methods=["get"])
    def worklist(self, request):
        """Each patient at ?facility= with the Maternal tag, and their open checks, limited to patients this user can see."""
        facility = _facility_from(request.query_params.get("facility"))
        if facility is None:
            raise PermissionDenied("Pass ?facility=<facility id>.")
        today = timezone.localdate()
        rows = []
        for patient in tags.tagged_patients(facility):
            if not (_is_registrar(request.user, patient)
                    or AuthorizationController.call("can_view_patient_obj", request.user, patient)):
                continue
            for pregnancy in patient.maternal_pregnancies.filter(deleted=False).order_by("-lmp"):
                open_items = pregnancy.items.filter(deleted=False, done_on__isnull=True)
                rows.append({
                    "patient_id": str(patient.external_id),
                    "patient_name": patient.name,
                    "pregnancy_id": str(pregnancy.external_id),
                    "edd": pregnancy.edd,
                    "open_checks": open_items.count(),
                    "overdue_checks": open_items.filter(due_to__lt=today).count(),
                })
        return Response(rows)

    def retrieve(self, request, external_id=None):
        return Response(PregnancySerializer(self._pregnancy(request, external_id)).data)

    @action(detail=True, methods=["get"])
    def items(self, request, external_id=None):
        pregnancy = self._pregnancy(request, external_id)
        qs = pregnancy.items.filter(deleted=False).order_by("due_from", "spec_id")
        return Response(ScheduleItemSerializer(qs, many=True).data)

    @action(detail=True, methods=["post"], url_path=r"items/(?P<spec_id>[^/]+)/complete")
    def complete(self, request, external_id=None, spec_id=None):
        pregnancy = self._pregnancy(request, external_id)
        _writable_patient(request, pregnancy.patient)
        body = CompleteItemSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        item = get_object_or_404(pregnancy.items, spec_id=spec_id, deleted=False)
        services.complete_item(item, body.validated_data["on_date"], request.user)
        facility = _facility_from(request.data.get("facility"))
        if facility:
            tags.sync_tag(pregnancy.patient, facility)
        return Response(ScheduleItemSerializer(item).data)

    @action(detail=True, methods=["post"], url_path=r"items/(?P<spec_id>[^/]+)/book")
    def book(self, request, external_id=None, spec_id=None):
        pregnancy = self._pregnancy(request, external_id)
        _writable_patient(request, pregnancy.patient)
        body = BookVisitSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        item = get_object_or_404(pregnancy.items, spec_id=spec_id, deleted=False)
        booking_service.book_visit(
            item, body.validated_data["on_date"], body.validated_data["start_time"], request.user
        )
        return Response(ScheduleItemSerializer(item).data, status=201)

    @action(detail=True, methods=["get"])
    def slots(self, request, external_id=None):
        """The day's bookable times for the calendar: ?date=YYYY-MM-DD."""
        self._pregnancy(request, external_id)
        raw = request.query_params.get("date")
        if not raw:
            raise PermissionDenied("Pass ?date=YYYY-MM-DD.")
        on_date = date.fromisoformat(raw)
        return Response(booking_service.available_slots(request.user, on_date))

    @action(detail=True, methods=["post"])
    def emergency(self, request, external_id=None):
        pregnancy = self._pregnancy(request, external_id)
        _writable_patient(request, pregnancy.patient)
        body = EmergencySerializer(data=request.data)
        body.is_valid(raise_exception=True)
        alert = services.report_emergency(pregnancy, body.validated_data["symptoms"])
        return Response(AlertSerializer(alert).data, status=201)

    @action(detail=True, methods=["post"])
    def sweep(self, request, external_id=None):
        pregnancy = self._pregnancy(request, external_id)
        _writable_patient(request, pregnancy.patient)
        return Response({"overdue_alerts_raised": services.sweep_overdue(pregnancy)})

    @action(detail=True, methods=["get"])
    def alerts(self, request, external_id=None):
        pregnancy = self._pregnancy(request, external_id)
        qs = pregnancy.alerts.filter(deleted=False).order_by("-created_date")
        return Response(AlertSerializer(qs, many=True).data)

    @action(detail=True, methods=["post"], url_path=r"items/(?P<spec_id>[^/]+)/no-show")
    def no_show(self, request, external_id=None, spec_id=None):
        pregnancy = self._pregnancy(request, external_id)
        _writable_patient(request, pregnancy.patient)
        item = get_object_or_404(pregnancy.items, spec_id=spec_id, deleted=False)
        no_show_service.mark_no_show(item, actor=request.user)
        return Response(ScheduleItemSerializer(item).data)

    @action(detail=True, methods=["get"], url_path="home-visits")
    def home_visits(self, request, external_id=None):
        pregnancy = self._pregnancy(request, external_id)
        visits = pregnancy.home_visits.filter(deleted=False).order_by("-due_on")
        return Response([
            {
                "id": str(v.external_id),
                "reason": v.reason,
                "address": v.address,
                "due_on": v.due_on,
                "assigned_to": v.assigned_to.username if v.assigned_to else "",
                "visited_on": v.visited_on,
                "visit_note": v.visit_note,
            }
            for v in visits
        ])

    @action(detail=True, methods=["post"], url_path=r"home-visits/(?P<visit_id>[^/]+)/visited")
    def home_visit_done(self, request, external_id=None, visit_id=None):
        pregnancy = self._pregnancy(request, external_id)
        _writable_patient(request, pregnancy.patient)
        visit = get_object_or_404(pregnancy.home_visits, external_id=visit_id, deleted=False)
        visit.visited_on = timezone.localdate()
        visit.visit_note = str(request.data.get("note", ""))[:2000]
        visit.save(update_fields=["visited_on", "visit_note", "modified_date"])
        return Response({"visited_on": visit.visited_on})
