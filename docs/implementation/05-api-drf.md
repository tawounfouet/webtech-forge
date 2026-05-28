# 05 — API DRF

> **ADR de référence :** ADR-002, ADR-008
> **Dépendances :** 04-modeles-donnees.md

---

## Principes

- **ViewSets** pour les ressources CRUD stables (Workspace, Project, Environment, Service).
- **Vues d'actions dédiées** pour les commandes métier : `deploy`, `rollback`, `promote`, `backup`, `endorse`.
- **Scoping Workspace systématique** dans chaque `get_queryset`.
- **Permissions object-level** via `has_object_permission`.
- **Throttling** : 300 req/min par utilisateur authentifié.

---

## Structure des URLs

```python
# config/urls.py
from django.urls import path, include

urlpatterns = [
    path("api/v1/auth/", include("apps.accounts.urls")),
    path("api/v1/", include("apps.organizations.urls")),
    path("api/v1/", include("apps.workspaces.urls")),
    path("api/v1/", include("apps.projects.urls")),
    path("api/v1/", include("apps.environments.urls")),
    path("api/v1/", include("apps.services.urls")),
    path("api/v1/", include("apps.deployments.urls")),
    path("api/v1/catalog/", include("apps.catalog.urls")),
    path("api/v1/monitor/", include("apps.monitor.urls")),
    path("api/v1/", include("apps.activator.urls")),
    path("api/v1/integrations/", include("apps.integrations.urls")),
]
```

---

## Permissions

```python
# apps/workspaces/permissions.py
from rest_framework.permissions import BasePermission
from .models import WorkspaceMember

ROLE_HIERARCHY = {
    "admin": 6,
    "maintainer": 5,
    "operator": 4,
    "developer": 3,
    "viewer": 2,
    "auditor": 1,
}


class WorkspacePermission(BasePermission):
    required_role = "viewer"

    def has_permission(self, request, view):
        if not request.workspace:
            return False
        user_role = getattr(request, "workspace_role", None)
        if not user_role:
            return False
        return ROLE_HIERARCHY.get(user_role, 0) >= ROLE_HIERARCHY.get(self.required_role, 0)


class IsWorkspaceAdmin(WorkspacePermission):
    required_role = "admin"


class IsOperatorOrAbove(WorkspacePermission):
    required_role = "operator"


class IsDeveloperOrAbove(WorkspacePermission):
    required_role = "developer"
```

---

## ViewSet de référence — Service

```python
# apps/services/views.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Service
from .serializers import ServiceSerializer, ServiceCreateSerializer
from apps.workspaces.permissions import IsOperatorOrAbove, IsDeveloperOrAbove


class ServiceViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, IsDeveloperOrAbove]
    serializer_class = ServiceSerializer

    def get_queryset(self):
        workspace = self.request.workspace
        qs = Service.objects.select_related(
            "environment__project__workspace",
            "template",
            "active_deployment",
        ).filter(
            environment__project__workspace=workspace
        )
        environment_id = self.request.query_params.get("environment")
        if environment_id:
            qs = qs.filter(environment_id=environment_id)
        return qs

    def get_serializer_class(self):
        if self.action == "create":
            return ServiceCreateSerializer
        return ServiceSerializer

    def has_object_permission(self, request, view, obj):
        return obj.environment.project.workspace == request.workspace

    @action(detail=True, methods=["post"], permission_classes=[IsOperatorOrAbove])
    def deploy(self, request, pk=None):
        service = self.get_object()
        from apps.deployments.services import DeploymentService
        deployment = DeploymentService.create_deployment(
            service=service,
            triggered_by=request.user,
            trigger_source="manual",
        )
        return Response({"deployment_id": deployment.id}, status=status.HTTP_202_ACCEPTED)

    @action(detail=True, methods=["get"])
    def deployments(self, request, pk=None):
        service = self.get_object()
        from apps.deployments.models import Deployment
        from apps.deployments.serializers import DeploymentListSerializer
        deployments = Deployment.objects.filter(service=service).order_by("-created_at")[:20]
        return Response(DeploymentListSerializer(deployments, many=True).data)
```

---

## Sérializer de référence — Deployment

```python
# apps/deployments/serializers.py
from rest_framework import serializers
from .models import Deployment, DeploymentEvent


class DeploymentEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeploymentEvent
        fields = ["id", "phase", "message", "level", "emitted_at"]


class DeploymentListSerializer(serializers.ModelSerializer):
    duration_seconds = serializers.SerializerMethodField()

    class Meta:
        model = Deployment
        fields = [
            "id", "phase", "status", "commit_sha", "image_ref",
            "trigger_source", "triggered_by", "failure_reason",
            "created_at", "started_at", "finished_at", "duration_seconds",
        ]

    def get_duration_seconds(self, obj):
        if obj.started_at and obj.finished_at:
            return (obj.finished_at - obj.started_at).total_seconds()
        return None


class DeploymentDetailSerializer(DeploymentListSerializer):
    events = DeploymentEventSerializer(many=True, read_only=True)

    class Meta(DeploymentListSerializer.Meta):
        fields = DeploymentListSerializer.Meta.fields + ["events"]
```

---

## Endpoint de déploiement et rollback

```python
# apps/deployments/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import Deployment
from .services import DeploymentService
from apps.workspaces.permissions import IsOperatorOrAbove


class DeploymentRollbackView(APIView):
    permission_classes = [IsAuthenticated, IsOperatorOrAbove]

    def post(self, request, deployment_id):
        try:
            deployment = Deployment.objects.select_related(
                "service__environment__project__workspace"
            ).get(pk=deployment_id)
        except Deployment.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        if deployment.service.environment.project.workspace != request.workspace:
            return Response(status=status.HTTP_403_FORBIDDEN)

        new_deployment = DeploymentService.rollback(
            deployment=deployment,
            triggered_by=request.user,
        )
        return Response({"deployment_id": new_deployment.id}, status=status.HTTP_202_ACCEPTED)
```

---

## Webhook GitHub

```python
# apps/integrations/views.py
import hashlib
import hmac
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from apps.projects.models import ProjectRepository
from apps.deployments.services import DeploymentService


class GitHubWebhookView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        signature = request.headers.get("X-Hub-Signature-256", "")
        repo_url = request.data.get("repository", {}).get("clone_url", "")

        try:
            repo = ProjectRepository.objects.select_related("project__workspace").get(
                repo_url=repo_url
            )
        except ProjectRepository.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        # Validation HMAC
        expected = "sha256=" + hmac.new(
            repo.webhook_secret.encode(),
            request.body,
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        branch = request.data.get("ref", "").replace("refs/heads/", "")
        DeploymentService.trigger_auto_deploy(repo=repo, branch=branch)
        return Response({"ok": True})
```

---

## OpenAPI / Documentation

```python
# config/settings/base.py
SPECTACULAR_SETTINGS = {
    "TITLE": "WebTech Forge API",
    "DESCRIPTION": "Control plane PaaS interne — v1",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
}
```

Générer le schéma :
```bash
python manage.py spectacular --file openapi.yaml --validate
```

Générer les types TypeScript frontend :
```bash
npx openapi-typescript ../backend/openapi.yaml -o frontend/lib/api.d.ts
```
