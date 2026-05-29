from rest_framework import serializers

from .models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = AuditLog
        fields = [
            "id",
            "user_email",
            "action",
            "resource_type",
            "resource_id",
            "http_status",
            "ip_address",
            "metadata",
            "created_at",
        ]
        read_only_fields = fields
