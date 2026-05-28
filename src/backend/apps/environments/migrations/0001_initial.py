import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("projects", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Environment",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("name", models.CharField(max_length=128)),
                ("slug", models.SlugField()),
                (
                    "kind",
                    models.CharField(
                        choices=[
                            ("development", "Development"),
                            ("staging", "Staging"),
                            ("preview", "Preview"),
                            ("production", "Production"),
                        ],
                        max_length=32,
                    ),
                ),
                ("protected", models.BooleanField(default=False)),
                ("auto_deploy_branch", models.CharField(blank=True, max_length=128)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "project",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="environments",
                        to="projects.project",
                    ),
                ),
            ],
            options={
                "unique_together": {("project", "slug")},
            },
        ),
        migrations.CreateModel(
            name="PromotionPolicy",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("require_approval", models.BooleanField(default=False)),
                ("min_approvers", models.PositiveIntegerField(default=1)),
                ("notify_channels", models.JSONField(default=list)),
                (
                    "auto_promote_from",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="auto_promotes_to",
                        to="environments.environment",
                    ),
                ),
                (
                    "environment",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="promotion_policy",
                        to="environments.environment",
                    ),
                ),
            ],
        ),
    ]
