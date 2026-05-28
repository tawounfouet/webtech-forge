from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from apps.workspaces.permissions import IsDeveloperOrAbove

from .models import Environment
from .serializers import EnvironmentDetailSerializer, EnvironmentSerializer


class EnvironmentViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, IsDeveloperOrAbove]

    def get_queryset(self):
        qs = Environment.objects.filter(
            project__workspace=self.request.workspace
        ).select_related("project__workspace")

        project_id = self.request.query_params.get("project")
        if project_id:
            qs = qs.filter(project_id=project_id)
        return qs

    def get_serializer_class(self):
        if self.action == "retrieve":
            return EnvironmentDetailSerializer
        return EnvironmentSerializer
