# ADR-004 — Celery + deux instances Redis pour opérations asynchrones et channel layer

- **Statut :** Accepté
- **Priorité :** P1
- **Date :** 2026-05-27
- **Décideurs :** Équipe WebTech Forge

## Contexte

WebTech Forge nécessite deux types de communication asynchrone distincts :
1. **Opérations longues fiables** : déploiements, rollbacks, backups, healthchecks — nécessitent retry, scheduling, persistance de l'état.
2. **Streaming temps réel éphémère** : logs de déploiement via WebSocket — at-most-once acceptable, faible latence requise.

La question initiale était : une ou deux instances Redis ? Un seul Redis avec plusieurs databases ?

## Décision

Utiliser **Celery** pour toutes les opérations asynchrones critiques, avec **deux instances Redis distinctes** :

| Instance | Rôle | Configuration |
|---|---|---|
| `redis-broker` (RD1) | Broker Celery + result backend | Persistance AOF activée, maxmemory-policy `noeviction` |
| `redis-channels` (RD2) | Django Channels channel layer | Pas de persistance, maxmemory-policy `allkeys-lru` |

```yaml
# docker-compose.platform.yml (extrait)
redis-broker:
  image: redis:7-alpine
  command: redis-server --appendonly yes
  volumes: ["redis-broker-data:/data"]

redis-channels:
  image: redis:7-alpine
  command: redis-server --maxmemory 256mb --maxmemory-policy allkeys-lru
```

## Justification

**Pourquoi deux instances plutôt qu'un Redis avec deux databases ?**
- Les politiques d'éviction (`noeviction` vs `allkeys-lru`) sont incompatibles sur une même instance Redis.
- Une instance saturée par le channel layer (trafic WebSocket) ne doit pas bloquer les tâches Celery critiques.
- La persistance AOF sur le broker garantit qu'un redémarrage ne perd pas les tâches en file d'attente ; cette persistance est inutile et coûteuse pour le channel layer.

**Pourquoi Celery plutôt que RQ ?**
- Celery supporte nativement Canvas (chains, groups, chords) pour orchestrer les phases Medallion du pipeline.
- Celery Beat gère le scheduling des tâches Activator et des backups périodiques.
- RQ est excellent pour des tâches légères mais ne supporte pas les workflows orchestrés nécessaires aux déploiements.

## Alternatives considérées

| Alternative | Rejet |
|---|---|
| RQ à la place de Celery | Insuffisant pour les workflows orchestrés (Medallion pipeline, Activator) |
| Un seul Redis, deux databases | Politiques d'éviction incompatibles, pas d'isolation de fautes |
| Redis Streams à la place de Channels | Plus de complexité pour un use case where at-most-once suffit |
| Kafka / RabbitMQ comme broker | Surcoût opérationnel non justifié à cette échelle |

## Conséquences

- Deux services `redis-broker` et `redis-channels` dans le compose de la plateforme.
- `CELERY_BROKER_URL = "redis://redis-broker:6379/0"`
- `CHANNEL_LAYERS = {"default": {"BACKEND": "channels_redis.core.RedisChannelLayer", "CONFIG": {"hosts": [("redis-channels", 6379)]}}}`
- Le monitoring Prometheus scrape les métriques des deux instances séparément.
- En cas de panne du `redis-channels`, seul le streaming WebSocket est affecté — les déploiements continuent.
