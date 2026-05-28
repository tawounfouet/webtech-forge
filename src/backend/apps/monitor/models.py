from django.db import models


class MonitorSnapshot(models.Model):
    """Snapshot périodique d'état du workspace pour le Monitor Hub."""

    workspace = models.ForeignKey(
        "workspaces.Workspace",
        related_name="monitor_snapshots",
        on_delete=models.CASCADE,
    )
    total_services = models.PositiveIntegerField(default=0)
    running_services = models.PositiveIntegerField(default=0)
    failed_services = models.PositiveIntegerField(default=0)
    total_deployments_last_24h = models.PositiveIntegerField(default=0)
    failed_deployments_last_24h = models.PositiveIntegerField(default=0)
    cpu_usage_percent = models.FloatField(null=True, blank=True)
    memory_usage_percent = models.FloatField(null=True, blank=True)
    captured_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["workspace", "captured_at"]),
        ]
        ordering = ["-captured_at"]

    def __str__(self) -> str:
        return f"Snapshot({self.workspace} @ {self.captured_at:%Y-%m-%d %H:%M})"
