# 17 — Observabilité

> **ADR de référence :** ADR-009
> **Dépendances :** 13-infrastructure-compose.md

---

## Stack complète

| Composant | Rôle | Port interne |
|---|---|---|
| Prometheus | Scraping + stockage métriques | 9090 |
| Alertmanager | Routage des alertes | 9093 |
| Grafana | Dashboards | 3001 |
| Loki | Agrégation logs | 3100 |
| cAdvisor | Métriques conteneurs Docker | 8081 |
| postgres-exporter | Métriques PostgreSQL | 9187 |
| redis-exporter | Métriques Redis | 9121 |

---

## Configuration Prometheus

```yaml
# infra/prometheus/prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

alerting:
  alertmanagers:
    - static_configs:
        - targets: ["alertmanager:9093"]

rule_files:
  - /etc/prometheus/rules/*.yml

scrape_configs:
  - job_name: forge-api
    static_configs:
      - targets: ["api:8000"]
    metrics_path: /metrics

  - job_name: cadvisor
    static_configs:
      - targets: ["cadvisor:8080"]

  - job_name: postgres
    static_configs:
      - targets: ["postgres-exporter:9187"]

  - job_name: redis-broker
    static_configs:
      - targets: ["redis-exporter-broker:9121"]
    relabel_configs:
      - source_labels: [__address__]
        target_label: instance
        replacement: redis-broker

  - job_name: traefik
    static_configs:
      - targets: ["traefik:8080"]

  - job_name: node
    static_configs:
      - targets: ["node-exporter:9100"]
```

---

## Métriques Prometheus depuis Django

```python
# apps/deployments/metrics.py
from prometheus_client import Counter, Histogram, Gauge

deployment_total = Counter(
    "forge_deployment_total",
    "Total deployments triggered",
    ["workspace", "service", "trigger_source"],
)

deployment_duration = Histogram(
    "forge_deployment_duration_seconds",
    "Duration of deployments in seconds",
    ["workspace", "phase"],
    buckets=[10, 30, 60, 120, 300, 600],
)

deployment_failures = Counter(
    "forge_deployment_failures_total",
    "Failed deployments",
    ["workspace", "service", "phase"],
)

active_services = Gauge(
    "forge_active_services_total",
    "Number of services with at least one successful deployment",
    ["workspace"],
)

activator_executions = Counter(
    "forge_activator_executions_total",
    "Activator rule executions",
    ["workspace", "action_type", "success"],
)
```

```python
# config/urls.py (ajout de l'endpoint /metrics)
from django.urls import path
from prometheus_client import make_wsgi_app
from django.http import HttpResponse
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

def metrics_view(request):
    return HttpResponse(generate_latest(), content_type=CONTENT_TYPE_LATEST)

urlpatterns += [path("metrics", metrics_view)]
```

---

## Règles d'alerte

```yaml
# infra/prometheus/rules/forge.yml
groups:
  - name: forge-platform
    rules:
      - alert: ForgeAPIHighErrorRate
        expr: rate(django_http_responses_total_by_status_urlconf_method_view_agent_referer_total{status=~"5.."}[5m]) > 0.05
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "Forge API 5xx rate > 5%"

      - alert: ForgeCeleryQueueDepth
        expr: celery_queue_length{queue="deployments"} > 50
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Deployment queue depth > 50"

      - alert: ForgeDeploymentFailureRate
        expr: rate(forge_deployment_failures_total[10m]) > 0.1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Deployment failure rate elevated"

      - alert: ForgeBackupMissed
        expr: time() - forge_last_backup_timestamp_seconds > 86400 + 3600
        labels:
          severity: critical
        annotations:
          summary: "PostgreSQL backup missed (> 25h since last backup)"

      - alert: RegistryDiskCritical
        expr: (node_filesystem_size_bytes{mountpoint="/var/lib/registry"} - node_filesystem_avail_bytes{mountpoint="/var/lib/registry"}) / node_filesystem_size_bytes{mountpoint="/var/lib/registry"} > 0.85
        for: 10m
        labels:
          severity: critical
        annotations:
          summary: "Registry disk > 85% full"

      - alert: TLSCertExpiringSoon
        expr: traefik_tls_certs_not_after - time() < 7 * 86400
        labels:
          severity: warning
        annotations:
          summary: "TLS certificate expiring in less than 7 days"
```

---

## Configuration Loki

```yaml
# infra/loki/config.yml
auth_enabled: false

server:
  http_listen_port: 3100

ingester:
  lifecycler:
    address: 127.0.0.1
    ring:
      kvstore:
        store: inmemory
      replication_factor: 1

schema_config:
  configs:
    - from: 2024-01-01
      store: boltdb-shipper
      object_store: filesystem
      schema: v11
      index:
        prefix: index_
        period: 24h

storage_config:
  boltdb_shipper:
    active_index_directory: /loki/boltdb-shipper-active
    cache_location: /loki/boltdb-shipper-cache
  filesystem:
    directory: /loki/chunks

limits_config:
  retention_period: 2160h  # 90 jours
  ingestion_rate_mb: 10
  max_query_length: 720h
```

### Labels Loki obligatoires

Chaque ligne de log applicatif doit porter les labels :
```json
{
  "workspace": "acme",
  "project": "my-app",
  "service": "web",
  "deployment_id": "1234",
  "environment": "production"
}
```

Configuration Docker logging driver (dans les labels du conteneur) :
```yaml
labels:
  logging: "loki"
  logging_jobname: "forge-service"
  forge.workspace: "acme"
  forge.service: "web"
```

---

## Dashboards Grafana

| Dashboard | Contenu |
|---|---|
| **Forge Platform** | API latence, Celery queue depth, déploiements/heure, taux d'échec |
| **Forge Workspaces** | Consommation CPU/mémoire par workspace, services actifs |
| **Forge SLOs** | Taux de disponibilité API, taux de déploiements réussis, P95 Celery |
| **Infrastructure** | Métriques host (CPU, mémoire, disque, réseau), PostgreSQL, Redis |
| **Activator** | Règles déclenchées, actions exécutées, circuit-breakers actifs |

Les dashboards sont provisionnés via les fichiers JSON dans `infra/grafana/dashboards/`.
