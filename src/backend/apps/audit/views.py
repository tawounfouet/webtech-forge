from rest_framework import mixins, viewsets
from rest_framework.permissions import IsAuthenticated

from apps.workspaces.permissions import IsViewerOrAbove

from .models import AuditLog
from .serializers import AuditLogSerializer


class AuditLogViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = AuditLogSerializer
    permission_classes = [IsAuthenticated, IsViewerOrAbove]

    def get_queryset(self):
        qs = AuditLog.objects.select_related("user").filter(
            workspace=self.request.workspace
        )
        resource_type = self.request.query_params.get("resource_type")
        if resource_type:
            qs = qs.filter(resource_type=resource_type)
        return qs
