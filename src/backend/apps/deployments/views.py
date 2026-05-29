from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.workspaces.permissions import IsOperatorOrAbove

from .models import Deployment
from .serializers import DeploymentDetailSerializer, DeploymentListSerializer


class DeploymentViewSet(
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    """
    Read-only ViewSet for deployments.
    Write operations (create, rollback) go through ServiceViewSet.deploy
    and DeploymentViewSet.rollback action.
    """

    permission_classes = [IsAuthenticated, IsOperatorOrAbove]

    def get_queryset(self):
        return (
            Deployment.objects.select_related(
                "service__environment__project__workspace",
                "triggered_by",
            )
            .filter(service__environment__project__workspace=self.request.workspace)
            .order_by("-created_at")
        )

    def get_serializer_class(self):
        if self.action == "retrieve":
            return DeploymentDetailSerializer
        return DeploymentListSerializer

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[IsAuthenticated, IsOperatorOrAbove],
    )
    def rollback(self, request, pk=None):  # noqa: ARG002
        from .services import DeploymentService

        source = self.get_object()
        try:
            new_deployment = DeploymentService.rollback(source, triggered_by=request.user)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"deployment_id": new_deployment.id}, status=status.HTTP_202_ACCEPTED)
