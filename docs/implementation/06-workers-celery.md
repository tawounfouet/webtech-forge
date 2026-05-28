# 06 — Workers Celery

> **ADR de référence :** ADR-004
> **Dépendances :** 03-backend-django.md, 04-modeles-donnees.md

---

## Queues et workers

| Queue | Worker | Concurrence | Responsabilités |
|---|---|---|---|
| `default` | `forge-worker` | 4 | Tâches générales, notifications |
| `deployments` | `forge-worker` | 2 | Pipeline Medallion, rollbacks |
| `backups` | `forge-worker` | 1 | Backups PostgreSQL, volumes, Registry cleanup |
| `activator` | `forge-activator` | 2 | Évaluation règles Activator, exécution actions |

**Lancer les workers :**

```bash
# Worker principal (queues default + deployments + backups)
celery -A config.celery worker -l info \
  -Q default,deployments,backups \
  --concurrency 4 \
  --hostname forge-worker@%h

# Worker Activator (queue dédiée)
celery -A config.celery worker -l info \
  -Q activator \
  --concurrency 2 \
  --hostname forge-activator@%h

# Beat scheduler
celery -A config.celery beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
```

---

## Service métier DeploymentService

La logique de création de déploiement est encapsulée dans un service métier — pas dans les tâches Celery ni dans les vues DRF.

```python
# apps/deployments/services.py
from django.utils import timezone
from .models import Deployment, RollbackRecord
from .tasks import run_deployment_pipeline


class DeploymentService:
    @staticmethod
    def create_deployment(service, triggered_by, trigger_source="manual") -> Deployment:
        deployment = Deployment.objects.create(
            service=service,
            triggered_by=triggered_by,
            trigger_source=trigger_source,
            status=Deployment.Status.PENDING,
            phase=Deployment.Phase.BRONZE,
        )
        service.acquire_deploy_lock(deployment)
        run_deployment_pipeline.apply_async(
            args=[deployment.id],
            queue="deployments",
        )
        return deployment

    @staticmethod
    def rollback(deployment, triggered_by) -> Deployment:
        last_success = Deployment.objects.filter(
            service=deployment.service,
            status=Deployment.Status.SUCCESS,
        ).exclude(pk=deployment.pk).order_by("-finished_at").first()

        if not last_success:
            raise ValueError("No successful deployment to rollback to")

        new_deployment = Deployment.objects.create(
            service=deployment.service,
            triggered_by=triggered_by,
            trigger_source="manual",
            image_ref=last_success.image_ref,
            commit_sha=last_success.commit_sha,
            status=Deployment.Status.PENDING,
            phase=Deployment.Phase.GOLD,  # skip Bronze et Silver — image déjà buildée
        )
        RollbackRecord.objects.create(
            deployment=deployment,
            rolled_back_to=last_success,
            triggered_by=triggered_by,
        )
        run_deployment_pipeline.apply_async(
            args=[new_deployment.id],
            queue="deployments",
        )
        return new_deployment

    @staticmethod
    def trigger_auto_deploy(repo, branch):
        from apps.environments.models import Environment
        for env in Environment.objects.filter(
            project__repositories=repo,
            auto_deploy_branch=branch,
        ):
            for service in env.services.filter(runtime__in=["dockerfile", "compose"]):
                DeploymentService.create_deployment(
                    service=service,
                    triggered_by=None,
                    trigger_source="webhook",
                )
```

---

## Tâche principale — Pipeline Medallion

```python
# apps/deployments/tasks.py
from celery import shared_task
from django.utils import timezone
from .models import Deployment, DeploymentEvent


def _emit(deployment, phase, message, level="info"):
    DeploymentEvent.objects.create(
        deployment=deployment,
        phase=phase,
        message=message,
        level=level,
    )
    # Diffuse en temps réel via Channels
    from channels.layers import get_channel_layer
    from asgiref.sync import async_to_sync
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"deployment_{deployment.id}",
        {"type": "log.message", "message": message, "level": level, "phase": phase},
    )


def _update(deployment, status, phase=None):
    update_fields = {"status": status}
    if phase:
        update_fields["phase"] = phase
    if status in (Deployment.Status.BUILDING, Deployment.Status.CLONING):
        update_fields["started_at"] = timezone.now()
    if status in (Deployment.Status.SUCCESS, Deployment.Status.FAILED, Deployment.Status.ROLLED_BACK):
        update_fields["finished_at"] = timezone.now()
    Deployment.objects.filter(pk=deployment.pk).update(**update_fields)
    deployment.refresh_from_db()


@shared_task(bind=True, max_retries=3, default_retry_delay=30, queue="deployments")
def run_deployment_pipeline(self, deployment_id: int):
    from adapters.docker_adapter import DockerAdapter
    from adapters.git_adapter import GitAdapter
    from adapters.registry_adapter import RegistryAdapter
    from adapters.traefik_adapter import TraefikAdapter

    deployment = Deployment.objects.select_related(
        "service__environment__project__workspace",
        "service__active_deployment",
    ).get(pk=deployment_id)

    service = deployment.service
    workspace = service.environment.project.workspace

    try:
        # ── BRONZE — Artefact ──────────────────────────────────────────
        _update(deployment, Deployment.Status.CLONING, Deployment.Phase.BRONZE)
        _emit(deployment, "bronze", "Cloning repository...")

        git = GitAdapter()
        repo_path, commit_sha = git.clone_and_checkout(service)
        Deployment.objects.filter(pk=deployment.pk).update(commit_sha=commit_sha)
        _emit(deployment, "bronze", f"Cloned at commit {commit_sha[:8]}")

        # ── SILVER — Validation + Build ───────────────────────────────
        _update(deployment, Deployment.Status.VALIDATING, Deployment.Phase.SILVER)
        _emit(deployment, "silver", "Validating forge.yaml and Dockerfile...")

        git.validate_build_config(repo_path, service)
        env_vars = _resolve_env_vars(service)

        _update(deployment, Deployment.Status.BUILDING)
        _emit(deployment, "silver", "Building image...")

        registry = RegistryAdapter()
        image_ref = registry.build_and_push(
            workspace_slug=workspace.slug,
            service_slug=service.slug,
            commit_sha=commit_sha,
            context_path=repo_path,
            dockerfile_path=service.dockerfile_path,
        )
        Deployment.objects.filter(pk=deployment.pk).update(image_ref=image_ref)
        _emit(deployment, "silver", f"Image pushed: {image_ref}")

        _update(deployment, Deployment.Status.RELEASING)
        labels = TraefikAdapter.generate_labels(service, deployment)

        # ── GOLD — Live ────────────────────────────────────────────────
        _update(deployment, Deployment.Status.HEALTHCHECKING, Deployment.Phase.GOLD)
        _emit(deployment, "gold", "Starting container (blue/green)...")

        docker = DockerAdapter()
        docker.ensure_workspace_network(workspace)
        new_container = docker.run_service(service, deployment, image_ref, env_vars, labels)

        _emit(deployment, "gold", "Running healthchecks...")
        healthy = docker.wait_for_healthy(new_container, service.healthcheck)

        if healthy:
            docker.switch_traefik_traffic(service, new_container)
            docker.stop_previous_container(service)
            _update(deployment, Deployment.Status.SUCCESS)
            service.active_deployment = None
            service.save(update_fields=["active_deployment"])
            _emit(deployment, "gold", "Deployment successful ✓")
        else:
            docker.stop_container(new_container)
            _do_rollback(deployment, service, docker)

    except Exception as exc:
        _emit(deployment, deployment.phase, f"Error: {exc}", level="error")
        Deployment.objects.filter(pk=deployment.pk).update(
            status=Deployment.Status.FAILED,
            failure_reason=str(exc),
            finished_at=timezone.now(),
        )
        # Release lock
        service.__class__.objects.filter(pk=service.pk).update(active_deployment=None)
        raise


def _do_rollback(deployment, service, docker):
    _update(deployment, Deployment.Status.ROLLED_BACK)
    _emit(deployment, "gold", "Healthcheck failed — rolling back to previous deployment", level="warn")
    previous = Deployment.objects.filter(
        service=service, status=Deployment.Status.SUCCESS
    ).exclude(pk=deployment.pk).order_by("-finished_at").first()
    if previous and previous.image_ref:
        docker.restore_previous_container(service, previous)
    service.__class__.objects.filter(pk=service.pk).update(active_deployment=None)


def _resolve_env_vars(service) -> dict:
    env = {}
    for ev in service.env_vars.select_related("secret_ref"):
        if ev.secret_ref:
            env[ev.key] = ev.secret_ref.value  # décrypté automatiquement
        else:
            env[ev.key] = ev.value
    return env
```

---

## Tâche de backup PostgreSQL

```python
@shared_task(queue="backups")
def backup_postgres():
    import subprocess
    import hashlib
    from pathlib import Path
    from adapters.storage_adapter import ObjectStorageAdapter
    from django.conf import settings
    from django.utils import timezone

    date_str = timezone.now().strftime("%Y-%m-%d")
    dump_path = Path(f"/tmp/forge-pg-{date_str}.sql.gz")

    result = subprocess.run([
        "pg_dump", settings.DATABASES["default"]["NAME"],
        "--no-password", "--clean", "--if-exists",
    ], capture_output=True)

    if result.returncode != 0:
        raise RuntimeError(f"pg_dump failed: {result.stderr.decode()}")

    with open(dump_path, "wb") as f:
        import gzip
        f.write(gzip.compress(result.stdout))

    checksum = hashlib.sha256(dump_path.read_bytes()).hexdigest()
    s3_key = f"backups/postgres/{date_str}/{checksum[:8]}.sql.gz"

    storage = ObjectStorageAdapter()
    storage.upload(dump_path, s3_key)
    storage.verify_upload(s3_key, checksum)
    storage.rotate_old(prefix="backups/postgres/", keep_days=30)
    dump_path.unlink()
```
