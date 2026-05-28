from rest_framework import serializers

from .models import ServiceTemplate


class ServiceTemplateSerializer(serializers.ModelSerializer):
    endorsed_by_email = serializers.EmailField(source="endorsed_by.email", read_only=True)

    class Meta:
        model = ServiceTemplate
        fields = [
            "id", "name", "slug", "description", "icon",
            "endorsement", "service_type", "runtime", "default_port",
            "default_env_vars",
            "endorsed_by", "endorsed_by_email", "endorsed_at",
            "created_at",
        ]
        read_only_fields = ["id", "created_at", "endorsed_at", "endorsed_by", "endorsed_by_email"]


class ServiceTemplateDetailSerializer(ServiceTemplateSerializer):
    class Meta(ServiceTemplateSerializer.Meta):
        fields = ServiceTemplateSerializer.Meta.fields + [
            "compose_template", "forge_yaml_template",
        ]
