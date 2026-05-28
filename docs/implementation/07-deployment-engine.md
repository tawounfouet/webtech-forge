# 07 — Deployment Engine (Medallion Pipeline)

> **ADR de référence :** ADR-018, ADR-005, ADR-016
> **Dépendances :** 06-workers-celery.md, 15-isolation-reseau-docker.md, 16-registre-images.md

---

## Vue d'ensemble des phases

```
BRONZE  → Artefact source : clone Git, resolve commit SHA
SILVER  → Validation + Build : forge.yaml, secrets, build image, push registry
GOLD    → Live : create container, healthcheck, switch Traefik (blue/green), rollback si échec
```

Chaque phase produit des `DeploymentEvent` qui alimentent le streaming WebSocket et le Monitor Hub.

---

## State Machine des statuts

```
PENDING
  ↓ (enqueue Celery)
QUEUED
  ↓ (worker démarre)
CLONING          ← phase BRONZE
  ↓
VALIDATING       ← phase SILVER
  ↓
BUILDING
  ↓
RELEASING
  ↓
HEALTHCHECKING   ← phase GOLD
  ↓         ↓
SUCCESS    FAILED / ROLLED_BACK
```

Les transitions sont **séquentielles et non réversibles** — un déploiement ne peut pas revenir à un statut antérieur.

---

## DockerAdapter

```python
# adapters/docker_adapter.py
import docker
from docker.errors import DockerException
from django.conf import settings


class DockerAdapter:
    def __init__(self):
        self.client = docker.from_env()

    def ensure_workspace_network(self, workspace) -> None:
        name = workspace.docker_network_name
        try:
            self.client.networks.get(name)
        except docker.errors.NotFound:
            self.client.networks.create(
                name,
                driver="bridge",
                internal=True,
                labels={
                    "forge.workspace": workspace.slug,
                    "forge.managed": "true",
                },
            )

    def run_service(self, service, deployment, image_ref, env_vars, labels) -> docker.models.containers.Container:
        workspace = service.environment.project.workspace
        networks = [workspace.docker_network_name]
        if service.domains.exists():
            networks.append("forge-edge")

        container_name = f"forge-{workspace.slug}-{service.slug}-{deployment.id}"

        volumes = {}
        for vol in service.volumes.all():
            volumes[vol.name] = {"bind": vol.mount_path, "mode": "rw"}

        return self.client.containers.run(
            image=image_ref,
            name=container_name,
            detach=True,
            environment=env_vars,
            labels={**labels, "forge.deployment_id": str(deployment.id)},
            network=networks[0],
            volumes=volumes,
            restart_policy={"Name": "unless-stopped"},
        )

    def wait_for_healthy(self, container, healthcheck, timeout=120) -> bool:
        import time
        import requests

        if not healthcheck:
            time.sleep(5)
            container.reload()
            return container.status == "running"

        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                # Récupérer l'IP du conteneur dans son réseau principal
                container.reload()
                networks = container.attrs["NetworkSettings"]["Networks"]
                ip = list(networks.values())[0]["IPAddress"]
                resp = requests.get(
                    f"http://{ip}:{healthcheck.path}",
                    timeout=healthcheck.timeout_seconds,
                )
                if resp.status_code < 400:
                    return True
            except Exception:
                pass
            time.sleep(healthcheck.interval_seconds)
        return False

    def switch_traefik_traffic(self, service, new_container) -> None:
        # Active le label traefik sur le nouveau conteneur
        # Désactive le label sur l'ancien (s'il existe)
        old = self._find_active_container(service)
        if old:
            # Docker ne supporte pas la modification de labels en live
            # Solution : recréer le conteneur avec le label traefik.enable=false
            # ou utiliser le dynamic config file de Traefik
            pass
        new_container.reload()

    def stop_previous_container(self, service) -> None:
        old = self._find_active_container(service)
        if old:
            old.stop(timeout=30)
            old.remove()

    def restore_previous_container(self, service, previous_deployment) -> None:
        self.run_service(
            service=service,
            deployment=previous_deployment,
            image_ref=previous_deployment.image_ref,
            env_vars={},  # rechargé depuis les env vars actuels du service
            labels={},
        )

    def _find_active_container(self, service):
        containers = self.client.containers.list(
            filters={"label": f"forge.deployment_id={service.active_deployment_id}"}
        )
        return containers[0] if containers else None

    def get_container_logs(self, service, since=None, tail=100):
        container = self._find_active_container(service)
        if not container:
            return []
        return container.logs(since=since, tail=tail, timestamps=True).decode().splitlines()
```

---

## GitAdapter

```python
# adapters/git_adapter.py
import subprocess
import tempfile
import hashlib
import hmac
from pathlib import Path


class GitAdapter:
    def clone_and_checkout(self, service) -> tuple[Path, str]:
        repo = service.environment.project.repositories.filter(is_primary=True).first()
        if not repo:
            raise ValueError("No primary repository configured for this project")

        tmpdir = Path(tempfile.mkdtemp(prefix="forge-clone-"))
        subprocess.run(
            ["git", "clone", "--depth=1", "--branch", repo.default_branch, repo.repo_url, str(tmpdir)],
            check=True, capture_output=True,
        )
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=tmpdir, capture_output=True, text=True, check=True,
        )
        return tmpdir, result.stdout.strip()

    def validate_build_config(self, repo_path: Path, service) -> None:
        if service.runtime == "dockerfile":
            dockerfile = repo_path / service.dockerfile_path
            if not dockerfile.exists():
                raise FileNotFoundError(f"Dockerfile not found: {service.dockerfile_path}")
        elif service.runtime == "compose":
            compose_file = repo_path / (service.compose_file_path or "docker-compose.yml")
            if not compose_file.exists():
                raise FileNotFoundError(f"Compose file not found")

        forge_yaml = repo_path / "forge.yaml"
        if forge_yaml.exists():
            self._validate_forge_yaml(forge_yaml)

    def _validate_forge_yaml(self, path: Path) -> None:
        import yaml
        import jsonschema
        from pathlib import Path as P
        schema_path = P(settings.BASE_DIR) / "forge.yaml.schema.json"
        with open(path) as f:
            config = yaml.safe_load(f)
        with open(schema_path) as f:
            import json
            schema = json.load(f)
        jsonschema.validate(config, schema)

    @staticmethod
    def validate_webhook_signature(secret: str, payload: bytes, signature: str) -> bool:
        expected = "sha256=" + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)
```

---

## TraefikAdapter — Génération de labels

```python
# adapters/traefik_adapter.py


class TraefikAdapter:
    @staticmethod
    def generate_labels(service, deployment) -> dict:
        workspace = service.environment.project.workspace
        service_id = f"forge-{workspace.slug}-{service.slug}"
        labels = {
            "traefik.enable": "true",
            f"traefik.http.services.{service_id}.loadbalancer.server.port": str(service.internal_port),
        }
        for domain in service.domains.all():
            router_id = f"{service_id}-{domain.id}"
            labels[f"traefik.http.routers.{router_id}.rule"] = f"Host(`{domain.hostname}`)"
            if domain.tls_enabled:
                labels[f"traefik.http.routers.{router_id}.tls"] = "true"
                labels[f"traefik.http.routers.{router_id}.tls.certresolver"] = "letsencrypt"
            labels[f"traefik.http.routers.{router_id}.service"] = service_id

        # Middleware de sécurité par défaut
        labels[f"traefik.http.routers.{service_id}.middlewares"] = "forge-security-headers@file"
        return labels
```

---

## Stratégie Blue/Green

En phase Gold, le switch de trafic se fait en deux étapes atomiques :

1. **Start** : le nouveau conteneur démarre, attaché au réseau workspace. Traefik n'a pas encore son label `traefik.enable=true`.
2. **Healthcheck** : dès que le healthcheck est vert, le label `traefik.enable=true` est ajouté via mise à jour du dynamic config de Traefik (fichier YAML dans `/traefik/dynamic/`).
3. **Switch** : Traefik détecte le changement et route le trafic vers le nouveau conteneur.
4. **Cleanup** : l'ancien conteneur est arrêté et supprimé.

```python
# Dans DockerAdapter.switch_traefik_traffic
def switch_traefik_traffic(self, service, new_container) -> None:
    import yaml
    workspace = service.environment.project.workspace
    service_id = f"forge-{workspace.slug}-{service.slug}"
    dynamic_path = Path(settings.TRAEFIK_DYNAMIC_DIR) / f"{service_id}.yaml"

    config = {
        "http": {
            "services": {
                service_id: {
                    "loadBalancer": {
                        "servers": [{"url": f"http://{self._get_container_ip(new_container)}:{service.internal_port}"}]
                    }
                }
            }
        }
    }
    with open(dynamic_path, "w") as f:
        yaml.dump(config, f)
    # Traefik watch le dossier et recharge automatiquement
```
