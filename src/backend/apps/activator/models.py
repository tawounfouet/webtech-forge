from django.conf import settings
from django.db import models


class ActivatorRule(models.Model):
    class Metric(models.TextChoices):
        CPU_PERCENT = "cpu_percent", "CPU %"
        MEMORY_PERCENT = "memory_percent", "Memory %"
        HTTP_5XX_RATE = "http_5xx_rate", "HTTP 5xx rate"
        DEPLOYMENT_FAILURE_RATE = "deployment_failure_rate", "Deployment failure rate"
        HEALTHCHECK_FAILURES = "healthcheck_failures", "Healthcheck failures"

    class Operator(models.TextChoices):
        GT = "gt", ">"
        GTE = "gte", ">="
        LT = "lt", "<"
        LTE = "lte", "<="
        EQ = "eq", "=="

    class Action(models.TextChoices):
        ROLLBACK = "rollback", "Rollback"
        SCALE_UP = "scale_up", "Scale up"
        SCALE_DOWN = "scale_down", "Scale down"
        ALERT = "alert", "Alert only"
        DISABLE_SERVICE = "disable_service", "Disable service"

    workspace = models.ForeignKey(
        "workspaces.Workspace",
        related_name="activator_rules",
        on_delete=models.CASCADE,
    )
    service = models.ForeignKey(
        "services.Service",
        null=True,
        blank=True,
        related_name="activator_rules",
        on_delete=models.CASCADE,
    )
    name = models.CharField(max_length=255)
    metric = models.CharField(max_length=64, choices=Metric.choices)
    operator = models.CharField(max_length=8, choices=Operator.choices)
    threshold = models.FloatField()
    action = models.CharField(max_length=32, choices=Action.choices)
    cooldown_seconds = models.PositiveIntegerField(default=300)
    is_active = models.BooleanField(default=True)
    circuit_open = models.BooleanField(default=False)
    circuit_opened_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.name} [{self.metric} {self.operator} {self.threshold}]"


class ActivatorExecution(models.Model):
    class Result(models.TextChoices):
        TRIGGERED = "triggered", "Triggered"
        SKIPPED_COOLDOWN = "skipped_cooldown", "Skipped (cooldown)"
        SKIPPED_CIRCUIT = "skipped_circuit", "Skipped (circuit open)"
        FAILED = "failed", "Failed"

    rule = models.ForeignKey(
        ActivatorRule, related_name="executions", on_delete=models.CASCADE
    )
    measured_value = models.FloatField()
    result = models.CharField(max_length=32, choices=Result.choices)
    action_taken = models.CharField(max_length=64, blank=True)
    error_message = models.TextField(blank=True)
    executed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-executed_at"]

    def __str__(self) -> str:
        return f"Execution({self.rule}) → {self.result}"
