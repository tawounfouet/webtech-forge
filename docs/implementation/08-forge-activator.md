# 08 — Forge Activator

> **ADR de référence :** ADR-017
> **Dépendances :** 06-workers-celery.md, 17-observabilite.md

---

## Modèles

```python
# apps/activator/models.py
from django.conf import settings
from django.db import models
from django.utils import timezone


class ActivatorRule(models.Model):
    class TargetType(models.TextChoices):
        SERVICE = "service", "Service"
        DEPLOYMENT = "deployment", "Deployment"
        WORKSPACE = "workspace", "Workspace"

    class ConditionOperator(models.TextChoices):
        GT = "gt", "Greater than"
        LT = "lt", "Less than"
        GTE = "gte", "Greater or equal"
        LTE = "lte", "Less or equal"
        EQ = "eq", "Equal to"
        CHANGE = "change", "Changes to"

    class ActionType(models.TextChoices):
        ROLLBACK = "rollback", "Auto-rollback"
        ALERT_EMAIL = "alert_email", "Email alert"
        ALERT_SLACK = "alert_slack", "Slack alert"
        WEBHOOK = "webhook", "Webhook"
        REDEPLOY = "redeploy", "Trigger redeploy"

    workspace = models.ForeignKey(
        "workspaces.Workspace", related_name="activator_rules", on_delete=models.CASCADE
    )
    name = models.CharField(max_length=255)
    target_type = models.CharField(max_length=32, choices=TargetType.choices)
    target_id = models.PositiveIntegerField(null=True, blank=True)
    condition_metric = models.CharField(max_length=128)
    condition_operator = models.CharField(max_length=16, choices=ConditionOperator.choices)
    condition_threshold = models.FloatField()
    condition_duration_seconds = models.PositiveIntegerField(default=300)
    action_type = models.CharField(max_length=32, choices=ActionType.choices)
    action_payload = models.JSONField(default=dict)
    circuit_breaker_limit = models.PositiveIntegerField(default=5)
    enabled = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def evaluate(self, value: float) -> bool:
        ops = {
            "gt": lambda v, t: v > t,
            "lt": lambda v, t: v < t,
            "gte": lambda v, t: v >= t,
            "lte": lambda v, t: v <= t,
            "eq": lambda v, t: v == t,
        }
        fn = ops.get(self.condition_operator)
        return fn(value, self.condition_threshold) if fn else False

    def executions_last_hour(self) -> int:
        one_hour_ago = timezone.now() - timezone.timedelta(hours=1)
        return self.executions.filter(triggered_at__gte=one_hour_ago).count()


class ActivatorExecution(models.Model):
    rule = models.ForeignKey(ActivatorRule, related_name="executions", on_delete=models.CASCADE)
    triggered_at = models.DateTimeField(auto_now_add=True)
    metric_value = models.FloatField()
    action_result = models.TextField(blank=True)
    success = models.BooleanField(default=True)
    error_message = models.TextField(blank=True)
```

---

## Tasks Celery

```python
# apps/activator/tasks.py
from celery import shared_task
from .models import ActivatorRule, ActivatorExecution
from adapters.metrics_adapter import MetricsAdapter


@shared_task(queue="activator")
def evaluate_activator_rules():
    for rule in ActivatorRule.objects.filter(enabled=True).select_related("workspace"):
        # Circuit-breaker
        if rule.executions_last_hour() >= rule.circuit_breaker_limit:
            continue
        try:
            value = MetricsAdapter.query(
                metric=rule.condition_metric,
                target_type=rule.target_type,
                target_id=rule.target_id,
                duration_seconds=rule.condition_duration_seconds,
            )
            if rule.evaluate(value):
                execute_activator_action.apply_async(
                    args=[rule.id, value],
                    queue="activator",
                )
        except Exception:
            pass  # ne pas bloquer l'évaluation des autres règles


@shared_task(queue="activator")
def execute_activator_action(rule_id: int, metric_value: float):
    rule = ActivatorRule.objects.select_related("workspace").get(pk=rule_id)
    executor = ActionExecutor(rule)
    success, result, error = executor.run()
    ActivatorExecution.objects.create(
        rule=rule,
        metric_value=metric_value,
        action_result=result,
        success=success,
        error_message=error or "",
    )
    # Journaliser dans l'AuditLog
    from apps.audit.models import AuditLog
    AuditLog.objects.create(
        workspace=rule.workspace,
        action=f"activator.{rule.action_type}",
        resource_type=rule.target_type,
        resource_id=str(rule.target_id or ""),
        metadata={"rule_id": rule.id, "metric_value": metric_value, "success": success},
    )
```

---

## ActionExecutor

```python
# apps/activator/executors.py
import requests
from django.conf import settings
from django.core.mail import send_mail


class ActionExecutor:
    def __init__(self, rule):
        self.rule = rule

    def run(self) -> tuple[bool, str, str | None]:
        try:
            result = self._dispatch()
            return True, result, None
        except Exception as exc:
            return False, "", str(exc)

    def _dispatch(self) -> str:
        action = self.rule.action_type
        if action == "rollback":
            return self._do_rollback()
        elif action == "redeploy":
            return self._do_redeploy()
        elif action == "alert_email":
            return self._send_email()
        elif action == "alert_slack":
            return self._send_slack()
        elif action == "webhook":
            return self._call_webhook()
        raise ValueError(f"Unknown action: {action}")

    def _do_rollback(self) -> str:
        from apps.services.models import Service
        from apps.deployments.services import DeploymentService
        service = Service.objects.get(pk=self.rule.target_id)
        last_success = service.deployments.filter(status="success").order_by("-finished_at").first()
        if not last_success:
            raise ValueError("No successful deployment to rollback to")
        DeploymentService.rollback(last_success, triggered_by=None)
        return f"Rolled back service {service.slug}"

    def _do_redeploy(self) -> str:
        from apps.services.models import Service
        from apps.deployments.services import DeploymentService
        service = Service.objects.get(pk=self.rule.target_id)
        DeploymentService.create_deployment(service, triggered_by=None, trigger_source="activator")
        return f"Redeployed service {service.slug}"

    def _send_email(self) -> str:
        payload = self.rule.action_payload
        send_mail(
            subject=payload.get("subject", f"[WebTech Forge] Activator alert: {self.rule.name}"),
            message=payload.get("body", f"Rule '{self.rule.name}' was triggered."),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=payload.get("recipients", []),
        )
        return "Email sent"

    def _send_slack(self) -> str:
        payload = self.rule.action_payload
        resp = requests.post(
            payload["webhook_url"],
            json={"text": payload.get("message", f":alert: Forge Activator: *{self.rule.name}* triggered")},
            timeout=10,
        )
        resp.raise_for_status()
        return "Slack message sent"

    def _call_webhook(self) -> str:
        payload = self.rule.action_payload
        resp = requests.post(
            payload["url"],
            json={"rule": self.rule.name, "workspace": self.rule.workspace.slug},
            headers={"Authorization": f"Bearer {payload.get('token', '')}"},
            timeout=15,
        )
        resp.raise_for_status()
        return f"Webhook called: {resp.status_code}"
```

---

## MetricsAdapter

```python
# adapters/metrics_adapter.py
import requests
from django.conf import settings


METRIC_QUERIES = {
    "cpu_usage": 'avg(rate(container_cpu_usage_seconds_total{{forge_service_id="{target_id}"}}[{duration}s]))',
    "memory_pct": 'avg(container_memory_usage_bytes{{forge_service_id="{target_id}"}}) / avg(container_spec_memory_limit_bytes{{forge_service_id="{target_id}"}}) * 100',
    "error_rate": 'sum(rate(forge_deployment_failures_total{{service_id="{target_id}"}}[{duration}s]))',
    "deploy_fail_count": 'sum_over_time(forge_deployment_failures_total{{service_id="{target_id}"}}[{duration}s])',
}


class MetricsAdapter:
    @staticmethod
    def query(metric: str, target_type: str, target_id: int | None, duration_seconds: int) -> float:
        query_template = METRIC_QUERIES.get(metric)
        if not query_template:
            raise ValueError(f"Unknown metric: {metric}")

        query = query_template.format(target_id=target_id or "", duration=duration_seconds)
        resp = requests.get(
            f"{settings.PROMETHEUS_URL}/api/v1/query",
            params={"query": query},
            timeout=10,
        )
        resp.raise_for_status()
        result = resp.json()["data"]["result"]
        if not result:
            return 0.0
        return float(result[0]["value"][1])
```

---

## Endpoints API

```python
# apps/activator/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path("workspaces/<slug:workspace_slug>/activator/rules/", views.ActivatorRuleListCreateView.as_view()),
    path("workspaces/<slug:workspace_slug>/activator/rules/<int:pk>/", views.ActivatorRuleDetailView.as_view()),
    path("activator/rules/<int:pk>/executions/", views.ActivatorExecutionListView.as_view()),
]
```

---

## Règles de sécurité

- Les règles `ROLLBACK` et `REDEPLOY` nécessitent le rôle `WorkspaceAdmin`.
- Le circuit-breaker (max N exécutions/heure) est vérifié avant chaque évaluation.
- Chaque exécution est loguée dans `AuditLog` avec `action="activator.{type}"`.
- Un endpoint `PATCH /activator/rules/{id}/` permet de désactiver une règle en urgence.
