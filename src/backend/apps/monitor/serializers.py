from rest_framework import serializers

from .models import MonitorSnapshot


class MonitorSnapshotSerializer(serializers.ModelSerializer):
    class Meta:
        model = MonitorSnapshot
        fields = [
            "id",
            "total_services",
            "running_services",
            "failed_services",
            "total_deployments_last_24h",
            "failed_deployments_last_24h",
            "cpu_usage_percent",
            "memory_usage_percent",
            "captured_at",
        ]
        read_only_fields = fields
