"""
Adapter Docker SDK — interface entre le deployment engine et le daemon Docker.
Implémentation complète dans 07-deployment-engine.md.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


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

    def pull_image(self, image_ref: str) -> str:
        logger.info("pulling_image", extra={"image": image_ref})
        image = self._client.images.pull(image_ref)
        return image.id

    def build_image(self, context_path: str, dockerfile: str, tag: str) -> str:
        logger.info("building_image", extra={"tag": tag})
        image, logs = self._client.images.build(
            path=context_path,
            dockerfile=dockerfile,
            tag=tag,
            rm=True,
        )
        return image.id

    def run_container(self, spec: ContainerSpec) -> str:
        logger.info("running_container", extra={"name": spec.name})
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

    def stop_container(self, container_name: str, timeout: int = 30) -> None:
        logger.info("stopping_container", extra={"name": container_name})
        try:
            container = self._client.containers.get(container_name)
            container.stop(timeout=timeout)
            container.remove()
        except Exception as exc:  # noqa: BLE001
            logger.warning("container_stop_failed", extra={"name": container_name, "error": str(exc)})

    def create_network(self, network_name: str) -> str:
        logger.info("creating_network", extra={"name": network_name})
        network = self._client.networks.create(
            network_name,
            driver="bridge",
            labels={"managed-by": "webtech-forge"},
        )
        return network.id

    def get_container_logs(self, container_name: str, tail: int = 100) -> list[str]:
        container = self._client.containers.get(container_name)
        raw = container.logs(tail=tail, timestamps=True)
        return raw.decode("utf-8", errors="replace").splitlines()

    def healthcheck(self, container_name: str, path: str, port: int) -> bool:
        import urllib.request

        url = f"http://{container_name}:{port}{path}"
        try:
            with urllib.request.urlopen(url, timeout=5) as resp:  # noqa: S310
                return resp.status < 400
        except Exception:  # noqa: BLE001
            return False
