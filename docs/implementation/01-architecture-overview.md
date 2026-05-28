# 01 — Architecture Overview

> **ADR de référence :** ADR-001, ADR-002, ADR-005, ADR-015
> **Dépendances :** aucune — point d'entrée

---

## Vue d'ensemble

WebTech Forge est un **PaaS interne mono-serveur** (V1) constitué de six couches distinctes :

| Couche | Responsabilité | Composants |
|---|---|---|
| **Control Plane** | État désiré, RBAC, orchestration d'intentions | Django 5.x + DRF + PostgreSQL |
| **Async Plane** | Opérations longues, scheduling, Activator | Celery + Redis Broker |
| **Realtime Plane** | Streaming logs, événements UI | Django Channels + Redis Channel Layer |
| **Data Plane** | Exécution des workloads | Docker Engine + Compose |
| **Edge Plane** | Routing HTTP/S, TLS, discovery | Traefik |
| **Observability Plane** | Métriques, logs, alertes | Prometheus + Loki + Grafana + Alertmanager |

---

## Topologie réseau Docker

```
┌─────────────────────────────────────────────────────────────┐
│  forge-platform (réseau interne — jamais exposé)            │
│  Django · PostgreSQL · Redis-broker · Redis-channels        │
│  Celery-workers · Celery-activator · Registry               │
└──────────────────────────┬──────────────────────────────────┘
                           │ API HTTP seulement
┌──────────────────────────▼──────────────────────────────────┐
│  forge-edge (réseau Traefik — ports 80/443 exposés)         │
│  Traefik · Console Next.js                                  │
└──────────┬───────────────────────────┬───────────────────────┘
           │                           │
┌──────────▼──────────┐   ┌────────────▼─────────────┐
│  forge-ws-acme      │   │  forge-ws-beta            │
│  (Workspace "acme") │   │  (Workspace "beta")       │
│  web · api · db     │   │  web · worker · cache     │
└─────────────────────┘   └──────────────────────────┘
```

**Règles strictes :**
- Aucun conteneur applicatif n'est attaché à `forge-platform`.
- Traefik accède au socket Docker en lecture seule depuis `forge-edge`.
- Les services exposés publiquement sont attachés à `forge-ws-{slug}` **et** `forge-edge`.
- Les services internes (workers, db) sont attachés à `forge-ws-{slug}` **uniquement**.

---

## Flux de déploiement simplifié

```
Utilisateur → POST /api/v1/services/{id}/deploy
    ↓
Django : validation RBAC + protection environment
    ↓
Django : création Deployment (phase=BRONZE, status=PENDING)
    ↓
Celery : enqueue tâche deployment_task.delay(deployment_id)
    ↓
Worker : phase BRONZE → clone repo, resolve SHA
    ↓
Worker : phase SILVER → validate forge.yaml, build image, push registry
    ↓
Worker : phase GOLD → create container, healthcheck, switch Traefik
    ↓
Worker : SUCCESS → release lock, emit events, Activator eval
```

---

## Ports et services internes

| Service | Port interne | Exposé ? |
|---|---|---|
| Django ASGI (Daphne/Uvicorn) | 8000 | Via Traefik uniquement |
| Console Next.js | 3000 | Via Traefik uniquement |
| PostgreSQL | 5432 | Non — `forge-platform` uniquement |
| Redis Broker | 6379 | Non — `forge-platform` uniquement |
| Redis Channels | 6380 | Non — `forge-platform` uniquement |
| Registry Docker local | 5000 | `127.0.0.1:5000` (localhost VPS uniquement) |
| Prometheus | 9090 | Non (ou VPN/accès restreint) |
| Grafana | 3001 | Via Traefik, accès restreint |
| Traefik Dashboard | 8080 | Non (ou VPN/accès restreint) |

---

## Décisions architecturales clés

1. **Modulith avant microservices** → ADR-002 : Django apps par domaine, pas de services séparés.
2. **Docker Compose avant Kubernetes** → ADR-005 : runtime simple, progressif.
3. **Isolation réseau par workspace** → ADR-015 : `forge-ws-{slug}` obligatoire.
4. **Registre d'images dès V1** → ADR-016 : rollbacks fiables, préparation V3.
5. **Deux Redis distincts** → ADR-004 : broker (persistant) vs channel layer (éphémère).

---

## Schéma de composants V1

```
                    ┌───────────────┐
                    │  Console      │
                    │  Next.js      │
                    └───────┬───────┘
                            │ REST + WebSocket
                    ┌───────▼───────┐
                    │  Django 5.x   │
                    │  + DRF        │◄──── ASGI (Daphne)
                    └──┬────┬───┬───┘
                       │    │   │
              ┌────────▼┐  ┌▼──────┐  ┌▼────────┐
              │PostgreSQL│  │Redis  │  │Redis    │
              │(state)   │  │Broker │  │Channels │
              └──────────┘  └───┬───┘  └────┬────┘
                                │            │
                         ┌──────▼──────┐     │
                         │Celery       │     │
                         │Workers      │     │
                         │+ Activator  │     │
                         └──┬──────────┘     │
                            │                │
                    ┌───────▼───────┐  ┌─────▼──────┐
                    │Docker Engine  │  │WS Consumers │
                    │+ Compose      │  │(log stream) │
                    └──┬────────────┘  └─────────────┘
                       │
              ┌────────▼────────┐
              │Registry local   │
              │Traefik          │
              │Prometheus/Loki  │
              └─────────────────┘
```
