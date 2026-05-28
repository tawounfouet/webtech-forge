import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("workspaces", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="MonitorSnapshot",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("total_services", models.PositiveIntegerField(default=0)),
                ("running_services", models.PositiveIntegerField(default=0)),
                ("failed_services", models.PositiveIntegerField(default=0)),
                ("total_deployments_last_24h", models.PositiveIntegerField(default=0)),
                ("failed_deployments_last_24h", models.PositiveIntegerField(default=0)),
                ("cpu_usage_percent", models.FloatField(blank=True, null=True)),
                ("memory_usage_percent", models.FloatField(blank=True, null=True)),
                ("captured_at", models.DateTimeField(auto_now_add=True)),
                (
                    "workspace",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="monitor_snapshots",
                        to="workspaces.workspace",
                    ),
                ),
            ],
            options={
                "ordering": ["-captured_at"],
                "indexes": [
                    models.Index(
                        fields=["workspace", "captured_at"],
                        name="monitor_workspace_captured_idx",
                    )
                ],
            },
        ),
    ]
