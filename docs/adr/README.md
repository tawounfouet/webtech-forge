# Architecture Decision Records — WebTech Forge

Ce dossier contient les 22 ADR (Architecture Decision Records) de WebTech Forge, classés par priorité et domaine.

> **Format :** chaque ADR suit la structure : Contexte → Décision → Justification → Alternatives → Conséquences.
> **Statuts :** `Accepté` | `Proposé` | `Déprécié` | `Remplacé`

---

## P1 — Fondations (V1)

| ADR | Décision | Statut |
|---|---|---|
| [ADR-001](ADR-001-ontologie-organisation-workspace-project.md) | Ontologie `Organization → Workspace → Project → Environment → Service → Deployment` | Accepté |
| [ADR-002](ADR-002-modulith-django-drf.md) | Control plane Django 5.x Modular Monolith + DRF | Accepté |
| [ADR-003](ADR-003-frontend-nextjs-separe.md) | Frontend Next.js séparé du backend | Accepté |
| [ADR-004](ADR-004-celery-redis-deux-instances.md) | Celery + deux instances Redis (broker + channel layer) | Accepté |
| [ADR-005](ADR-005-docker-compose-pas-kubernetes.md) | Docker Engine + Compose en V1/V2, Kubernetes différé | Accepté |
| [ADR-006](ADR-006-traefik-edge-router.md) | Traefik comme edge router principal | Accepté |
| [ADR-007](ADR-007-postgresql-local-v1.md) | PostgreSQL 16 local comme base du control plane en V1 | Accepté |
| [ADR-008](ADR-008-tenancy-workspace-rbac.md) | Tenancy par Workspace avec scoping dur dans l'API et l'audit | Accepté |
| [ADR-009](ADR-009-observabilite-prometheus-grafana-loki.md) | Observabilité via Prometheus + Grafana + Loki + Alertmanager | Accepté |
| [ADR-010](ADR-010-gestion-secrets-deux-niveaux.md) | Secrets : chiffrage applicatif V1, Vault KV v2 en V2 | Accepté |
| [ADR-011](ADR-011-backups-s3-versionnes.md) | Sauvegardes S3-compatible versionnées et immuables | Accepté |
| [ADR-015](ADR-015-isolation-reseau-docker-workspace.md) | Isolation réseau Docker stricte par Workspace (`forge-ws-{slug}`) | Accepté |
| [ADR-016](ADR-016-registre-images-interne.md) | Registre d'images interne dès V1 (local → Harbor en V2) | Accepté |
| [ADR-018](ADR-018-medallion-deployment-pipeline.md) | Pipeline de déploiement Medallion Bronze → Silver → Gold | Accepté |
| [ADR-020](ADR-020-monitor-hub-centralise.md) | Monitor Hub centralisé (distinct de Grafana) | Accepté |
| [ADR-021](ADR-021-service-endorsement-catalogue-templates.md) | Service Endorsement & Catalogue de Templates | Accepté |

## P2 — Fonctionnalités avancées (V2)

| ADR | Décision | Statut |
|---|---|---|
| [ADR-012](ADR-012-agents-multiserveurs-v3.md) | Mode multi-serveur par agents légers plutôt que Kubernetes | Accepté |
| [ADR-013](ADR-013-forge-yaml-manifeste-declaratif.md) | Fichier déclaratif `forge.yaml` par Project | Accepté |
| [ADR-014](ADR-014-cicd-github-actions-oidc.md) | CI/CD via GitHub Actions, OIDC et attestations d'artefacts | Accepté |
| [ADR-017](ADR-017-forge-activator.md) | Forge Activator : rules engine event-driven en V2 | Accepté |
| [ADR-019](ADR-019-deployment-pipelines-gate-approbation.md) | Deployment Pipelines avec gate d'approbation configurable | Accepté |

## P3 — Roadmap V3

| ADR | Décision | Statut |
|---|---|---|
| [ADR-022](ADR-022-forgestore-shortcuts-v3.md) | ForgeStore Shortcuts : services partagés cross-workspace | Proposé |

---

## Principes transverses

Ces ADR forment un ensemble cohérent guidé par dix principes (cf. spec v2) :

1. **État désiré explicite** — ADR-001, ADR-018
2. **Opérations longues découplées** — ADR-004
3. **Runtime standard et portable** — ADR-005, ADR-016
4. **Sécurité par moindre privilège** — ADR-008, ADR-010, ADR-015
5. **Conformité dès la conception** — ADR-008, ADR-010
6. **Sortie de plateforme possible** — ADR-013
7. **Complexité distribuée différée** — ADR-002, ADR-005, ADR-012
8. **Isolation réseau stricte par Workspace** — ADR-015
9. **Pipeline de déploiement auditable** — ADR-018, ADR-019
10. **Automatisation réactive** — ADR-017

---

## Comment ajouter un ADR

1. Créer un fichier `ADR-0NN-titre-court.md` dans ce dossier.
2. Utiliser le template : Contexte → Décision → Justification → Alternatives → Conséquences.
3. Ajouter une ligne dans ce README avec le lien, la décision et le statut.
4. Référencer l'ADR dans la spec principale (`playground/specs/`).
