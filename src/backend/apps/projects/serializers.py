from rest_framework import serializers

from .models import Project, ProjectRepository


class ProjectRepositorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectRepository
        fields = ["id", "name", "repo_url", "default_branch", "is_primary", "created_at"]
        read_only_fields = ["id", "created_at"]
        extra_kwargs = {"webhook_secret": {"write_only": True}}


class ProjectSerializer(serializers.ModelSerializer):
    workspace_slug = serializers.SlugField(source="workspace.slug", read_only=True)

    class Meta:
        model = Project
        fields = ["id", "workspace", "workspace_slug", "name", "slug", "description", "created_at"]
        read_only_fields = ["id", "created_at", "workspace_slug", "workspace"]


class ProjectDetailSerializer(ProjectSerializer):
    repositories = ProjectRepositorySerializer(many=True, read_only=True)

    class Meta(ProjectSerializer.Meta):
        fields = ProjectSerializer.Meta.fields + ["repositories"]
