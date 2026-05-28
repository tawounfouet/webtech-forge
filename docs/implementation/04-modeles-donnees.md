# 04 — Modèles de données

> **ADR de référence :** ADR-001, ADR-008, ADR-018
> **Dépendances :** 03-backend-django.md

---

## Vue d'ensemble des relations

```
Organization
  └── Workspace (+ WorkspaceMember, WorkspaceSecret, WorkspaceQuota)
        └── Project
              └── ProjectRepository
              └── Environment (+ PromotionPolicy)
                    └── Service (+ ServiceEnvVar, Domain, Volume, Healthcheck, ServiceBinding)
                          └── Deployment (+ DeploymentEvent, RollbackRecord)
        └── ServiceTemplate (catalog)
        └── ActivatorRule (+ ActivatorExecution)
        └── AuditLog
        └── ServerTarget (V3)
```

---

## Modèles complets

```python
# apps/organizations/models.py
from django.db import models


class Organization(models.Model):
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    billing_email = models.EmailField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name
```

```python
# apps/workspaces/models.py
from django.conf import settings
from django.db import models
from encrypted_fields.fields import EncryptedTextField


class Workspace(models.Model):
    organization = models.ForeignKey(
        "organizations.Organization", related_name="workspaces", on_delete=models.CASCADE
    )
    name = models.CharField(max_length=255)
    slug = models.SlugField()
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("organization", "slug")

    @property
    def docker_network_name(self):
        return f"forge-ws-{self.slug}"

    def __str__(self):
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
        settings.AUTH_USER_MODEL, null=True, related_name="+", on_delete=models.SET_NULL
    )

    class Meta:
        unique_together = ("workspace", "user")


class WorkspaceSecret(models.Model):
    workspace = models.ForeignKey(Workspace, related_name="secrets", on_delete=models.CASCADE)
    key = models.CharField(max_length=255)
    value = EncryptedTextField()
    description = models.CharField(max_length=255, blank=True)
    last_rotated_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("workspace", "key")


class WorkspaceQuota(models.Model):
    workspace = models.OneToOneField(Workspace, related_name="quota", on_delete=models.CASCADE)
    max_services = models.PositiveIntegerField(default=20)
    max_cpu_cores = models.PositiveIntegerField(default=8)
    max_memory_gb = models.FloatField(default=16.0)
    max_storage_gb = models.FloatField(default=50.0)
    max_deployments_kept = models.PositiveIntegerField(default=10)
    max_preview_environments = models.PositiveIntegerField(default=5)
    log_retention_days = models.PositiveIntegerField(default=30)
    backup_window_days = models.PositiveIntegerField(default=30)
```

```python
# apps/projects/models.py
from django.db import models


class Project(models.Model):
    workspace = models.ForeignKey(
        "workspaces.Workspace", related_name="projects", on_delete=models.CASCADE
    )
    name = models.CharField(max_length=255)
    slug = models.SlugField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("workspace", "slug")


class ProjectRepository(models.Model):
    project = models.ForeignKey(Project, related_name="repositories", on_delete=models.CASCADE)
    name = models.CharField(max_length=128)
    repo_url = models.URLField()
    default_branch = models.CharField(max_length=128, default="main")
    is_primary = models.BooleanField(default=False)
    webhook_secret = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
```

```python
# apps/environments/models.py
from django.conf import settings
from django.db import models


class Environment(models.Model):
    class Kind(models.TextChoices):
        DEVELOPMENT = "development", "Development"
        STAGING = "staging", "Staging"
        PREVIEW = "preview", "Preview"
        PRODUCTION = "production", "Production"

    project = models.ForeignKey(
        "projects.Project", related_name="environments", on_delete=models.CASCADE
    )
    name = models.CharField(max_length=128)
    slug = models.SlugField()
    kind = models.CharField(max_length=32, choices=Kind.choices)
    protected = models.BooleanField(default=False)
    auto_deploy_branch = models.CharField(max_length=128, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("project", "slug")


class PromotionPolicy(models.Model):
    environment = models.OneToOneField(Environment, on_delete=models.CASCADE)
    require_approval = models.BooleanField(default=False)
    min_approvers = models.PositiveIntegerField(default=1)
    auto_promote_from = models.ForeignKey(
        Environment, null=True, blank=True,
        related_name="auto_promotes_to", on_delete=models.SET_NULL
    )
    notify_channels = models.JSONField(default=list)
```

```python
# apps/services/models.py
from django.conf import settings
from django.db import models
from encrypted_fields.fields import EncryptedTextField


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
        "environments.Environment", related_name="services", on_delete=models.CASCADE
    )
    template = models.ForeignKey(
        "catalog.ServiceTemplate", null=True, blank=True, on_delete=models.SET_NULL
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
        "deployments.Deployment", null=True, blank=True,
        related_name="locking_service", on_delete=models.SET_NULL
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("environment", "slug")

    def acquire_deploy_lock(self, deployment):
        from django.core.exceptions import ValidationError
        updated = Service.objects.filter(
            pk=self.pk, active_deployment__isnull=True
        ).update(active_deployment=deployment)
        if not updated:
            raise ValidationError(f"Service {self.slug} already has an active deployment")


class ServiceEnvVar(models.Model):
    service = models.ForeignKey(Service, related_name="env_vars", on_delete=models.CASCADE)
    key = models.CharField(max_length=255)
    value = models.TextField(blank=True)
    is_secret = models.BooleanField(default=False)
    secret_ref = models.ForeignKey(
        "workspaces.WorkspaceSecret", null=True, blank=True, on_delete=models.SET_NULL
    )

    class Meta:
        unique_together = ("service", "key")


class Domain(models.Model):
    service = models.ForeignKey(Service, related_name="domains", on_delete=models.CASCADE)
    hostname = models.CharField(max_length=255)
    is_custom = models.BooleanField(default=False)
    tls_enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)


class Volume(models.Model):
    service = models.ForeignKey(Service, related_name="volumes", on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    mount_path = models.CharField(max_length=512)
    size_gb = models.FloatField(default=1.0)


class Healthcheck(models.Model):
    class Protocol(models.TextChoices):
        HTTP = "http", "HTTP"
        TCP = "tcp", "TCP"
        COMMAND = "command", "Command"

    service = models.OneToOneField(Service, on_delete=models.CASCADE)
    protocol = models.CharField(max_length=16, choices=Protocol.choices, default=Protocol.HTTP)
    path = models.CharField(max_length=255, default="/health")
    interval_seconds = models.PositiveIntegerField(default=30)
    timeout_seconds = models.PositiveIntegerField(default=5)
    retries = models.PositiveIntegerField(default=3)


class ServiceBinding(models.Model):
    class BindingType(models.TextChoices):
        LOCAL = "local", "Local"
        CROSS_ENV = "cross_env", "Cross-Environment"
        SHORTCUT = "shortcut", "ForgeStore Shortcut (V3)"

    source_service = models.ForeignKey(Service, related_name="bindings", on_delete=models.CASCADE)
    target_service = models.ForeignKey(Service, related_name="bound_by", on_delete=models.CASCADE)
    binding_type = models.CharField(max_length=32, choices=BindingType.choices)
    env_prefix = models.CharField(max_length=64, blank=True)
    allowed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL
    )
```

```python
# apps/deployments/models.py
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

    service = models.ForeignKey(
        "services.Service", related_name="deployments", on_delete=models.CASCADE
    )
    phase = models.CharField(max_length=16, choices=Phase.choices, default=Phase.BRONZE)
    commit_sha = models.CharField(max_length=64, blank=True)
    image_ref = models.CharField(max_length=512, blank=True)
    image_digest = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.PENDING)
    triggered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL
    )
    trigger_source = models.CharField(
        max_length=32,
        choices=[("manual","Manual"),("webhook","Webhook"),("promotion","Promotion"),("activator","Activator")],
        default="manual"
    )
    failure_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["service", "status"]),
            models.Index(fields=["service", "phase", "status"]),
        ]


class DeploymentEvent(models.Model):
    deployment = models.ForeignKey(Deployment, related_name="events", on_delete=models.CASCADE)
    phase = models.CharField(max_length=16)
    message = models.TextField()
    level = models.CharField(max_length=16, default="info")
    emitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["emitted_at"]


class RollbackRecord(models.Model):
    deployment = models.ForeignKey(Deployment, related_name="rollbacks", on_delete=models.CASCADE)
    rolled_back_to = models.ForeignKey(
        Deployment, related_name="restored_by", on_delete=models.CASCADE
    )
    triggered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL
    )
    trigger_source = models.CharField(max_length=32, default="manual")
    created_at = models.DateTimeField(auto_now_add=True)
```

---

## Indexes recommandés

```python
# À ajouter dans les Meta des modèles critiques

# Deployment — requêtes Monitor Hub fréquentes
class Meta:
    indexes = [
        models.Index(fields=["service", "status"]),
        models.Index(fields=["service", "phase", "status"]),
        models.Index(fields=["created_at"]),        # pour les filtres temporels
    ]

# AuditLog — requêtes audit fréquentes
class Meta:
    indexes = [
        models.Index(fields=["workspace", "created_at"]),
        models.Index(fields=["user", "created_at"]),
        models.Index(fields=["resource_type", "resource_id"]),
    ]
```

---

## Migrations — règles

1. Chaque migration est revue avant merge — pas de `makemigrations` automatisé en CI.
2. Les migrations destructives (suppression de colonne) passent par une migration en deux étapes (nullable → suppression).
3. La migration initiale inclut la création du custom User model.
4. Les données de seed (templates certifiés) sont dans des `data migrations` dédiées.
