from django.conf import settings
from django.db import models


class AuditLog(models.Model):
    workspace = models.ForeignKey(
        "workspaces.Workspace",
        null=True,
        related_name="audit_logs",
        on_delete=models.SET_NULL,
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        related_name="audit_logs",
        on_delete=models.SET_NULL,
    )
    action = models.CharField(max_length=512)
    resource_type = models.CharField(max_length=64, blank=True)
    resource_id = models.CharField(max_length=64, blank=True)
    http_status = models.PositiveSmallIntegerField(null=True)
    ip_address = models.GenericIPAddressField(null=True)
    metadata = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["workspace", "created_at"]),
            models.Index(fields=["user", "created_at"]),
            models.Index(fields=["resource_type", "resource_id"]),
        ]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"[{self.action}] by {self.user} @ {self.created_at:%Y-%m-%d %H:%M}"
