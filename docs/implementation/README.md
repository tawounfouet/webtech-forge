# Documentation d'implémentation — WebTech Forge

Ce dossier contient l'ensemble des guides d'implémentation de la plateforme WebTech Forge, organisés par couche technique et par domaine fonctionnel.

> **Prérequis :** avoir lu la [spec v2](../../specs/2026-05-27_Rapport technique de spécification pour WebTech Forge - v2.md) et les [ADR](../adr/README.md) avant de commencer l'implémentation.

---

## Navigation

### Fondations

| Fichier | Contenu |
|---|---|
| [01-architecture-overview.md](01-architecture-overview.md) | Vue d'ensemble, composants, topologie réseau |
| [02-monorepo-setup.md](02-monorepo-setup.md) | Structure du monorepo, tooling, conventions |
| [03-backend-django.md](03-backend-django.md) | Django apps, custom user model, middleware, settings |
| [04-modeles-donnees.md](04-modeles-donnees.md) | Tous les modèles Django, relations, migrations |

### API & Async

| Fichier | Contenu |
|---|---|
| [05-api-drf.md](05-api-drf.md) | DRF : sérializers, viewsets, permissions, endpoints |
| [06-workers-celery.md](06-workers-celery.md) | Celery : configuration, tasks, Beat scheduling |
| [07-deployment-engine.md](07-deployment-engine.md) | Pipeline Medallion Bronze → Silver → Gold, state machine |
| [21-websocket-auth.md](21-websocket-auth.md) | Channels : auth WebSocket, streaming de logs |

### Composants Fabric-inspirés

| Fichier | Contenu |
|---|---|
| [08-forge-activator.md](08-forge-activator.md) | Activator : rules engine, évaluation, circuit-breaker |
| [09-monitor-hub.md](09-monitor-hub.md) | Monitor Hub : API, agrégation, niveaux d'accès |
| [10-catalogue-templates.md](10-catalogue-templates.md) | Templates certifiés, endorsement workflow |
| [11-deployment-pipelines.md](11-deployment-pipelines.md) | Promotion, diff automatique, gate d'approbation |

### Frontend

| Fichier | Contenu |
|---|---|
| [12-frontend-nextjs.md](12-frontend-nextjs.md) | App Router, API client typé, hooks WebSocket |

### Infrastructure

| Fichier | Contenu |
|---|---|
| [13-infrastructure-compose.md](13-infrastructure-compose.md) | docker-compose.platform.yml complet |
| [14-traefik-routing.md](14-traefik-routing.md) | Labels, TLS, routing preview, blue/green |
| [15-isolation-reseau-docker.md](15-isolation-reseau-docker.md) | Réseaux Docker par workspace, règles d'attachement |
| [16-registre-images.md](16-registre-images.md) | Registry local, tagging, rétention, migration Harbor |

### Opérationnel

| Fichier | Contenu |
|---|---|
| [17-observabilite.md](17-observabilite.md) | Prometheus, Grafana dashboards, Loki labels, alertes |
| [18-securite.md](18-securite.md) | Django security checklist, RBAC, OWASP API |
| [19-gestion-secrets.md](19-gestion-secrets.md) | Champs chiffrés, Compose secrets, Vault migration |
| [20-backups-restore.md](20-backups-restore.md) | Pipeline backup, procédure restore, drill mensuel |
| [22-tests.md](22-tests.md) | Stratégie de test : unit, intégration, multi-tenant, chaos |

### Roadmap

| Fichier | Contenu |
|---|---|
| [23-roadmap.md](23-roadmap.md) | Jalons V1/V2/V3, livrables, critères de sortie |

---

## Ordre de lecture recommandé

**Pour démarrer le projet :**
1. [01-architecture-overview.md](01-architecture-overview.md)
2. [02-monorepo-setup.md](02-monorepo-setup.md)
3. [13-infrastructure-compose.md](13-infrastructure-compose.md)

**Pour implémenter le backend :**
4. [03-backend-django.md](03-backend-django.md)
5. [04-modeles-donnees.md](04-modeles-donnees.md)
6. [05-api-drf.md](05-api-drf.md)
7. [06-workers-celery.md](06-workers-celery.md)

**Pour le deployment engine :**
8. [07-deployment-engine.md](07-deployment-engine.md)
9. [14-traefik-routing.md](14-traefik-routing.md)
10. [15-isolation-reseau-docker.md](15-isolation-reseau-docker.md)
11. [16-registre-images.md](16-registre-images.md)

**Pour les composants avancés (V2) :**
12. [08-forge-activator.md](08-forge-activator.md)
13. [09-monitor-hub.md](09-monitor-hub.md)
14. [10-catalogue-templates.md](10-catalogue-templates.md)
15. [11-deployment-pipelines.md](11-deployment-pipelines.md)

---

## Conventions de ce dossier

- Les fichiers sont numérotés pour indiquer l'ordre logique d'implémentation.
- Les extraits de code sont fonctionnels et directement utilisables comme base de travail.
- Les références aux ADR sont indiquées sous forme `→ ADR-00N`.
- Les dépendances entre fichiers sont indiquées en début de chaque document.
