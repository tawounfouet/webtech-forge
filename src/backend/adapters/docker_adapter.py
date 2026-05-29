"""
Adapter Docker SDK — interface entre le deployment engine et le daemon Docker.
"""
from __future__ import annotations

import logging
import time
import urllib.request
from dataclasses import dataclass

logger = logging.getLogger(__name__)

_BLUE = "blue"
_GREEN = "green"


@dataclass
class ContainerSpec:
    name: str
    image: str
    env_vars: dict[str, str]
    network: str
    ports: dict[int, int] | None = None
    volumes: dict[str, str] | None = None
    labels: dict[str, str] | None = None
    cpu_limit: float = 0.0
    memory_limit_mb: int = 0


class DockerAdapter:
    def __init__(self, socket_url: str = "unix://var/run/docker.sock") -> None:
        import docker

        self._client = docker.DockerClient(base_url=socket_url)

    # ── Network ───────────────────────────────────────────────────────────────

    def ensure_workspace_network(self, workspace) -> str:
        network_name = workspace.docker_network_name
        try:
            self._client.networks.get(network_name)
            logger.info("network_exists", extra={"network": network_name})
        except Exception:
            self._client.networks.create(
                network_name,
                driver="bridge",
                labels={"managed-by": "webtech-forge", "workspace": workspace.slug},
            )
            logger.info("network_created", extra={"network": network_name})
        return network_name

    def create_network(self, network_name: str) -> str:
        network = self._client.networks.create(
            network_name,
            driver="bridge",
            labels={"managed-by": "webtech-forge"},
        )
        return network.id

    # ── Container lifecycle ───────────────────────────────────────────────────

    def run_service(self, service, _deployment, image_ref: str, env_vars: dict, labels: dict):
        """Lance un nouveau conteneur blue/green pour le service."""
        color = self._next_color(service)
        name = f"{service.slug}-{color}"
        network = service.environment.project.workspace.docker_network_name

        volumes = {
            v.name: {"bind": v.mount_path, "mode": "rw"}
            for v in service.volumes.all()
        }

        logger.info("running_container", extra={"name": name, "image": image_ref})
        container = self._client.containers.run(
            image=image_ref,
            name=name,
            environment=env_vars,
            network=network,
            volumes=volumes,
            labels={**(labels or {}), "forge.color": color, "forge.service": service.slug},
            detach=True,
            remove=False,
        )
        return container

    def run_container(self, spec: ContainerSpec) -> str:
        container = self._client.containers.run(
            image=spec.image,
            name=spec.name,
            environment=spec.env_vars,
            network=spec.network,
            ports=spec.ports or {},
            volumes=spec.volumes or {},
            labels=spec.labels or {},
            detach=True,
            remove=False,
        )
        return container.id

    def stop_container(self, container, timeout: int = 30) -> None:
        """Arrête et supprime un conteneur (accepte un objet container ou un nom)."""
        if isinstance(container, str):
            try:
                container = self._client.containers.get(container)
            except Exception as exc:
                logger.warning("container_not_found", extra={"name": container, "error": str(exc)})
                return
        try:
            container.stop(timeout=timeout)
            container.remove()
            logger.info("container_stopped", extra={"name": container.name})
        except Exception as exc:
            logger.warning("container_stop_failed", extra={"error": str(exc)})

    def stop_previous_container(self, service) -> None:
        """Arrête les conteneurs du service qui ne sont pas le conteneur actif actuel."""
        for color in (_BLUE, _GREEN):
            name = f"{service.slug}-{color}"
            try:
                c = self._client.containers.get(name)
                labels = c.labels or {}
                # Ne pas arrêter le conteneur fraîchement déployé (marqué "new")
                if labels.get("forge.new") != "true":
                    c.stop(timeout=30)
                    c.remove()
                    logger.info("previous_container_stopped", extra={"name": name})
            except Exception:
                pass

    def restore_previous_container(self, service, previous_deployment) -> None:
        """Relance le conteneur depuis le déploiement précédent pour le rollback."""
        image_ref = previous_deployment.image_ref
        if not image_ref:
            raise ValueError("Previous deployment has no image_ref — cannot restore")

        color = self._next_color(service)
        name = f"{service.slug}-{color}"
        network = service.environment.project.workspace.docker_network_name

        logger.info("restoring_container", extra={"name": name, "image": image_ref})
        self._client.containers.run(
            image=image_ref,
            name=name,
            network=network,
            labels={"forge.service": service.slug, "forge.rollback": "true"},
            detach=True,
            remove=False,
        )

    # ── Healthcheck ───────────────────────────────────────────────────────────

    def wait_for_healthy(self, container, healthcheck=None, max_wait: int = 120) -> bool:
        """Attend que le conteneur soit sain (HTTP ou Docker native healthcheck)."""
        if healthcheck is None:
            return self._wait_docker_healthy(container, max_wait)

        protocol = getattr(healthcheck, "protocol", "http")
        if protocol == "http":
            return self._wait_http_healthy(
                host=container.name,
                path=healthcheck.path,
                port=getattr(healthcheck, "port", None) or 8000,
                interval=healthcheck.interval_seconds,
                timeout=healthcheck.timeout_seconds,
                retries=healthcheck.retries,
            )
        return self._wait_docker_healthy(container, max_wait)

    def _wait_http_healthy(
        self, host: str, path: str, port: int, interval: int, timeout: int, retries: int
    ) -> bool:
        url = f"http://{host}:{port}{path}"
        for attempt in range(retries):
            try:
                with urllib.request.urlopen(url, timeout=timeout) as resp:  # noqa: S310
                    if resp.status < 400:
                        logger.info("healthcheck_passed", extra={"url": url, "attempt": attempt})
                        return True
            except Exception as exc:
                logger.debug("healthcheck_attempt_failed", extra={"url": url, "attempt": attempt, "error": str(exc)})
            time.sleep(interval)
        return False

    def _wait_docker_healthy(self, container, max_wait: int) -> bool:
        deadline = time.monotonic() + max_wait
        while time.monotonic() < deadline:
            container.reload()
            state = container.attrs.get("State", {})
            health = state.get("Health", {})
            status = health.get("Status", "")
            if status == "healthy":
                return True
            if status == "unhealthy":
                return False
            time.sleep(5)
        container.reload()
        return container.attrs.get("State", {}).get("Status") == "running"

    # ── Traefik blue/green ────────────────────────────────────────────────────

    def switch_traefik_traffic(self, service, new_container) -> None:
        """
        Marque le nouveau conteneur comme actif pour Traefik.
        Traefik relit les labels Docker automatiquement — on met à jour
        les labels du nouveau conteneur pour retirer le flag 'new'.
        """
        try:
            new_container.reload()
            new_container.labels.pop("forge.new", None)
            logger.info("traefik_traffic_switched", extra={"service": service.slug, "container": new_container.name})
        except Exception as exc:
            logger.warning("traefik_switch_failed", extra={"error": str(exc)})

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _next_color(self, service) -> str:
        """Retourne la couleur (blue/green) non utilisée actuellement."""
        for color in (_BLUE, _GREEN):
            try:
                self._client.containers.get(f"{service.slug}-{color}")
            except Exception:
                return color
        return _BLUE

    def pull_image(self, image_ref: str) -> str:
        image = self._client.images.pull(image_ref)
        return image.id

    def build_image(self, context_path: str, dockerfile: str, tag: str) -> str:
        image, _ = self._client.images.build(
            path=context_path,
            dockerfile=dockerfile,
            tag=tag,
            rm=True,
        )
        return image.id

    def get_container_logs(self, container_name: str, tail: int = 100) -> list[str]:
        container = self._client.containers.get(container_name)
        raw = container.logs(tail=tail, timestamps=True)
        return raw.decode("utf-8", errors="replace").splitlines()

    def healthcheck(self, container_name: str, path: str, port: int) -> bool:
        url = f"http://{container_name}:{port}{path}"
        try:
            with urllib.request.urlopen(url, timeout=5) as resp:  # noqa: S310
                return resp.status < 400
        except Exception:
            return False
