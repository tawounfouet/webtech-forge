from __future__ import annotations

import gzip
import hashlib
import subprocess
import tempfile
from pathlib import Path

from asgiref.sync import async_to_sync
from celery import shared_task
from channels.layers import get_channel_layer
from django.utils import timezone


# ── Helpers ───────────────────────────────────────────────────────────────────

def _emit(deployment, phase: str, message: str, level: str = "info") -> None:
    """Persiste un DeploymentEvent ET le diffuse en temps réel via Channels."""
    from .models import DeploymentEvent

    DeploymentEvent.objects.create(
        deployment=deployment,
        phase=phase,
        message=message,
        level=level,
    )
    channel_layer = get_channel_layer()
    if channel_layer:
        async_to_sync(channel_layer.group_send)(
            f"deployment_{deployment.id}",
            {
                "type": "deployment.log",
                "data": {
                    "phase": phase,
                    "message": message,
                    "level": level,
                    "emitted_at": timezone.now().isoformat(),
                },
            },
        )


def _update(deployment, status: str, phase: str | None = None) -> None:
    """Met à jour le statut/phase et les timestamps en un seul UPDATE atomique."""
    from .models import Deployment

    fields: dict = {"status": status}
    if phase:
        fields["phase"] = phase
    if status in (Deployment.Status.CLONING, Deployment.Status.BUILDING):
        fields.setdefault("started_at", timezone.now())
    if status in (
        Deployment.Status.SUCCESS,
        Deployment.Status.FAILED,
        Deployment.Status.ROLLED_BACK,
    ):
        fields["finished_at"] = timezone.now()

    Deployment.objects.filter(pk=deployment.pk).update(**fields)
    deployment.refresh_from_db()


def _resolve_env_vars(service) -> dict[str, str]:
    """Résout les env vars du service — déchiffre les refs WorkspaceSecret."""
    env: dict[str, str] = {}
    for ev in service.env_vars.select_related("secret_ref"):
        env[ev.key] = ev.secret_ref.value if ev.secret_ref else ev.value
    return env


def _do_auto_rollback(deployment, service, docker) -> None:
    """Appelé quand le healthcheck échoue : tente de remonter le conteneur précédent."""
    from .models import Deployment

    _update(deployment, Deployment.Status.ROLLED_BACK)
    _emit(
        deployment,
        "gold",
        "Healthcheck failed — rolling back to previous deployment",
        level="warning",
    )
    previous = (
        Deployment.objects.filter(service=service, status=Deployment.Status.SUCCESS)
        .exclude(pk=deployment.pk)
        .order_by("-finished_at")
        .first()
    )
    if previous and previous.image_ref:
        try:
            docker.restore_previous_container(service, previous)
        except Exception as exc:
            _emit(deployment, "gold", f"Auto-rollback failed: {exc}", level="error")
    service.__class__.objects.filter(pk=service.pk).update(active_deployment=None)


# ── Pipeline principal ────────────────────────────────────────────────────────

@shared_task(
    max_retries=0,
    queue="deployments",
    name="apps.deployments.tasks.run_deployment_pipeline",
)
def run_deployment_pipeline(deployment_id: int) -> dict:
    """
    Pipeline Medallion Bronze → Silver → Gold.

    Bronze : clone Git, résolution du commit SHA
    Silver : validation forge.yaml + Dockerfile, build image, push registry
    Gold   : run container, healthcheck, switch Traefik (blue/green), cleanup
    """
    from .models import Deployment

    from adapters.docker_adapter import DockerAdapter
    from adapters.git_adapter import GitAdapter
    from adapters.registry_adapter import RegistryAdapter
    from adapters.traefik_adapter import TraefikAdapter

    deployment = Deployment.objects.select_related(
        "service__environment__project__workspace",
    ).get(pk=deployment_id)
    service = deployment.service
    workspace = service.environment.project.workspace

    try:
        # ── BRONZE — Artefact source ──────────────────────────────────────────
        _update(deployment, Deployment.Status.CLONING, Deployment.Phase.BRONZE)
        _emit(deployment, "bronze", "Cloning repository…")

        git = GitAdapter()
        repo_path, commit_sha = git.clone_and_checkout(service)
        Deployment.objects.filter(pk=deployment.pk).update(commit_sha=commit_sha)
        _emit(deployment, "bronze", f"Cloned at commit {commit_sha[:8]}")

        # ── SILVER — Build ────────────────────────────────────────────────────
        _update(deployment, Deployment.Status.VALIDATING, Deployment.Phase.SILVER)
        _emit(deployment, "silver", "Validating forge.yaml and Dockerfile…")
        git.validate_build_config(repo_path, service)

        env_vars = _resolve_env_vars(service)

        _update(deployment, Deployment.Status.BUILDING)
        _emit(deployment, "silver", "Building image…")

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

        # ── GOLD — Live ───────────────────────────────────────────────────────
        _update(deployment, Deployment.Status.HEALTHCHECKING, Deployment.Phase.GOLD)
        _emit(deployment, "gold", "Starting container (blue/green)…")

        docker = DockerAdapter()
        docker.ensure_workspace_network(workspace)
        healthcheck = getattr(service, "healthcheck", None)
        new_container = docker.run_service(service, deployment, image_ref, env_vars, labels)

        _emit(deployment, "gold", "Running healthchecks…")
        healthy = docker.wait_for_healthy(new_container, healthcheck)

        if healthy:
            docker.switch_traefik_traffic(service, new_container)
            docker.stop_previous_container(service)
            _update(deployment, Deployment.Status.SUCCESS)
            service.__class__.objects.filter(pk=service.pk).update(active_deployment=None)
            _emit(deployment, "gold", "Deployment successful ✓")
        else:
            docker.stop_container(new_container)
            _do_auto_rollback(deployment, service, docker)

    except Exception as exc:
        _emit(deployment, deployment.phase, f"Error: {exc}", level="error")
        Deployment.objects.filter(pk=deployment.pk).update(
            status=Deployment.Status.FAILED,
            failure_reason=str(exc),
            finished_at=timezone.now(),
        )
        service.__class__.objects.filter(pk=service.pk).update(active_deployment=None)
        raise

    return {"deployment_id": deployment_id, "status": deployment.status}


# ── Backup PostgreSQL ─────────────────────────────────────────────────────────

@shared_task(name="apps.deployments.tasks.backup_postgres", queue="backups")
def backup_postgres() -> dict:
    """Backup journalier PostgreSQL compressé vers S3 (rétention 30 jours)."""
    from django.conf import settings

    from adapters.storage_adapter import ObjectStorageAdapter

    db = settings.DATABASES["default"]
    db_name = db.get("NAME", "forge")
    date_str = timezone.now().strftime("%Y-%m-%d-%H%M")
    _, tmp_str = tempfile.mkstemp(prefix=f"forge-pg-{date_str}-", suffix=".sql.gz")
    dump_path = Path(tmp_str)

    result = subprocess.run(
        ["pg_dump", "--no-password", "--clean", "--if-exists", db_name],
        capture_output=True,
        env={
            "PGHOST": db.get("HOST", "localhost"),
            "PGPORT": str(db.get("PORT", "5432")),
            "PGUSER": db.get("USER", "forge"),
            "PGPASSWORD": db.get("PASSWORD", ""),
        },
    )
    if result.returncode != 0:
        raise RuntimeError(f"pg_dump failed: {result.stderr.decode()}")

    compressed = gzip.compress(result.stdout)
    dump_path.write_bytes(compressed)
    checksum = hashlib.sha256(compressed).hexdigest()

    s3_key = f"backups/postgres/{date_str}/{checksum[:8]}.sql.gz"
    storage = ObjectStorageAdapter()
    storage.upload(dump_path, s3_key)
    storage.rotate_old(prefix="backups/postgres/", keep_days=30)
    dump_path.unlink(missing_ok=True)

    return {"s3_key": s3_key, "checksum": checksum, "size_bytes": len(compressed)}


# ── Registry cleanup ──────────────────────────────────────────────────────────

@shared_task(name="apps.deployments.tasks.registry_cleanup", queue="backups")
def registry_cleanup() -> dict:
    """Supprime du registry les images sans déploiement SUCCESS actif."""
    from apps.deployments.models import Deployment

    from adapters.registry_adapter import RegistryAdapter

    registry = RegistryAdapter()
    active_refs = set(
        Deployment.objects.filter(status=Deployment.Status.SUCCESS)
        .exclude(image_ref="")
        .values_list("image_ref", flat=True)
    )

    removed = 0
    for image_ref in registry.list_all_images():
        if image_ref not in active_refs:
            try:
                registry.delete_image(image_ref)
                removed += 1
            except Exception:
                pass  # image déjà supprimée ou en cours d'utilisation

    return {"removed": removed}
