from rest_framework import serializers

from .models import Environment, PromotionPolicy


class PromotionPolicySerializer(serializers.ModelSerializer):
    class Meta:
        model = PromotionPolicy
        fields = [
            "require_approval", "min_approvers",
            "auto_promote_from", "notify_channels",
        ]


class EnvironmentSerializer(serializers.ModelSerializer):
    project_slug = serializers.SlugField(source="project.slug", read_only=True)

    class Meta:
        model = Environment
        fields = [
            "id", "project", "project_slug",
            "name", "slug", "kind", "protected", "auto_deploy_branch", "created_at",
        ]
        read_only_fields = ["id", "created_at", "project_slug"]


class EnvironmentDetailSerializer(EnvironmentSerializer):
    promotion_policy = PromotionPolicySerializer(read_only=True)

    class Meta(EnvironmentSerializer.Meta):
        fields = EnvironmentSerializer.Meta.fields + ["promotion_policy"]
