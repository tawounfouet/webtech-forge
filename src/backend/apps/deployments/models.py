from django.conf import settings
from django.db import models


class Deployment(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        QUEUED = "queued", "Queued"
        CLONING = "cloning", "Cloning"
        VALIDATING = "validating", "Validating"
        BUILDING = "building", "Building"
        RELEASING = "releasing", "Releasing"
        HEALTHCHECKING = "healthchecking", "Healthchecking"
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"
        ROLLED_BACK = "rolled_back", "Rolled Back"

    class Phase(models.TextChoices):
        BRONZE = "bronze", "Bronze"
        SILVER = "silver", "Silver"
        GOLD = "gold", "Gold"

    class TriggerSource(models.TextChoices):
        MANUAL = "manual", "Manual"
        WEBHOOK = "webhook", "Webhook"
        PROMOTION = "promotion", "Promotion"
        ACTIVATOR = "activator", "Activator"

    service = models.ForeignKey(
        "services.Service",
        related_name="deployments",
        on_delete=models.CASCADE,
    )
    phase = models.CharField(max_length=16, choices=Phase.choices, default=Phase.BRONZE)
    commit_sha = models.CharField(max_length=64, blank=True)
    image_ref = models.CharField(max_length=512, blank=True)
    image_digest = models.CharField(max_length=255, blank=True)
    status = models.CharField(
        max_length=32, choices=Status.choices, default=Status.PENDING
    )
    triggered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL
    )
    trigger_source = models.CharField(
        max_length=32, choices=TriggerSource.choices, default=TriggerSource.MANUAL
    )
    failure_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["service", "status"]),
            models.Index(fields=["service", "phase", "status"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self) -> str:
        return f"Deployment#{self.pk} {self.service} [{self.status}]"


class DeploymentEvent(models.Model):
    class Level(models.TextChoices):
        DEBUG = "debug", "Debug"
        INFO = "info", "Info"
        WARNING = "warning", "Warning"
        ERROR = "error", "Error"

    deployment = models.ForeignKey(
        Deployment, related_name="events", on_delete=models.CASCADE
    )
    phase = models.CharField(max_length=16)
    message = models.TextField()
    level = models.CharField(max_length=16, choices=Level.choices, default=Level.INFO)
    emitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["emitted_at"]

    def __str__(self) -> str:
        return f"[{self.level}] {self.message[:80]}"


class RollbackRecord(models.Model):
    class TriggerSource(models.TextChoices):
        MANUAL = "manual", "Manual"
        ACTIVATOR = "activator", "Activator (auto)"
        HEALTHCHECK = "healthcheck", "Healthcheck failure"

    deployment = models.ForeignKey(
        Deployment, related_name="rollbacks", on_delete=models.CASCADE
    )
    rolled_back_to = models.ForeignKey(
        Deployment, related_name="restored_by", on_delete=models.CASCADE
    )
    triggered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL
    )
    trigger_source = models.CharField(
        max_length=32, choices=TriggerSource.choices, default=TriggerSource.MANUAL
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"Rollback {self.deployment} → {self.rolled_back_to}"
