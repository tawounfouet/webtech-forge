# 15 — Isolation réseau Docker par Workspace

> **ADR de référence :** ADR-015
> **Dépendances :** 07-deployment-engine.md

---

## Règles d'attachement réseau

| Conteneur | Réseaux | Justification |
|---|---|---|
| Service web exposé | `forge-ws-{slug}` + `forge-edge` | Doit être routé par Traefik |
| Service worker/cron | `forge-ws-{slug}` uniquement | Pas d'exposition publique |
| Database managée | `forge-ws-{slug}` uniquement | Accès interne uniquement |
| Control plane Django | `forge-platform` uniquement | Jamais accessible aux workloads |
| Traefik | `forge-edge` + accès socket Docker (ro) | Route le trafic public |
| Celery worker | `forge-platform` + `forge-ws-{slug}` (pendant les ops) | Doit créer/inspecter les conteneurs |

---

## Implémentation complète du DockerAdapter (partie réseau)

```python
# adapters/docker_adapter.py (partie réseau)
import docker
from django.conf import settings


class DockerAdapter:
    def __init__(self):
        self.client = docker.from_env()

    def ensure_workspace_network(self, workspace) -> str:
        name = workspace.docker_network_name  # forge-ws-{slug}
        try:
            network = self.client.networks.get(name)
        except docker.errors.NotFound:
            network = self.client.networks.create(
                name,
                driver="bridge",
                internal=True,           # pas d'accès internet direct
                enable_ipv6=False,
                labels={
                    "forge.workspace": workspace.slug,
                    "forge.managed": "true",
                    "forge.workspace_id": str(workspace.pk),
                },
                options={"com.docker.network.bridge.name": f"fwk{workspace.pk}"},
            )
            self._log_audit(workspace, "network.create", name)
        return name

    def delete_workspace_network(self, workspace) -> None:
        name = workspace.docker_network_name
        try:
            network = self.client.networks.get(name)
            # Arrêter tous les conteneurs du workspace avant de supprimer le réseau
            containers = self.client.containers.list(
                filters={"network": name}
            )
            for c in containers:
                c.stop(timeout=10)
                c.remove()
            network.remove()
            self._log_audit(workspace, "network.delete", name)
        except docker.errors.NotFound:
            pass

    def connect_to_edge(self, container, service) -> None:
        if service.domains.exists():
            try:
                edge_network = self.client.networks.get("forge-edge")
                edge_network.connect(container)
            except docker.errors.NotFound:
                raise RuntimeError("forge-edge network not found — is Traefik running?")

    def get_workspace_containers(self, workspace) -> list:
        return self.client.containers.list(
            filters={"network": workspace.docker_network_name, "label": "forge.managed=true"}
        )

    def _log_audit(self, workspace, action: str, resource: str) -> None:
        from apps.audit.models import AuditLog
        AuditLog.objects.create(
            workspace=workspace,
            action=f"docker.{action}",
            resource_type="network",
            resource_id=resource,
        )
```

---

## Vérification de l'isolation

Script de test d'isolation à exécuter après chaque changement du DockerAdapter :

```bash
#!/usr/bin/env bash
# tests/integration/test_network_isolation.sh

set -e

echo "=== Test d'isolation réseau entre workspaces ==="

# Créer deux conteneurs dans des workspaces différents
docker run -d --name test-ws-alpha --network forge-ws-alpha alpine sleep 300
docker run -d --name test-ws-beta  --network forge-ws-beta  alpine sleep 300

# Récupérer l'IP du conteneur alpha
IP_ALPHA=$(docker inspect test-ws-alpha --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}')

# Vérifier que beta ne peut pas ping alpha
if docker exec test-ws-beta ping -c 1 -W 2 "$IP_ALPHA" 2>/dev/null; then
  echo "FAIL: beta peut atteindre alpha — isolation réseau compromise"
  exit 1
else
  echo "PASS: beta ne peut pas atteindre alpha ✓"
fi

# Cleanup
docker rm -f test-ws-alpha test-ws-beta
```

Test pytest équivalent :

```python
# tests/integration/test_network_isolation.py
import docker
import pytest


@pytest.mark.integration
def test_workspace_network_isolation():
    client = docker.from_env()

    # Créer deux réseaux de workspaces simulés
    net_a = client.networks.create("test-forge-ws-alpha", driver="bridge", internal=True)
    net_b = client.networks.create("test-forge-ws-beta", driver="bridge", internal=True)

    try:
        # Démarrer un conteneur dans chaque réseau
        container_a = client.containers.run(
            "alpine", "sleep 30", detach=True, network="test-forge-ws-alpha"
        )
        container_b = client.containers.run(
            "alpine", "sleep 30", detach=True, network="test-forge-ws-beta"
        )

        # Récupérer l'IP de A
        container_a.reload()
        ip_a = container_a.attrs["NetworkSettings"]["Networks"]["test-forge-ws-alpha"]["IPAddress"]

        # B ne doit pas pouvoir atteindre A
        result = container_b.exec_run(f"ping -c 1 -W 2 {ip_a}")
        assert result.exit_code != 0, "Network isolation failed: beta can reach alpha"

    finally:
        container_a.remove(force=True)
        container_b.remove(force=True)
        net_a.remove()
        net_b.remove()
```

---

## Nettoyage des réseaux orphelins

```python
# apps/deployments/tasks.py
@shared_task
def cleanup_orphan_networks():
    """Supprime les réseaux forge-ws-* dont le workspace n'existe plus."""
    import docker
    from apps.workspaces.models import Workspace

    client = docker.from_env()
    forge_networks = client.networks.list(filters={"label": "forge.managed=true"})
    existing_slugs = set(Workspace.objects.values_list("slug", flat=True))

    for network in forge_networks:
        slug = network.labels.get("forge.workspace")
        if slug and slug not in existing_slugs:
            try:
                # Ne supprimer que si aucun conteneur n'est connecté
                if not network.containers:
                    network.remove()
            except Exception:
                pass
```
