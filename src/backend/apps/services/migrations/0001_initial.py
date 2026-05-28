"""
Migration 0001 : crée Service sans active_deployment (évite la dépendance circulaire
avec deployments). Le FK active_deployment est ajouté dans 0002 après que
deployments/0001 soit appliqué.
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("catalog", "0001_initial"),
        ("environments", "0001_initial"),
        ("workspaces", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Service",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("name", models.CharField(max_length=255)),
                ("slug", models.SlugField()),
                (
                    "service_type",
                    models.CharField(
                        choices=[
                            ("web", "Web"),
                            ("api", "API"),
                            ("worker", "Worker"),
                            ("cron", "Cron"),
                            ("database", "Database"),
                            ("cache", "Cache"),
                            ("storage", "Storage"),
                        ],
                        max_length=32,
                    ),
                ),
                (
                    "runtime",
                    models.CharField(
                        choices=[
                            ("dockerfile", "Dockerfile"),
                            ("compose", "Compose"),
                            ("image", "Image"),
                        ],
                        max_length=32,
                    ),
                ),
                ("image", models.CharField(blank=True, max_length=512)),
                ("dockerfile_path", models.CharField(default="Dockerfile", max_length=255)),
                ("compose_file_path", models.CharField(blank=True, max_length=255)),
                ("build_context", models.CharField(default=".", max_length=255)),
                ("internal_port", models.PositiveIntegerField(default=8000)),
                ("replicas", models.PositiveIntegerField(default=1)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "environment",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="services",
                        to="environments.environment",
                    ),
                ),
                (
                    "template",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to="catalog.servicetemplate",
                    ),
                ),
            ],
            options={
                "unique_together": {("environment", "slug")},
            },
        ),
        migrations.CreateModel(
            name="ServiceEnvVar",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("key", models.CharField(max_length=255)),
                ("value", models.TextField(blank=True)),
                ("is_secret", models.BooleanField(default=False)),
                (
                    "secret_ref",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to="workspaces.workspacesecret",
                    ),
                ),
                (
                    "service",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="env_vars",
                        to="services.service",
                    ),
                ),
            ],
            options={
                "unique_together": {("service", "key")},
            },
        ),
        migrations.CreateModel(
            name="Domain",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("hostname", models.CharField(max_length=255)),
                ("is_custom", models.BooleanField(default=False)),
                ("tls_enabled", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "service",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="domains",
                        to="services.service",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="Volume",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("name", models.CharField(max_length=255)),
                ("mount_path", models.CharField(max_length=512)),
                ("size_gb", models.FloatField(default=1.0)),
                (
                    "service",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="volumes",
                        to="services.service",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="Healthcheck",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                (
                    "protocol",
                    models.CharField(
                        choices=[
                            ("http", "HTTP"),
                            ("tcp", "TCP"),
                            ("command", "Command"),
                        ],
                        default="http",
                        max_length=16,
                    ),
                ),
                ("path", models.CharField(default="/health", max_length=255)),
                ("interval_seconds", models.PositiveIntegerField(default=30)),
                ("timeout_seconds", models.PositiveIntegerField(default=5)),
                ("retries", models.PositiveIntegerField(default=3)),
                (
                    "service",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="healthcheck",
                        to="services.service",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="ServiceBinding",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                (
                    "binding_type",
                    models.CharField(
                        choices=[
                            ("local", "Local"),
                            ("cross_env", "Cross-Environment"),
                            ("shortcut", "ForgeStore Shortcut (V3)"),
                        ],
                        max_length=32,
                    ),
                ),
                ("env_prefix", models.CharField(blank=True, max_length=64)),
                (
                    "allowed_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "source_service",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="bindings",
                        to="services.service",
                    ),
                ),
                (
                    "target_service",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="bound_by",
                        to="services.service",
                    ),
                ),
            ],
        ),
    ]
