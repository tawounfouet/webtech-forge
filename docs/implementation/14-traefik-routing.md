# 14 — Traefik Routing

> **ADR de référence :** ADR-006
> **Dépendances :** 13-infrastructure-compose.md, 07-deployment-engine.md

---

## Configuration statique

```yaml
# infra/traefik/traefik.yml
api:
  dashboard: false

entryPoints:
  web:
    address: ":80"
    http:
      redirections:
        entrypoint:
          to: websecure
          scheme: https
  websecure:
    address: ":443"

providers:
  docker:
    exposedByDefault: false
    network: forge-edge
    watch: true
  file:
    directory: /traefik/dynamic
    watch: true

certificatesResolvers:
  letsencrypt:
    acme:
      email: "${ACME_EMAIL}"
      storage: /certs/acme.json
      httpChallenge:
        entryPoint: web

metrics:
  prometheus:
    addEntryPointsLabels: true
    addRoutersLabels: true
    addServicesLabels: true

log:
  level: INFO
  format: json

accessLog:
  format: json
  fields:
    headers:
      defaultMode: drop
      names:
        Authorization: redact
```

---

## Middlewares de sécurité (config dynamique)

```yaml
# infra/traefik/dynamic/middlewares.yml
http:
  middlewares:
    forge-security-headers:
      headers:
        sslRedirect: true
        stsSeconds: 31536000
        stsIncludeSubdomains: true
        contentTypeNosniff: true
        browserXssFilter: true
        referrerPolicy: "strict-origin-when-cross-origin"
        customResponseHeaders:
          X-Forge-Platform: "WebTech Forge v1"

    forge-rate-limit:
      rateLimit:
        average: 100
        burst: 50
        period: 1m
```

---

## Génération des labels par le TraefikAdapter

```python
# adapters/traefik_adapter.py (complet)
from pathlib import Path
import yaml
from django.conf import settings


class TraefikAdapter:
    DYNAMIC_DIR = Path(settings.TRAEFIK_DYNAMIC_DIR)

    @staticmethod
    def generate_labels(service, deployment) -> dict:
        workspace = service.environment.project.workspace
        service_id = f"forge-{workspace.slug}-{service.slug}-{deployment.id}"
        labels = {
            "traefik.enable": "true",
            f"traefik.http.services.{service_id}.loadbalancer.server.port": str(service.internal_port),
            f"traefik.http.routers.{service_id}.middlewares": "forge-security-headers@file,forge-rate-limit@file",
        }
        for domain in service.domains.all():
            router_id = f"{service_id}-d{domain.id}"
            labels[f"traefik.http.routers.{router_id}.entrypoints"] = "websecure"
            labels[f"traefik.http.routers.{router_id}.rule"] = f"Host(`{domain.hostname}`)"
            labels[f"traefik.http.routers.{router_id}.service"] = service_id
            if domain.tls_enabled:
                labels[f"traefik.http.routers.{router_id}.tls"] = "true"
                labels[f"traefik.http.routers.{router_id}.tls.certresolver"] = "letsencrypt"
        return labels

    @classmethod
    def write_dynamic_config(cls, service, container_ip: str, port: int) -> None:
        workspace = service.environment.project.workspace
        service_id = f"forge-{workspace.slug}-{service.slug}"
        config = {
            "http": {
                "services": {
                    service_id: {
                        "loadBalancer": {
                            "servers": [{"url": f"http://{container_ip}:{port}"}],
                            "healthCheck": {
                                "path": getattr(service, "healthcheck", None) and service.healthcheck.path or "/",
                                "interval": "30s",
                                "timeout": "5s",
                            },
                        }
                    }
                }
            }
        }
        config_path = cls.DYNAMIC_DIR / f"{service_id}.yml"
        with open(config_path, "w") as f:
            yaml.dump(config, f)

    @classmethod
    def remove_dynamic_config(cls, service) -> None:
        workspace = service.environment.project.workspace
        service_id = f"forge-{workspace.slug}-{service.slug}"
        config_path = cls.DYNAMIC_DIR / f"{service_id}.yml"
        if config_path.exists():
            config_path.unlink()
```

---

## Preview environments — Routing wildcard

Pour les preview environments (V2), chaque PR génère un sous-domaine unique :
`pr-{number}.{project-slug}.forge.internal`

Traefik supporte les wildcards avec DNS-01 challenge :

```yaml
# infra/traefik/dynamic/wildcard-certs.yml
tls:
  certificates:
    - certFile: /certs/wildcard.crt
      keyFile: /certs/wildcard.key
      stores:
        - default
```

Labels générés pour un preview environment :
```python
def generate_preview_labels(service, pr_number: int, project_slug: str) -> dict:
    hostname = f"pr-{pr_number}.{project_slug}.{settings.FORGE_DOMAIN}"
    service_id = f"forge-preview-{pr_number}-{service.slug}"
    return {
        "traefik.enable": "true",
        f"traefik.http.routers.{service_id}.rule": f"Host(`{hostname}`)",
        f"traefik.http.routers.{service_id}.tls": "true",
        f"traefik.http.services.{service_id}.loadbalancer.server.port": str(service.internal_port),
    }
```

---

## Blue/Green via fichier dynamique

La stratégie blue/green utilise le **provider file** de Traefik (plus fiable que les labels pour le switch atomique) :

```
Phase GOLD — démarrage :
  1. Nouveau conteneur démarre sans label traefik.enable
  2. Healthcheck vérifié directement via l'IP du conteneur
  3. Si healthy → TraefikAdapter.write_dynamic_config(service, new_ip, port)
  4. Traefik détecte le changement dans /traefik/dynamic/ et route vers le nouveau conteneur
  5. Ancien conteneur arrêté → TraefikAdapter.remove_dynamic_config(old_service_id)
```

Ce mécanisme évite le downtime : Traefik ne route jamais vers un conteneur non healthchecké.

---

## Monitoring Traefik

Prometheus scrape les métriques Traefik sur `:8080/metrics`. Métriques clés :

| Métrique | Usage |
|---|---|
| `traefik_router_requests_total` | Taux de requêtes par route/service |
| `traefik_router_request_duration_seconds` | Latence P50/P95/P99 par route |
| `traefik_service_open_connections` | Connexions actives par service |
| `traefik_tls_certs_not_after` | Expiration des certificats TLS |

Alert critique : `traefik_tls_certs_not_after < now() + 7 days` → alerte renouvellement cert.
