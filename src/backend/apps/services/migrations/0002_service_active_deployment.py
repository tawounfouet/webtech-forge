"""
Résolution de la dépendance circulaire Services ↔ Deployments.
services/0001 crée Service sans active_deployment.
deployments/0001 crée Deployment avec FK vers services.Service.
Cette migration 0002 ajoute le FK active_deployment vers deployments.Deployment.
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("services", "0001_initial"),
        ("deployments", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="service",
            name="active_deployment",
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="locking_service",
                to="deployments.deployment",
            ),
        ),
    ]
