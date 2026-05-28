from django.db import models


class Environment(models.Model):
    class Kind(models.TextChoices):
        DEVELOPMENT = "development", "Development"
        STAGING = "staging", "Staging"
        PREVIEW = "preview", "Preview"
        PRODUCTION = "production", "Production"

    project = models.ForeignKey(
        "projects.Project",
        related_name="environments",
        on_delete=models.CASCADE,
    )
    name = models.CharField(max_length=128)
    slug = models.SlugField()
    kind = models.CharField(max_length=32, choices=Kind.choices)
    protected = models.BooleanField(default=False)
    auto_deploy_branch = models.CharField(max_length=128, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("project", "slug")

    def __str__(self) -> str:
        return f"{self.project}/{self.slug} [{self.kind}]"


class PromotionPolicy(models.Model):
    environment = models.OneToOneField(
        Environment, related_name="promotion_policy", on_delete=models.CASCADE
    )
    require_approval = models.BooleanField(default=False)
    min_approvers = models.PositiveIntegerField(default=1)
    auto_promote_from = models.ForeignKey(
        Environment,
        null=True,
        blank=True,
        related_name="auto_promotes_to",
        on_delete=models.SET_NULL,
    )
    notify_channels = models.JSONField(default=list)

    def __str__(self) -> str:
        return f"PromotionPolicy({self.environment})"
