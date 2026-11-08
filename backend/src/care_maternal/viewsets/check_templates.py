from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from care_maternal import check_templates as svc
from care_maternal.models import MaternalCheckTemplate


def template_json(t: MaternalCheckTemplate) -> dict:
    return {
        "id": str(t.external_id),
        "spec_id": t.spec_id,
        "label": t.label,
        "kind": t.kind,
        "from_weeks": t.from_weeks,
        "to_weeks": t.to_weeks,
        "relative_to": t.relative_to,
        "after_days": t.after_days,
        "waiting_note": t.waiting_note,
        "active": t.active,
        "sort_order": t.sort_order,
        "source": t.source,
    }


class CheckTemplateViewSet(GenericViewSet):
    """The hospital's check list. Anyone on staff can read it; doctors and facility admins can change it."""

    permission_classes = [IsAuthenticated]
    lookup_field = "external_id"
    queryset = MaternalCheckTemplate.objects.filter(deleted=False)

    def list(self, request):
        return Response({
            "can_edit": svc.can_edit(request.user),
            "results": [template_json(t) for t in svc.all_templates()],
        })

    def create(self, request):
        return Response(template_json(svc.create_template(request.data, request.user)), status=201)

    def partial_update(self, request, external_id=None):
        template = get_object_or_404(MaternalCheckTemplate, external_id=external_id, deleted=False)
        return Response(template_json(svc.update_template(template, request.data, request.user)))
