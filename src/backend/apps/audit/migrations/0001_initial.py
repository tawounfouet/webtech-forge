import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("workspaces", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AuditLog",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("action", models.CharField(max_length=512)),
                ("resource_type", models.CharField(blank=True, max_length=64)),
                ("resource_id", models.CharField(blank=True, max_length=64)),
                ("http_status", models.PositiveSmallIntegerField(null=True)),
                ("ip_address", models.GenericIPAddressField(null=True)),
                ("metadata", models.JSONField(default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "user",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="audit_logs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "workspace",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="audit_logs",
                        to="workspaces.workspace",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(
                        fields=["workspace", "created_at"],
                        name="audit_workspace_created_idx",
                    ),
                    models.Index(
                        fields=["user", "created_at"],
                        name="audit_user_created_idx",
                    ),
                    models.Index(
                        fields=["resource_type", "resource_id"],
                        name="audit_resource_idx",
                    ),
                ],
            },
        ),
    ]
