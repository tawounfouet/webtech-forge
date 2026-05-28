import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("services", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Deployment",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                (
                    "phase",
                    models.CharField(
                        choices=[
                            ("bronze", "Bronze"),
                            ("silver", "Silver"),
                            ("gold", "Gold"),
                        ],
                        default="bronze",
                        max_length=16,
                    ),
                ),
                ("commit_sha", models.CharField(blank=True, max_length=64)),
                ("image_ref", models.CharField(blank=True, max_length=512)),
                ("image_digest", models.CharField(blank=True, max_length=255)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("queued", "Queued"),
                            ("cloning", "Cloning"),
                            ("validating", "Validating"),
                            ("building", "Building"),
                            ("releasing", "Releasing"),
                            ("healthchecking", "Healthchecking"),
                            ("success", "Success"),
                            ("failed", "Failed"),
                            ("rolled_back", "Rolled Back"),
                        ],
                        default="pending",
                        max_length=32,
                    ),
                ),
                (
                    "trigger_source",
                    models.CharField(
                        choices=[
                            ("manual", "Manual"),
                            ("webhook", "Webhook"),
                            ("promotion", "Promotion"),
                            ("activator", "Activator"),
                        ],
                        default="manual",
                        max_length=32,
                    ),
                ),
                ("failure_reason", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                (
                    "service",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="deployments",
                        to="services.service",
                    ),
                ),
                (
                    "triggered_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "indexes": [
                    models.Index(fields=["service", "status"], name="deployments_service_status_idx"),
                    models.Index(
                        fields=["service", "phase", "status"],
                        name="deployments_service_phase_status_idx",
                    ),
                    models.Index(fields=["created_at"], name="deployments_created_at_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="DeploymentEvent",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("phase", models.CharField(max_length=16)),
                ("message", models.TextField()),
                (
                    "level",
                    models.CharField(
                        choices=[
                            ("debug", "Debug"),
                            ("info", "Info"),
                            ("warning", "Warning"),
                            ("error", "Error"),
                        ],
                        default="info",
                        max_length=16,
                    ),
                ),
                ("emitted_at", models.DateTimeField(auto_now_add=True)),
                (
                    "deployment",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="events",
                        to="deployments.deployment",
                    ),
                ),
            ],
            options={
                "ordering": ["emitted_at"],
            },
        ),
        migrations.CreateModel(
            name="RollbackRecord",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                (
                    "trigger_source",
                    models.CharField(
                        choices=[
                            ("manual", "Manual"),
                            ("activator", "Activator (auto)"),
                            ("healthcheck", "Healthcheck failure"),
                        ],
                        default="manual",
                        max_length=32,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "deployment",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="rollbacks",
                        to="deployments.deployment",
                    ),
                ),
                (
                    "rolled_back_to",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="restored_by",
                        to="deployments.deployment",
                    ),
                ),
                (
                    "triggered_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
    ]
