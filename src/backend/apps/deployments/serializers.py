from rest_framework import serializers

from .models import Deployment, DeploymentEvent, RollbackRecord


class DeploymentEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeploymentEvent
        fields = ["id", "phase", "message", "level", "emitted_at"]


class RollbackRecordSerializer(serializers.ModelSerializer):
    triggered_by_email = serializers.EmailField(source="triggered_by.email", read_only=True)

    class Meta:
        model = RollbackRecord
        fields = [
            "id", "deployment", "rolled_back_to",
            "triggered_by", "triggered_by_email", "trigger_source", "created_at",
        ]


class DeploymentListSerializer(serializers.ModelSerializer):
    triggered_by_email = serializers.EmailField(source="triggered_by.email", read_only=True)
    service_slug = serializers.SlugField(source="service.slug", read_only=True)
    duration_seconds = serializers.SerializerMethodField()

    class Meta:
        model = Deployment
        fields = [
            "id", "service", "service_slug",
            "phase", "status",
            "commit_sha", "image_ref", "image_digest",
            "trigger_source", "triggered_by", "triggered_by_email",
            "failure_reason",
            "created_at", "started_at", "finished_at", "duration_seconds",
        ]

    def get_duration_seconds(self, obj) -> float | None:
        if obj.started_at and obj.finished_at:
            return (obj.finished_at - obj.started_at).total_seconds()
        return None


class DeploymentDetailSerializer(DeploymentListSerializer):
    events = DeploymentEventSerializer(many=True, read_only=True)
    rollbacks = RollbackRecordSerializer(many=True, read_only=True)

    class Meta(DeploymentListSerializer.Meta):
        fields = DeploymentListSerializer.Meta.fields + ["events", "rollbacks"]
