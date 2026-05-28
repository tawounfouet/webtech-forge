import django.db.models.deletion
import encrypted_model_fields.fields
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("organizations", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Workspace",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("name", models.CharField(max_length=255)),
                ("slug", models.SlugField()),
                ("description", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="workspaces",
                        to="organizations.organization",
                    ),
                ),
            ],
            options={
                "unique_together": {("organization", "slug")},
            },
        ),
        migrations.CreateModel(
            name="WorkspaceMember",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                (
                    "role",
                    models.CharField(
                        choices=[
                            ("admin", "Admin"),
                            ("maintainer", "Maintainer"),
                            ("operator", "Operator"),
                            ("developer", "Developer"),
                            ("viewer", "Viewer"),
                            ("auditor", "Auditor"),
                        ],
                        max_length=32,
                    ),
                ),
                ("added_at", models.DateTimeField(auto_now_add=True)),
                (
                    "added_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "workspace",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="members",
                        to="workspaces.workspace",
                    ),
                ),
            ],
            options={
                "unique_together": {("workspace", "user")},
            },
        ),
        migrations.CreateModel(
            name="WorkspaceSecret",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("key", models.CharField(max_length=255)),
                ("value", encrypted_model_fields.fields.EncryptedTextField()),
                ("description", models.CharField(blank=True, max_length=255)),
                ("last_rotated_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "workspace",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="secrets",
                        to="workspaces.workspace",
                    ),
                ),
            ],
            options={
                "unique_together": {("workspace", "key")},
            },
        ),
        migrations.CreateModel(
            name="WorkspaceQuota",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("max_services", models.PositiveIntegerField(default=20)),
                ("max_cpu_cores", models.PositiveIntegerField(default=8)),
                ("max_memory_gb", models.FloatField(default=16.0)),
                ("max_storage_gb", models.FloatField(default=50.0)),
                ("max_deployments_kept", models.PositiveIntegerField(default=10)),
                ("max_preview_environments", models.PositiveIntegerField(default=5)),
                ("log_retention_days", models.PositiveIntegerField(default=30)),
                ("backup_window_days", models.PositiveIntegerField(default=30)),
                (
                    "workspace",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="quota",
                        to="workspaces.workspace",
                    ),
                ),
            ],
        ),
    ]
