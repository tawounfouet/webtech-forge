# ADR-009 — Observabilité via Prometheus + Grafana + Loki + Alertmanager

- **Statut :** Accepté
- **Priorité :** P1
- **Date :** 2026-05-27
- **Décideurs :** Équipe WebTech Forge

## Contexte

La plateforme doit être observable à deux niveaux :
1. **Métriques infra** : CPU, mémoire, réseau des conteneurs déployés et du control plane.
2. **Logs applicatifs** : logs des services déployés et du control plane lui-même.

Les SLOs définis (99,5 % API, 95 % déploiements réussis, P95 Celery < 30s) nécessitent un système d'alerting fiable.

## Décision

Adopter la stack **Prometheus + Grafana + Loki + Alertmanager** comme socle d'observabilité.

| Composant | Rôle |
|---|---|
| **Prometheus** | Scraping des métriques (control plane, Docker via cAdvisor, Redis, PostgreSQL) |
| **Alertmanager** | Routage des alertes (email, Slack, webhook) selon les SLOs |
| **Grafana** | Dashboards infra et applicatifs |
| **Loki** | Agrégation des logs à faible coût d'indexation (labels only, pas de full-text index) |

Le **Forge Activator** consomme également les métriques Prometheus pour évaluer ses règles — le `MetricsAdapter` appelle l'API Prometheus PromQL en lecture.

## Justification

- **Standard de facto :** stack non propriétaire, large communauté, nombreux exporters disponibles.
- **Loki vs ELK :** Loki indexe uniquement les labels (workspace, service, deployment_id), pas le contenu des logs — coût d'indexation et d'infrastructure réduit de 5 à 10x par rapport à Elasticsearch.
- **Intégration Grafana :** datasources Prometheus et Loki nativement supportées, pas de plugin tiers.
- **Pas de vendor lock-in :** OpenMetrics/OTLP standards, migration vers Datadog ou Grafana Cloud possible sans changer les instruments.

## Alternatives considérées

| Alternative | Rejet |
|---|---|
| ELK (Elasticsearch + Logstash + Kibana) | Trop lourd en ressources pour un VPS V1, coût d'indexation élevé |
| Datadog / New Relic | Coût variable difficile à maîtriser, lock-in vendor |
| VictoriaMetrics | Bonne alternative à Prometheus, mais écosystème moins riche pour V1 |

## Conséquences

- `cAdvisor` est déployé dans le compose plateforme pour les métriques containers Docker.
- `postgres_exporter` et `redis_exporter` sont déployés pour PG et Redis.
- Les règles d'alerte Alertmanager couvrent au minimum : API 5xx rate > 0,5 %, Celery queue depth > 50, backup job failure, disk > 80 %.
- Les logs applicatifs sont étiquetés avec `workspace`, `project`, `service`, `deployment_id` pour permettre le filtrage Loki.
- Grafana expose un dashboard par rôle : dashboard Ops (infra), dashboard Business (déploiements, SLOs), dashboard Sécurité (audit events).
- La rétention Prometheus est de 30 jours par défaut ; Loki de 90 jours.
