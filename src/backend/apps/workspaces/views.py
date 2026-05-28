from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Workspace, WorkspaceMember, WorkspaceQuota, WorkspaceSecret
from .permissions import IsViewerOrAbove, IsWorkspaceAdmin
from .serializers import (
    WorkspaceMemberSerializer,
    WorkspaceQuotaSerializer,
    WorkspaceSecretSerializer,
    WorkspaceSerializer,
)


class WorkspaceViewSet(viewsets.ModelViewSet):
    """
    CRUD on workspaces the requester belongs to.
    Nested actions (members, secrets, quota) enforce workspace RBAC via
    IsViewerOrAbove / IsWorkspaceAdmin on top of IsAuthenticated.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = WorkspaceSerializer
    lookup_field = "slug"

    def get_queryset(self):
        return (
            Workspace.objects.filter(members__user=self.request.user)
            .select_related("organization")
            .distinct()
        )

    def perform_create(self, serializer):
        serializer.save()

    # ── Members ──────────────────────────────────────────────────────────────

    @action(
        detail=True,
        methods=["get", "post"],
        permission_classes=[IsAuthenticated, IsViewerOrAbove],
    )
    def members(self, request, slug=None):
        workspace = self.get_object()
        if request.method == "GET":
            qs = WorkspaceMember.objects.filter(workspace=workspace).select_related("user")
            return Response(WorkspaceMemberSerializer(qs, many=True).data)

        # POST — only admins can invite
        if not IsWorkspaceAdmin().has_permission(request, self):
            return Response(status=status.HTTP_403_FORBIDDEN)
        serializer = WorkspaceMemberSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(workspace=workspace, added_by=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(
        detail=True,
        methods=["delete"],
        url_path="members/(?P<member_pk>[^/.]+)",
        permission_classes=[IsAuthenticated, IsWorkspaceAdmin],
    )
    def member_delete(self, request, slug=None, member_pk=None):
        workspace = self.get_object()
        try:
            member = WorkspaceMember.objects.get(pk=member_pk, workspace=workspace)
        except WorkspaceMember.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        member.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    # ── Secrets ───────────────────────────────────────────────────────────────

    @action(
        detail=True,
        methods=["get", "post"],
        permission_classes=[IsAuthenticated, IsViewerOrAbove],
    )
    def secrets(self, request, slug=None):
        workspace = self.get_object()
        if request.method == "GET":
            qs = WorkspaceSecret.objects.filter(workspace=workspace)
            return Response(WorkspaceSecretSerializer(qs, many=True).data)

        if not IsViewerOrAbove().has_permission(request, self):
            return Response(status=status.HTTP_403_FORBIDDEN)
        serializer = WorkspaceSecretSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(workspace=workspace)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    # ── Quota ────────────────────────────────────────────────────────────────

    @action(
        detail=True,
        methods=["get", "put", "patch"],
        permission_classes=[IsAuthenticated, IsViewerOrAbove],
    )
    def quota(self, request, slug=None):
        workspace = self.get_object()
        quota, _ = WorkspaceQuota.objects.get_or_create(workspace=workspace)
        if request.method == "GET":
            return Response(WorkspaceQuotaSerializer(quota).data)

        if not IsWorkspaceAdmin().has_permission(request, self):
            return Response(status=status.HTTP_403_FORBIDDEN)
        partial = request.method == "PATCH"
        serializer = WorkspaceQuotaSerializer(quota, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
