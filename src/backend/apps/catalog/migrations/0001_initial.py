import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ServiceTemplate",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("name", models.CharField(max_length=255)),
                ("slug", models.SlugField(unique=True)),
                ("description", models.TextField(blank=True)),
                ("icon", models.CharField(blank=True, max_length=128)),
                (
                    "endorsement",
                    models.CharField(
                        choices=[
                            ("experimental", "Experimental"),
                            ("promoted", "Promoted"),
                            ("certified", "Certified"),
                        ],
                        default="experimental",
                        max_length=32,
                    ),
                ),
                ("service_type", models.CharField(blank=True, max_length=32)),
                ("runtime", models.CharField(blank=True, max_length=32)),
                ("default_port", models.PositiveIntegerField(blank=True, null=True)),
                ("compose_template", models.TextField(blank=True)),
                ("forge_yaml_template", models.TextField(blank=True)),
                ("default_env_vars", models.JSONField(default=dict)),
                ("endorsed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "endorsed_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
    ]
