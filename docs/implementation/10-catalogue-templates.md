# 10 — Catalogue de Templates & Endorsement

> **ADR de référence :** ADR-021
> **Dépendances :** 04-modeles-donnees.md, 05-api-drf.md

---

## Modèles

```python
# apps/catalog/models.py
from django.conf import settings
from django.db import models


class EndorsementStatus(models.TextChoices):
    EXPERIMENTAL = "experimental", "Experimental"
    PROMOTED = "promoted", "Promoted"
    CERTIFIED = "certified", "Certified"


class ServiceTemplate(models.Model):
    workspace = models.ForeignKey(
        "workspaces.Workspace", null=True, blank=True,
        related_name="templates", on_delete=models.CASCADE,
        help_text="null = template global Organisation"
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    endorsement = models.CharField(
        max_length=32, choices=EndorsementStatus.choices,
        default=EndorsementStatus.EXPERIMENTAL,
    )
    template_config = models.JSONField()
    version = models.CharField(max_length=16, default="1.0.0")
    endorsed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        related_name="endorsed_templates", on_delete=models.SET_NULL,
    )
    endorsed_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.endorsement})"
```

---

## Templates de seed — Data Migration

```python
# apps/catalog/migrations/0002_seed_certified_templates.py
from django.db import migrations

CERTIFIED_TEMPLATES = [
    {
        "name": "Django Web + PostgreSQL",
        "description": "Application web Django avec base PostgreSQL managée et backup quotidien.",
        "endorsement": "certified",
        "version": "1.0.0",
        "template_config": {
            "service_type": "web",
            "runtime": "dockerfile",
            "internal_port": 8000,
            "healthcheck": {"path": "/health/", "interval": 30, "timeout": 5, "retries": 3},
            "env_defaults": {
                "DJANGO_SETTINGS_MODULE": "config.settings.production",
                "PYTHONUNBUFFERED": "1",
            },
            "required_secrets": ["DATABASE_URL", "SECRET_KEY"],
            "linked_services": [
                {
                    "type": "database",
                    "image": "postgres:16-alpine",
                    "backup": {"enabled": True, "schedule": "0 2 * * *", "retention_days": 30},
                }
            ],
        },
    },
    {
        "name": "Next.js Standalone",
        "description": "Application Next.js App Router déployée en mode standalone Docker.",
        "endorsement": "certified",
        "version": "1.0.0",
        "template_config": {
            "service_type": "web",
            "runtime": "dockerfile",
            "internal_port": 3000,
            "healthcheck": {"path": "/api/health", "interval": 30, "timeout": 5, "retries": 3},
            "env_defaults": {"NODE_ENV": "production", "NEXT_TELEMETRY_DISABLED": "1"},
        },
    },
    {
        "name": "Redis Cache",
        "description": "Instance Redis managée pour cache et sessions.",
        "endorsement": "certified",
        "version": "1.0.0",
        "template_config": {
            "service_type": "cache",
            "runtime": "image",
            "image": "redis:7-alpine",
            "internal_port": 6379,
            "volumes": [{"name": "redis-data", "mount_path": "/data"}],
        },
    },
    {
        "name": "Celery Worker",
        "description": "Worker Celery pour tâches asynchrones.",
        "endorsement": "promoted",
        "version": "1.0.0",
        "template_config": {
            "service_type": "worker",
            "runtime": "dockerfile",
            "command": "celery -A config worker -l info --concurrency 2",
            "required_secrets": ["DATABASE_URL", "REDIS_BROKER_URL"],
        },
    },
]


def seed_templates(apps, schema_editor):
    ServiceTemplate = apps.get_model("catalog", "ServiceTemplate")
    for t in CERTIFIED_TEMPLATES:
        ServiceTemplate.objects.get_or_create(
            name=t["name"],
            workspace=None,
            defaults={k: v for k, v in t.items() if k != "name"},
        )


class Migration(migrations.Migration):
    dependencies = [("catalog", "0001_initial")]
    operations = [migrations.RunPython(seed_templates, migrations.RunPython.noop)]
```

---

## Vues API

```python
# apps/catalog/views.py
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import ServiceTemplate, EndorsementStatus
from .serializers import ServiceTemplateSerializer
from apps.workspaces.permissions import IsWorkspaceAdmin


class ServiceTemplateViewSet(viewsets.ModelViewSet):
    serializer_class = ServiceTemplateSerializer

    def get_queryset(self):
        # Templates globaux (workspace=null) + templates du workspace courant
        from django.db.models import Q
        return ServiceTemplate.objects.filter(
            Q(workspace__isnull=True) | Q(workspace=self.request.workspace)
        ).order_by("-endorsement", "name")

    @action(detail=True, methods=["post"], permission_classes=[IsWorkspaceAdmin])
    def endorse(self, request, pk=None):
        template = self.get_object()
        level = request.data.get("level")
        if level not in [EndorsementStatus.PROMOTED, EndorsementStatus.CERTIFIED]:
            return Response(
                {"error": "level must be 'promoted' or 'certified'"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # Certified nécessite OrganizationOwner
        if level == EndorsementStatus.CERTIFIED and not request.user.is_superuser:
            return Response(status=status.HTTP_403_FORBIDDEN)

        template.endorsement = level
        template.endorsed_by = request.user
        template.endorsed_at = timezone.now()
        template.save(update_fields=["endorsement", "endorsed_by", "endorsed_at"])
        return Response(ServiceTemplateSerializer(template).data)

    @action(detail=True, methods=["post"])
    def create_service(self, request, pk=None):
        """Créer un Service depuis ce template dans un Environment donné."""
        template = self.get_object()
        from apps.services.models import Service
        from apps.environments.models import Environment

        env_id = request.data.get("environment_id")
        name = request.data.get("name")

        try:
            env = Environment.objects.get(
                pk=env_id, project__workspace=request.workspace
            )
        except Environment.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        config = template.template_config
        service = Service.objects.create(
            environment=env,
            template=template,
            name=name,
            slug=name.lower().replace(" ", "-"),
            service_type=config.get("service_type", "web"),
            runtime=config.get("runtime", "dockerfile"),
            internal_port=config.get("internal_port", 8000),
        )
        return Response({"service_id": service.id}, status=status.HTTP_201_CREATED)
```

---

## Sérializer

```python
# apps/catalog/serializers.py
from rest_framework import serializers
from .models import ServiceTemplate


class ServiceTemplateSerializer(serializers.ModelSerializer):
    endorsed_by_email = serializers.SerializerMethodField()
    is_global = serializers.SerializerMethodField()

    class Meta:
        model = ServiceTemplate
        fields = [
            "id", "name", "description", "endorsement", "version",
            "template_config", "is_global",
            "endorsed_by_email", "endorsed_at",
            "created_at",
        ]
        read_only_fields = ["endorsed_by_email", "endorsed_at", "is_global"]

    def get_endorsed_by_email(self, obj):
        return obj.endorsed_by.email if obj.endorsed_by else None

    def get_is_global(self, obj):
        return obj.workspace is None
```
