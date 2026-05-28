from rest_framework import serializers

from .models import Domain, Healthcheck, Service, ServiceBinding, ServiceEnvVar, Volume


class ServiceEnvVarSerializer(serializers.ModelSerializer):
    value = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = ServiceEnvVar
        fields = ["id", "key", "value", "is_secret", "secret_ref"]
        read_only_fields = ["id"]


class DomainSerializer(serializers.ModelSerializer):
    class Meta:
        model = Domain
        fields = ["id", "hostname", "is_custom", "tls_enabled", "created_at"]
        read_only_fields = ["id", "created_at"]


class VolumeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Volume
        fields = ["id", "name", "mount_path", "size_gb"]
        read_only_fields = ["id"]


class HealthcheckSerializer(serializers.ModelSerializer):
    class Meta:
        model = Healthcheck
        fields = ["protocol", "path", "interval_seconds", "timeout_seconds", "retries"]


class ServiceBindingSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceBinding
        fields = ["id", "source_service", "target_service", "binding_type", "env_prefix", "allowed_by"]
        read_only_fields = ["id", "allowed_by"]


class ServiceSerializer(serializers.ModelSerializer):
    environment_slug = serializers.SlugField(source="environment.slug", read_only=True)
    active_deployment_id = serializers.PrimaryKeyRelatedField(
        source="active_deployment", read_only=True
    )

    class Meta:
        model = Service
        fields = [
            "id", "environment", "environment_slug", "template",
            "name", "slug", "service_type", "runtime",
            "image", "dockerfile_path", "compose_file_path", "build_context",
            "internal_port", "replicas",
            "active_deployment_id", "created_at",
        ]
        read_only_fields = ["id", "created_at", "environment_slug", "active_deployment_id"]


class ServiceDetailSerializer(ServiceSerializer):
    env_vars = ServiceEnvVarSerializer(many=True, read_only=True)
    domains = DomainSerializer(many=True, read_only=True)
    volumes = VolumeSerializer(many=True, read_only=True)
    healthcheck = HealthcheckSerializer(read_only=True)

    class Meta(ServiceSerializer.Meta):
        fields = ServiceSerializer.Meta.fields + [
            "env_vars", "domains", "volumes", "healthcheck",
        ]


class ServiceCreateSerializer(ServiceSerializer):
    """Write serializer — environment is set from the request context, not the payload."""

    class Meta(ServiceSerializer.Meta):
        read_only_fields = ["id", "created_at", "active_deployment_id"]
