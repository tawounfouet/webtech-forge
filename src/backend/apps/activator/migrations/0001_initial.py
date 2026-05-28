import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("services", "0002_service_active_deployment"),
        ("workspaces", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="ActivatorRule",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("name", models.CharField(max_length=255)),
                (
                    "metric",
                    models.CharField(
                        choices=[
                            ("cpu_percent", "CPU %"),
                            ("memory_percent", "Memory %"),
                            ("http_5xx_rate", "HTTP 5xx rate"),
                            ("deployment_failure_rate", "Deployment failure rate"),
                            ("healthcheck_failures", "Healthcheck failures"),
                        ],
                        max_length=64,
                    ),
                ),
                (
                    "operator",
                    models.CharField(
                        choices=[
                            ("gt", ">"),
                            ("gte", ">="),
                            ("lt", "<"),
                            ("lte", "<="),
                            ("eq", "=="),
                        ],
                        max_length=8,
                    ),
                ),
                ("threshold", models.FloatField()),
                (
                    "action",
                    models.CharField(
                        choices=[
                            ("rollback", "Rollback"),
                            ("scale_up", "Scale up"),
                            ("scale_down", "Scale down"),
                            ("alert", "Alert only"),
                            ("disable_service", "Disable service"),
                        ],
                        max_length=32,
                    ),
                ),
                ("cooldown_seconds", models.PositiveIntegerField(default=300)),
                ("is_active", models.BooleanField(default=True)),
                ("circuit_open", models.BooleanField(default=False)),
                ("circuit_opened_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "service",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="activator_rules",
                        to="services.service",
                    ),
                ),
                (
                    "workspace",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="activator_rules",
                        to="workspaces.workspace",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="ActivatorExecution",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("measured_value", models.FloatField()),
                (
                    "result",
                    models.CharField(
                        choices=[
                            ("triggered", "Triggered"),
                            ("skipped_cooldown", "Skipped (cooldown)"),
                            ("skipped_circuit", "Skipped (circuit open)"),
                            ("failed", "Failed"),
                        ],
                        max_length=32,
                    ),
                ),
                ("action_taken", models.CharField(blank=True, max_length=64)),
                ("error_message", models.TextField(blank=True)),
                ("executed_at", models.DateTimeField(auto_now_add=True)),
                (
                    "rule",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="executions",
                        to="activator.activatorrule",
                    ),
                ),
            ],
            options={
                "ordering": ["-executed_at"],
            },
        ),
    ]
