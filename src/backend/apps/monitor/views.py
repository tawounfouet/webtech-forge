from rest_framework import mixins, viewsets
from rest_framework.permissions import IsAuthenticated

from apps.workspaces.permissions import IsViewerOrAbove

from .models import MonitorSnapshot
from .serializers import MonitorSnapshotSerializer


class MonitorSnapshotViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = MonitorSnapshotSerializer
    permission_classes = [IsAuthenticated, IsViewerOrAbove]

    def get_queryset(self):
        return MonitorSnapshot.objects.filter(
            workspace=self.request.workspace
        ).order_by("-captured_at")[:50]
