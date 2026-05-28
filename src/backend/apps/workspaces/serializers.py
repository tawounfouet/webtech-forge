from rest_framework import serializers

from .models import Workspace, WorkspaceMember, WorkspaceQuota, WorkspaceSecret


class WorkspaceMemberSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = WorkspaceMember
        fields = ["id", "user", "user_email", "role", "added_at", "added_by"]
        read_only_fields = ["id", "added_at", "added_by"]


class WorkspaceSecretSerializer(serializers.ModelSerializer):
    value = serializers.CharField(write_only=True)

    class Meta:
        model = WorkspaceSecret
        fields = ["id", "key", "value", "description", "last_rotated_at", "created_at"]
        read_only_fields = ["id", "last_rotated_at", "created_at"]


class WorkspaceQuotaSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkspaceQuota
        fields = [
            "max_services", "max_cpu_cores", "max_memory_gb", "max_storage_gb",
            "max_deployments_kept", "max_preview_environments",
            "log_retention_days", "backup_window_days",
        ]


class WorkspaceSerializer(serializers.ModelSerializer):
    organization_slug = serializers.SlugField(source="organization.slug", read_only=True)
    my_role = serializers.SerializerMethodField()

    class Meta:
        model = Workspace
        fields = [
            "id", "organization", "organization_slug",
            "name", "slug", "description", "created_at", "my_role",
        ]
        read_only_fields = ["id", "created_at", "organization_slug", "my_role"]

    def get_my_role(self, obj) -> str | None:
        request = self.context.get("request")
        if request and getattr(request, "workspace", None) == obj:
            return getattr(request, "workspace_role", None)
        return None
