from django.conf import settings
from django.db import models


class ServiceTemplate(models.Model):
    class EndorsementLevel(models.TextChoices):
        EXPERIMENTAL = "experimental", "Experimental"
        PROMOTED = "promoted", "Promoted"
        CERTIFIED = "certified", "Certified"

    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=128, blank=True)
    endorsement = models.CharField(
        max_length=32,
        choices=EndorsementLevel.choices,
        default=EndorsementLevel.EXPERIMENTAL,
    )
    service_type = models.CharField(max_length=32, blank=True)
    runtime = models.CharField(max_length=32, blank=True)
    default_port = models.PositiveIntegerField(null=True, blank=True)
    compose_template = models.TextField(blank=True)
    forge_yaml_template = models.TextField(blank=True)
    default_env_vars = models.JSONField(default=dict)
    endorsed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )
    endorsed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"{self.name} [{self.endorsement}]"
