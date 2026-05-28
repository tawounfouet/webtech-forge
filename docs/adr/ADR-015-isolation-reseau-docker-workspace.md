# ADR-015 — Isolation réseau Docker stricte par Workspace

- **Statut :** Accepté
- **Priorité :** P1
- **Date :** 2026-05-27
- **Décideurs :** Équipe WebTech Forge

## Contexte

WebTech Forge est multi-tenant : plusieurs workspaces partagent le même Docker Engine. Sans isolation réseau explicite, un conteneur d'un workspace pourrait atteindre les conteneurs d'un autre workspace via le réseau bridge par défaut de Docker. Ce serait un trou de sécurité critique.

L'isolation RBAC au niveau de l'API Django ne suffit pas : elle protège l'accès au control plane mais pas les communications réseau entre conteneurs au runtime.

## Décision

Chaque Workspace dispose d'un **réseau Docker nommé dédié** `forge-ws-{workspace-slug}`. Les conteneurs d'un workspace ne peuvent pas communiquer avec ceux d'un autre workspace sans un binding explicite approuvé.

### Topologie des réseaux

```
forge-platform    → control plane uniquement (Django, Celery, Redis, PG)
forge-edge        → Traefik uniquement (ports 80/443 exposés)
forge-ws-acme     → conteneurs du Workspace "acme"
forge-ws-beta     → conteneurs du Workspace "beta"
forge-link-X-Y    → liaison cross-workspace (V3, ForgeStore Shortcuts uniquement)
```

### Règles d'attachement réseau

| Conteneur | Réseaux attachés |
|---|---|
| Service web exposé (Workspace A) | `forge-ws-{slug-A}` + `forge-edge` |
| Service worker non exposé (Workspace A) | `forge-ws-{slug-A}` uniquement |
| DB managée (Workspace A) | `forge-ws-{slug-A}` uniquement |
| Control plane Django | `forge-platform` uniquement |
| Traefik | `forge-edge` + accès socket Docker (lecture seule) |

### Implémentation dans DockerAdapter

```python
class DockerAdapter:
    def ensure_workspace_network(self, workspace: Workspace) -> None:
        network_name = workspace.docker_network_name  # forge-ws-{slug}
        try:
            self.client.networks.get(network_name)
        except docker.errors.NotFound:
            self.client.networks.create(
                network_name,
                driver="bridge",
                internal=True,  # pas d'accès internet sauf via forge-edge
                labels={"forge.workspace": workspace.slug}
            )

    def run_service(self, service: Service, deployment: Deployment) -> None:
        networks = [service.environment.project.workspace.docker_network_name]
        if service.is_exposed:
            networks.append("forge-edge")
        # ...
```

## Justification

- **Sécurité multi-tenant :** sans réseau dédié, un conteneur compromis dans le Workspace A peut scanner et atteindre les services du Workspace B via le bridge Docker par défaut.
- **NIST SP 800-190 :** recommande explicitement l'isolation réseau entre workloads de tenants différents dans les environnements de conteneurs partagés.
- **Principe de moindre privilège :** un service qui n'a pas besoin d'Internet ne doit pas y avoir accès (`internal: True`).

## Alternatives considérées

| Alternative | Rejet |
|---|---|
| Réseau bridge par défaut Docker | Pas d'isolation entre workspaces — tous les conteneurs sur le même réseau |
| iptables rules manuelles | Fragiles, non portables, difficiles à auditer |
| Network policies Kubernetes | Différé avec K8s (V3+) |

## Conséquences

- La création d'un réseau `forge-ws-{slug}` est obligatoire avant tout premier déploiement dans un workspace.
- La suppression d'un workspace déclenche la suppression de son réseau Docker et de tous ses conteneurs.
- Les tests d'intégration vérifient que deux conteneurs de workspaces différents ne peuvent pas se pinger.
- Le `DockerAdapter` logue toute création/suppression de réseau dans l'`AuditLog`.
- En V3, `ForgeStore Shortcuts` crée un réseau `forge-link-{src}-{tgt}` — révocable à tout moment par le workspace source.
