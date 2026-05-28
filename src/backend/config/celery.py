import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")

app = Celery("forge")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

app.conf.task_routes = {
    "apps.deployments.tasks.*": {"queue": "deployments"},
    "apps.activator.tasks.*": {"queue": "activator"},
    "apps.deployments.tasks.backup_postgres": {"queue": "backups"},
    "apps.deployments.tasks.registry_cleanup": {"queue": "backups"},
}
