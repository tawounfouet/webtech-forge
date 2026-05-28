# 09 — Monitor Hub

> **ADR de référence :** ADR-020
> **Dépendances :** 04-modeles-donnees.md, 05-api-drf.md

---

## Principe

Le Monitor Hub est une **API en lecture seule** qui agrège des données déjà présentes dans PostgreSQL. Aucun stockage supplémentaire. Il coexiste avec Grafana (métriques infra) sans le remplacer.

| Monitor Hub | Grafana |
|---|---|
| Qui a déployé quoi, quand | CPU, mémoire, latence réseau |
| Alertes Activator déclenchées | Métriques Prometheus |
| Capacité consommée par workspace | Dashboards infra |
| Services dégradés (business) | Alertes infra |

---

## Endpoints

```python
# apps/monitor/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path("activity/", views.ActivityView.as_view()),
    path("capacity/", views.CapacityView.as_view()),
    path("alerts/", views.AlertsView.as_view()),
    path("degraded/", views.DegradedView.as_view()),
]
```

---

## Vues

```python
# apps/monitor/views.py
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from apps.deployments.models import Deployment, DeploymentEvent
from apps.audit.models import AuditLog
from apps.activator.models import ActivatorExecution
from apps.services.models import Service
from apps.workspaces.permissions import IsWorkspaceAdmin


class ActivityView(APIView):
    """
    Flux d'activité business filtrable.
    OrganizationOwner : cross-workspace.
    WorkspaceAdmin/Operator : workspace uniquement.
    """
    def get(self, request):
        since_hours = int(request.query_params.get("since_hours", 24))
        kind = request.query_params.get("kind", "deployment,backup,rollback,activator")
        since = timezone.now() - timezone.timedelta(hours=since_hours)
        kinds = kind.split(",")

        events = []

        if "deployment" in kinds or "rollback" in kinds:
            qs = Deployment.objects.select_related(
                "service__environment__project__workspace",
                "triggered_by",
            ).filter(created_at__gte=since)

            if not request.user.is_superuser:
                qs = qs.filter(service__environment__project__workspace=request.workspace)

            for d in qs.order_by("-created_at")[:100]:
                events.append({
                    "type": "rollback" if d.trigger_source == "manual" and d.phase == "gold" else "deployment",
                    "workspace": d.service.environment.project.workspace.slug,
                    "project": d.service.environment.project.slug,
                    "service": d.service.slug,
                    "status": d.status,
                    "phase": d.phase,
                    "trigger_source": d.trigger_source,
                    "triggered_by": d.triggered_by.email if d.triggered_by else "system",
                    "at": d.created_at.isoformat(),
                    "duration_seconds": (
                        (d.finished_at - d.started_at).total_seconds()
                        if d.started_at and d.finished_at else None
                    ),
                })

        if "activator" in kinds:
            qs = ActivatorExecution.objects.select_related(
                "rule__workspace"
            ).filter(triggered_at__gte=since)
            if not request.user.is_superuser:
                qs = qs.filter(rule__workspace=request.workspace)

            for ex in qs.order_by("-triggered_at")[:50]:
                events.append({
                    "type": "activator_action",
                    "workspace": ex.rule.workspace.slug,
                    "rule": ex.rule.name,
                    "action": ex.rule.action_type,
                    "metric_value": ex.metric_value,
                    "success": ex.success,
                    "at": ex.triggered_at.isoformat(),
                })

        events.sort(key=lambda e: e["at"], reverse=True)
        return Response({"events": events[:200]})


class CapacityView(APIView):
    """
    Consommation de ressources par workspace.
    OrganizationOwner uniquement.
    """
    def get(self, request):
        if not request.user.is_superuser:
            workspace = request.workspace
            return Response({"workspaces": [self._workspace_capacity(workspace)]})

        from apps.workspaces.models import Workspace
        workspaces = Workspace.objects.select_related("quota").filter(
            organization=request.workspace.organization
        )
        return Response({
            "workspaces": [self._workspace_capacity(w) for w in workspaces]
        })

    def _workspace_capacity(self, workspace):
        service_count = Service.objects.filter(
            environment__project__workspace=workspace
        ).count()
        active_deployments = Deployment.objects.filter(
            service__environment__project__workspace=workspace,
            status=Deployment.Status.SUCCESS,
        ).count()
        quota = getattr(workspace, "quota", None)
        return {
            "workspace": workspace.slug,
            "services": service_count,
            "active_deployments": active_deployments,
            "quota": {
                "max_services": quota.max_services if quota else None,
                "used_pct": round(service_count / quota.max_services * 100, 1) if quota else None,
            },
        }


class AlertsView(APIView):
    """Alertes Activator déclenchées."""
    def get(self, request):
        since_hours = int(request.query_params.get("since_hours", 48))
        since = timezone.now() - timezone.timedelta(hours=since_hours)
        qs = ActivatorExecution.objects.select_related("rule__workspace").filter(
            triggered_at__gte=since
        )
        if not request.user.is_superuser:
            qs = qs.filter(rule__workspace=request.workspace)

        return Response({
            "alerts": [
                {
                    "rule": ex.rule.name,
                    "workspace": ex.rule.workspace.slug,
                    "action": ex.rule.action_type,
                    "metric_value": ex.metric_value,
                    "success": ex.success,
                    "at": ex.triggered_at.isoformat(),
                }
                for ex in qs.order_by("-triggered_at")[:100]
            ]
        })


class DegradedView(APIView):
    """Services en état FAILED ou ROLLED_BACK au cours des dernières 24h."""
    def get(self, request):
        since = timezone.now() - timezone.timedelta(hours=24)
        qs = Deployment.objects.select_related(
            "service__environment__project__workspace"
        ).filter(
            status__in=[Deployment.Status.FAILED, Deployment.Status.ROLLED_BACK],
            created_at__gte=since,
        )
        if not request.user.is_superuser:
            qs = qs.filter(service__environment__project__workspace=request.workspace)

        return Response({
            "degraded_services": [
                {
                    "workspace": d.service.environment.project.workspace.slug,
                    "service": d.service.slug,
                    "status": d.status,
                    "phase": d.phase,
                    "failure_reason": d.failure_reason,
                    "at": d.created_at.isoformat(),
                }
                for d in qs.order_by("-created_at")[:50]
            ]
        })
```

---

## Export CSV

Chaque endpoint supporte `?format=csv` pour les rapports ops :

```python
# apps/monitor/renderers.py
import csv
import io
from rest_framework.renderers import BaseRenderer


class CSVRenderer(BaseRenderer):
    media_type = "text/csv"
    format = "csv"

    def render(self, data, accepted_media_type=None, renderer_context=None):
        if not data:
            return ""
        rows = data.get("events") or data.get("alerts") or data.get("degraded_services") or []
        if not rows:
            return ""
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
        return output.getvalue()
```
