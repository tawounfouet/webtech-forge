# 16 — Registre d'images

> **ADR de référence :** ADR-016
> **Dépendances :** 07-deployment-engine.md, 13-infrastructure-compose.md

---

## Convention de nommage des tags

```
localhost:5000/{workspace_slug}/{service_slug}:{commit_sha7}
localhost:5000/{workspace_slug}/{service_slug}:latest
```

Exemples :
```
localhost:5000/acme/web:a1b2c3d
localhost:5000/acme/web:latest
localhost:5000/beta-corp/api:e4f5g6h
```

Le tag `{commit_sha7}` est **immuable** — c'est lui qui est stocké dans `Deployment.image_ref`. Le tag `latest` est mis à jour à chaque build réussi.

---

## RegistryAdapter

```python
# adapters/registry_adapter.py
import subprocess
from pathlib import Path
import docker
from django.conf import settings


class RegistryAdapter:
    def __init__(self):
        self.client = docker.from_env()
        self.registry_url = settings.REGISTRY_URL  # localhost:5000

    def build_and_push(
        self,
        workspace_slug: str,
        service_slug: str,
        commit_sha: str,
        context_path: Path,
        dockerfile_path: str = "Dockerfile",
        build_args: dict | None = None,
    ) -> str:
        sha7 = commit_sha[:7]
        image_name = f"{workspace_slug}/{service_slug}"
        versioned_ref = f"{self.registry_url}/{image_name}:{sha7}"
        latest_ref = f"{self.registry_url}/{image_name}:latest"

        # Build
        self.client.images.build(
            path=str(context_path),
            dockerfile=dockerfile_path,
            tag=versioned_ref,
            buildargs=build_args or {},
            rm=True,
            labels={
                "forge.workspace": workspace_slug,
                "forge.service": service_slug,
                "forge.commit": commit_sha,
            },
        )

        # Tag latest
        image = self.client.images.get(versioned_ref)
        image.tag(latest_ref)

        # Push les deux tags
        self.client.images.push(versioned_ref)
        self.client.images.push(latest_ref)

        # Récupérer le digest de l'image pushée
        image.reload()
        digest = image.id  # sha256:...

        # Nettoyer le cache local (l'image est dans le registry)
        self.client.images.remove(versioned_ref, force=False)

        return versioned_ref

    def pull(self, image_ref: str) -> None:
        self.client.images.pull(image_ref)

    def list_tags(self, workspace_slug: str, service_slug: str) -> list[str]:
        import requests
        url = f"http://{self.registry_url}/v2/{workspace_slug}/{service_slug}/tags/list"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 404:
            return []
        resp.raise_for_status()
        return resp.json().get("tags") or []

    def delete_tag(self, workspace_slug: str, service_slug: str, tag: str) -> None:
        import requests
        # Étape 1 : récupérer le digest du tag
        head_url = f"http://{self.registry_url}/v2/{workspace_slug}/{service_slug}/manifests/{tag}"
        resp = requests.head(
            head_url,
            headers={"Accept": "application/vnd.docker.distribution.manifest.v2+json"},
            timeout=10,
        )
        digest = resp.headers.get("Docker-Content-Digest")
        if not digest:
            return

        # Étape 2 : supprimer le digest
        del_url = f"http://{self.registry_url}/v2/{workspace_slug}/{service_slug}/manifests/{digest}"
        requests.delete(del_url, timeout=10)
```

---

## Tâche de rétention — Cleanup

```python
# apps/deployments/tasks.py
@shared_task(queue="backups")
def registry_cleanup():
    """
    Pour chaque service, conserver les 10 derniers tags (par ordre de déploiement).
    Supprimer les tags plus anciens.
    """
    from apps.services.models import Service
    from adapters.registry_adapter import RegistryAdapter

    registry = RegistryAdapter()
    MAX_TAGS = 10  # Configurable via WorkspaceQuota

    for service in Service.objects.select_related("environment__project__workspace"):
        workspace_slug = service.environment.project.workspace.slug
        try:
            tags = registry.list_tags(workspace_slug, service.slug)
            # Exclure "latest" et trier par date (les tags sha7 sont triés alphabétiquement
            # mais on se base sur les Deployment.created_at pour l'ordre réel)
            sha_tags = [t for t in tags if t != "latest"]

            # Récupérer les deployments dans l'ordre antéchronologique
            from apps.deployments.models import Deployment
            ordered_refs = list(
                Deployment.objects.filter(service=service, image_ref__isnull=False)
                .order_by("-created_at")
                .values_list("image_ref", flat=True)[:MAX_TAGS]
            )
            tags_to_keep = set()
            for ref in ordered_refs:
                if ":" in ref:
                    tags_to_keep.add(ref.split(":")[-1])

            for tag in sha_tags:
                if tag not in tags_to_keep:
                    try:
                        registry.delete_tag(workspace_slug, service.slug, tag)
                    except Exception:
                        pass
        except Exception:
            continue
```

---

## Migration V2 → Harbor

Quand le registre local est remplacé par Harbor en V2 :

1. Configurer Harbor avec le même namespace `{workspace_slug}/{service_slug}`.
2. Mettre à jour `REGISTRY_URL` dans les settings.
3. Migrer les images existantes (script one-shot) :

```bash
#!/usr/bin/env bash
# scripts/migrate-registry.sh
OLD_REGISTRY=localhost:5000
NEW_REGISTRY=harbor.forge.internal

docker images --format "{{.Repository}}:{{.Tag}}" | grep "^${OLD_REGISTRY}" | while read img; do
  new_img="${img/$OLD_REGISTRY/$NEW_REGISTRY}"
  docker pull "$img"
  docker tag "$img" "$new_img"
  docker push "$new_img"
  echo "Migrated: $img → $new_img"
done
```

4. Mettre à jour `Deployment.image_ref` en base pour pointer vers le nouveau registry.
5. Tester un rollback pour valider la migration.

---

## Monitoring du registre

```yaml
# infra/prometheus/prometheus.yml (extrait)
scrape_configs:
  - job_name: registry
    static_configs:
      - targets: ["registry:5001"]  # /metrics sur le port debug
    metrics_path: /metrics
```

Alerte critique :
```yaml
# infra/prometheus/rules/registry.yml
groups:
  - name: registry
    rules:
      - alert: RegistryDiskCritical
        expr: node_filesystem_avail_bytes{mountpoint="/var/lib/registry"} / node_filesystem_size_bytes{mountpoint="/var/lib/registry"} < 0.15
        for: 5m
        annotations:
          summary: "Registry disk usage critical (< 15% free)"
```
