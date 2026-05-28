from django.conf import settings
from django.db import models
from encrypted_model_fields.fields import EncryptedTextField


class Workspace(models.Model):
    organization = models.ForeignKey(
        "organizations.Organization",
        related_name="workspaces",
        on_delete=models.CASCADE,
    )
    name = models.CharField(max_length=255)
    slug = models.SlugField()
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("organization", "slug")

    @property
    def docker_network_name(self) -> str:
        return f"forge-ws-{self.slug}"

    def __str__(self) -> str:
        return f"{self.organization.slug}/{self.slug}"


class WorkspaceMember(models.Model):
    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        MAINTAINER = "maintainer", "Maintainer"
        OPERATOR = "operator", "Operator"
        DEVELOPER = "developer", "Developer"
        VIEWER = "viewer", "Viewer"
        AUDITOR = "auditor", "Auditor"

    workspace = models.ForeignKey(Workspace, related_name="members", on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    role = models.CharField(max_length=32, choices=Role.choices)
    added_at = models.DateTimeField(auto_now_add=True)
    added_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        related_name="+",
        on_delete=models.SET_NULL,
    )

    class Meta:
        unique_together = ("workspace", "user")

    def __str__(self) -> str:
        return f"{self.user} @ {self.workspace} [{self.role}]"


class WorkspaceSecret(models.Model):
    workspace = models.ForeignKey(Workspace, related_name="secrets", on_delete=models.CASCADE)
    key = models.CharField(max_length=255)
    value = EncryptedTextField()
    description = models.CharField(max_length=255, blank=True)
    last_rotated_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("workspace", "key")

    def __str__(self) -> str:
        return f"{self.workspace}/{self.key}"


class WorkspaceQuota(models.Model):
    workspace = models.OneToOneField(
        Workspace, related_name="quota", on_delete=models.CASCADE
    )
    max_services = models.PositiveIntegerField(default=20)
    max_cpu_cores = models.PositiveIntegerField(default=8)
    max_memory_gb = models.FloatField(default=16.0)
    max_storage_gb = models.FloatField(default=50.0)
    max_deployments_kept = models.PositiveIntegerField(default=10)
    max_preview_environments = models.PositiveIntegerField(default=5)
    log_retention_days = models.PositiveIntegerField(default=30)
    backup_window_days = models.PositiveIntegerField(default=30)

    def __str__(self) -> str:
        return f"Quota({self.workspace})"
