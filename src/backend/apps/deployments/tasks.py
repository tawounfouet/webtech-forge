from celery import shared_task


@shared_task(
    name="apps.deployments.tasks.run_deployment",
    bind=True,
    max_retries=0,
    queue="deployments",
)
def run_deployment(self, deployment_id: int) -> dict:
    """
    Orchestrate the Medallion deployment pipeline: Bronze → Silver → Gold.
    Implemented in 07-deployment-engine.md.
    """
    raise NotImplementedError("TODO: implement run_deployment — see 07-deployment-engine.md")


@shared_task(name="apps.deployments.tasks.backup_postgres", queue="backups")
def backup_postgres() -> dict:
    """Backup PostgreSQL vers S3 — implémenté dans 20-backups-restore.md."""
    raise NotImplementedError("TODO: implement backup_postgres task")


@shared_task(name="apps.deployments.tasks.registry_cleanup", queue="backups")
def registry_cleanup() -> dict:
    """Nettoyage hebdomadaire des images orphelines du registry local."""
    raise NotImplementedError("TODO: implement registry_cleanup task")
