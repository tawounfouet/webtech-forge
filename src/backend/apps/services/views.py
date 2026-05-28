from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.workspaces.permissions import IsDeveloperOrAbove, IsOperatorOrAbove

from .models import Service
from .serializers import ServiceCreateSerializer, ServiceDetailSerializer, ServiceSerializer


class ServiceViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, IsDeveloperOrAbove]

    def get_queryset(self):
        qs = Service.objects.select_related(
            "environment__project__workspace",
            "template",
            "active_deployment",
        ).filter(environment__project__workspace=self.request.workspace)

        env_id = self.request.query_params.get("environment")
        if env_id:
            qs = qs.filter(environment_id=env_id)
        return qs

    def get_serializer_class(self):
        if self.action == "create":
            return ServiceCreateSerializer
        if self.action == "retrieve":
            return ServiceDetailSerializer
        return ServiceSerializer

    def has_object_permission(self, request, view, obj):
        return obj.environment.project.workspace == request.workspace

    # ── Actions métier ────────────────────────────────────────────────────────

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[IsAuthenticated, IsOperatorOrAbove],
    )
    def deploy(self, request, pk=None):
        service = self.get_object()
        from apps.deployments.models import Deployment
        from apps.deployments.tasks import run_deployment

        deployment = Deployment.objects.create(
            service=service,
            triggered_by=request.user,
            trigger_source=Deployment.TriggerSource.MANUAL,
            status=Deployment.Status.PENDING,
            phase=Deployment.Phase.BRONZE,
        )
        run_deployment.delay(deployment.id)
        return Response({"deployment_id": deployment.id}, status=status.HTTP_202_ACCEPTED)

    @action(detail=True, methods=["get"])
    def deployments(self, request, pk=None):
        service = self.get_object()
        from apps.deployments.models import Deployment
        from apps.deployments.serializers import DeploymentListSerializer

        qs = Deployment.objects.filter(service=service).order_by("-created_at")[:20]
        return Response(DeploymentListSerializer(qs, many=True).data)
