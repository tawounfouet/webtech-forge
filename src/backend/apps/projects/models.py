from django.db import models


class Project(models.Model):
    workspace = models.ForeignKey(
        "workspaces.Workspace",
        related_name="projects",
        on_delete=models.CASCADE,
    )
    name = models.CharField(max_length=255)
    slug = models.SlugField()
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("workspace", "slug")

    def __str__(self) -> str:
        return f"{self.workspace}/{self.slug}"


class ProjectRepository(models.Model):
    project = models.ForeignKey(Project, related_name="repositories", on_delete=models.CASCADE)
    name = models.CharField(max_length=128)
    repo_url = models.URLField()
    default_branch = models.CharField(max_length=128, default="main")
    is_primary = models.BooleanField(default=False)
    webhook_secret = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.project}/{self.name}"
