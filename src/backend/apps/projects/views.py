from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.workspaces.permissions import IsDeveloperOrAbove

from .models import Project, ProjectRepository
from .serializers import (
    ProjectDetailSerializer,
    ProjectRepositorySerializer,
    ProjectSerializer,
)


class ProjectViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, IsDeveloperOrAbove]
    lookup_field = "slug"

    def get_queryset(self):
        return Project.objects.filter(
            workspace=self.request.workspace
        ).select_related("workspace")

    def get_serializer_class(self):
        if self.action == "retrieve":
            return ProjectDetailSerializer
        return ProjectSerializer

    def perform_create(self, serializer):
        serializer.save(workspace=self.request.workspace)

    @action(detail=True, methods=["get", "post"])
    def repositories(self, request, slug=None):
        project = self.get_object()
        if request.method == "GET":
            qs = ProjectRepository.objects.filter(project=project)
            return Response(ProjectRepositorySerializer(qs, many=True).data)

        serializer = ProjectRepositorySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(project=project)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
