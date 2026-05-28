from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class Service(models.Model):
    class Type(models.TextChoices):
        WEB = "web", "Web"
        API = "api", "API"
        WORKER = "worker", "Worker"
        CRON = "cron", "Cron"
        DATABASE = "database", "Database"
        CACHE = "cache", "Cache"
        STORAGE = "storage", "Storage"

    class Runtime(models.TextChoices):
        DOCKERFILE = "dockerfile", "Dockerfile"
        COMPOSE = "compose", "Compose"
        IMAGE = "image", "Image"

    environment = models.ForeignKey(
        "environments.Environment",
        related_name="services",
        on_delete=models.CASCADE,
    )
    template = models.ForeignKey(
        "catalog.ServiceTemplate",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    name = models.CharField(max_length=255)
    slug = models.SlugField()
    service_type = models.CharField(max_length=32, choices=Type.choices)
    runtime = models.CharField(max_length=32, choices=Runtime.choices)
    image = models.CharField(max_length=512, blank=True)
    dockerfile_path = models.CharField(max_length=255, default="Dockerfile")
    compose_file_path = models.CharField(max_length=255, blank=True)
    build_context = models.CharField(max_length=255, default=".")
    internal_port = models.PositiveIntegerField(default=8000)
    replicas = models.PositiveIntegerField(default=1)
    active_deployment = models.OneToOneField(
        "deployments.Deployment",
        null=True,
        blank=True,
        related_name="locking_service",
        on_delete=models.SET_NULL,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("environment", "slug")

    def acquire_deploy_lock(self, deployment: "deployments.Deployment") -> None:  # type: ignore[name-defined]
        updated = Service.objects.filter(
            pk=self.pk, active_deployment__isnull=True
        ).update(active_deployment=deployment)
        if not updated:
            raise ValidationError(f"Service {self.slug} already has an active deployment")

    def __str__(self) -> str:
        return f"{self.environment}/{self.slug}"


class ServiceEnvVar(models.Model):
    service = models.ForeignKey(Service, related_name="env_vars", on_delete=models.CASCADE)
    key = models.CharField(max_length=255)
    value = models.TextField(blank=True)
    is_secret = models.BooleanField(default=False)
    secret_ref = models.ForeignKey(
        "workspaces.WorkspaceSecret",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )

    class Meta:
        unique_together = ("service", "key")

    def __str__(self) -> str:
        return f"{self.service}/{self.key}"


class Domain(models.Model):
    service = models.ForeignKey(Service, related_name="domains", on_delete=models.CASCADE)
    hostname = models.CharField(max_length=255)
    is_custom = models.BooleanField(default=False)
    tls_enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.hostname


class Volume(models.Model):
    service = models.ForeignKey(Service, related_name="volumes", on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    mount_path = models.CharField(max_length=512)
    size_gb = models.FloatField(default=1.0)

    def __str__(self) -> str:
        return f"{self.service}/{self.name}"


class Healthcheck(models.Model):
    class Protocol(models.TextChoices):
        HTTP = "http", "HTTP"
        TCP = "tcp", "TCP"
        COMMAND = "command", "Command"

    service = models.OneToOneField(
        Service, related_name="healthcheck", on_delete=models.CASCADE
    )
    protocol = models.CharField(
        max_length=16, choices=Protocol.choices, default=Protocol.HTTP
    )
    path = models.CharField(max_length=255, default="/health")
    interval_seconds = models.PositiveIntegerField(default=30)
    timeout_seconds = models.PositiveIntegerField(default=5)
    retries = models.PositiveIntegerField(default=3)

    def __str__(self) -> str:
        return f"Healthcheck({self.service})"


class ServiceBinding(models.Model):
    class BindingType(models.TextChoices):
        LOCAL = "local", "Local"
        CROSS_ENV = "cross_env", "Cross-Environment"
        SHORTCUT = "shortcut", "ForgeStore Shortcut (V3)"

    source_service = models.ForeignKey(
        Service, related_name="bindings", on_delete=models.CASCADE
    )
    target_service = models.ForeignKey(
        Service, related_name="bound_by", on_delete=models.CASCADE
    )
    binding_type = models.CharField(max_length=32, choices=BindingType.choices)
    env_prefix = models.CharField(max_length=64, blank=True)
    allowed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL
    )

    def __str__(self) -> str:
        return f"{self.source_service} → {self.target_service} [{self.binding_type}]"
