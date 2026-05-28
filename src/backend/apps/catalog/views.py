from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.workspaces.permissions import IsOperatorOrAbove

from .models import ServiceTemplate
from .serializers import ServiceTemplateDetailSerializer, ServiceTemplateSerializer


class ServiceTemplateViewSet(viewsets.ModelViewSet):
    """
    Catalog of deployable service templates.
    Read access is open to any authenticated user.
    Write/endorse requires at least Operator role in the current workspace.
    """

    permission_classes = [IsAuthenticated]
    lookup_field = "slug"

    def get_queryset(self):
        return ServiceTemplate.objects.all()

    def get_serializer_class(self):
        if self.action == "retrieve":
            return ServiceTemplateDetailSerializer
        return ServiceTemplateSerializer

    def get_permissions(self):
        if self.action in ("create", "update", "partial_update", "destroy", "endorse"):
            return [IsAuthenticated(), IsOperatorOrAbove()]
        return [IsAuthenticated()]

    @action(detail=True, methods=["post"])
    def endorse(self, request, slug=None):
        template = self.get_object()
        template.endorsed_by = request.user
        template.endorsed_at = timezone.now()
        template.endorsement = ServiceTemplate.EndorsementLevel.CERTIFIED
        template.save(update_fields=["endorsed_by", "endorsed_at", "endorsement"])
        return Response(
            ServiceTemplateSerializer(template, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )
