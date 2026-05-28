# 23 — Roadmap V1 / V2 / V3

> **ADR de référence :** tous les ADR
> **Dépendances :** toutes les implémentations

---

## Vue d'ensemble

| Jalon | Périmètre | Effort estimé | Critère de sortie principal |
|---|---|---|---|
| **V1** | PaaS mono-serveur opérationnel | ~3 mois (1-2 devs) | Déploiement end-to-end fonctionnel en production |
| **V2** | Observabilité avancée, sécurité renforcée, Harbor | ~2 mois | SLO mesurés, audit certifié, Harbor en prod |
| **V3** | Multi-serveur, agents IA, ForgeStore | ~4 mois | Workspaces distribués, catalogue public |

---

## V1 — PaaS Mono-Serveur Opérationnel

### Objectif

Un opérateur WebTech Solutions peut déployer un service web depuis un dépôt Git jusqu'à un conteneur actif derrière Traefik, avec logs en temps réel et rollback automatique, sur un seul serveur Linux.

### Livrables

| # | Livrable | Fichier de référence |
|---|---|---|
| 1.1 | Modèles de données complets avec migrations | `04-modeles-donnees.md` |
| 1.2 | API DRF — tous les endpoints CRUD | `05-api-drf.md` |
| 1.3 | Moteur de déploiement Medallion (Bronze → Silver → Gold) | `06-workers-celery.md`, `07-deployment-engine.md` |
| 1.4 | Isolation réseau Docker par workspace | `15-isolation-reseau-docker.md` |
| 1.5 | Streaming WebSocket des logs de déploiement | `21-websocket-auth.md` |
| 1.6 | Rollback automatique sur healthcheck failure | `07-deployment-engine.md` |
| 1.7 | Multi-tenant RBAC (Owner / Admin / Developer / Viewer) | `05-api-drf.md` |
| 1.8 | Gestion des secrets chiffrés (AES-256) | `19-gestion-secrets.md` |
| 1.9 | Backups PostgreSQL + volumes vers S3 | `20-backups-restore.md` |
| 1.10 | Stack d'observabilité (Prometheus + Grafana + Loki) | `17-observabilite.md` |
| 1.11 | Console Next.js — golden path déploiement | `12-frontend-nextjs.md` |
| 1.12 | Infrastructure Docker Compose complète | `13-infrastructure-compose.md` |
| 1.13 | CI/CD GitHub Actions (lint + tests + image) | `22-tests.md` |
| 1.14 | forge.yaml — manifeste déclaratif validé | `ADR-013` |

### Critères de sortie V1

- [ ] Déploiement d'un service Django "Hello World" de zéro en moins de 5 minutes
- [ ] Isolation vérifiée : user B ne voit pas les ressources du workspace A (tests de permissions verts)
- [ ] Rollback automatique déclenché et tracé sur healthcheck failure simulée
- [ ] Backup PostgreSQL exécuté, vérifié par checksum, restore drill réussi sur base isolée
- [ ] Couverture tests ≥ 80% sur `apps/` (unit + integration)
- [ ] Zéro secret en clair dans les logs (redaction validée)
- [ ] Tous les endpoints protégés par authentification JWT (aucun endpoint public non intentionnel)

### Planning indicatif V1

```
Semaine 1-2  : Modèles + migrations + factories + tests de base
Semaine 3-4  : API DRF (CRUD + permissions) + middleware workspace
Semaine 5-6  : Moteur de déploiement (Bronze→Silver→Gold) + DockerAdapter
Semaine 7    : Isolation réseau + Traefik blue/green
Semaine 8    : WebSocket + streaming logs + rollback
Semaine 9    : Secrets + backups + restore drill
Semaine 10   : Observabilité (Prometheus + Grafana + Loki)
Semaine 11   : Console Next.js (golden path)
Semaine 12   : Tests E2E + hardening sécurité + documentation opérationnelle
```

---

## V2 — Observabilité Avancée & Sécurité Renforcée

### Objectif

Industrialiser la plateforme pour une utilisation multi-client : Harbor comme registry de production, Forge Activator opérationnel, Monitor Hub, Deployment Pipelines avec gates d'approbation, Vault pour les secrets, scan Trivy des images.

### Livrables

| # | Livrable | Fichier de référence |
|---|---|---|
| 2.1 | Forge Activator complet (Rules + circuit-breaker + rollback auto) | `08-forge-activator.md` |
| 2.2 | Monitor Hub — ActivityView + CapacityView + AlertsView | `09-monitor-hub.md` |
| 2.3 | Deployment Pipelines — PromotionRequest + gates d'approbation | `11-deployment-pipelines.md` |
| 2.4 | Catalogue de templates + endorsement (experimental/promoted/certified) | `10-catalogue-templates.md` |
| 2.5 | Harbor comme registry de production (migration depuis registry local) | `16-registre-images.md` |
| 2.6 | Migration des secrets vers HashiCorp Vault KV v2 | `19-gestion-secrets.md` |
| 2.7 | Scan Trivy des images avant déploiement | `18-securite.md` |
| 2.8 | MFA TOTP obligatoire pour les rôles Admin/Owner | `18-securite.md` |
| 2.9 | Alertes Prometheus + Alertmanager (PagerDuty/Slack) | `17-observabilite.md` |
| 2.10 | Attestations SLSA pour les images CI | `ADR-014` |
| 2.11 | Restore drill mensuel automatisé via Celery Beat | `20-backups-restore.md` |
| 2.12 | Preview environments (Traefik labels dynamiques) | `14-traefik-routing.md` |

### Critères de sortie V2

- [ ] Forge Activator déclenche un rollback automatique mesuré en < 60s après dépassement de seuil
- [ ] Monitor Hub affiche l'activité cross-workspace pour les superusers
- [ ] Promotion Staging→Production bloquée sans approbation quand `required_approvals > 0`
- [ ] Images Docker scannées par Trivy, déploiement bloqué si CVE critique
- [ ] Secrets migrés dans Vault, aucun secret en clair dans PostgreSQL
- [ ] MFA TOTP activé et testé pour un compte Admin
- [ ] Alertmanager envoie une alerte Slack sur `forge_deployment_failure_rate > 0.1`
- [ ] Restore drill automatisé exécuté et loggé dans AuditLog sans intervention manuelle

### Planning indicatif V2

```
Semaine 1-2  : Forge Activator (models + tasks + circuit-breaker)
Semaine 3    : Monitor Hub (ActivityView + CapacityView)
Semaine 4-5  : Deployment Pipelines (PromotionRequest + approbation)
Semaine 6    : Catalogue templates + endorsement
Semaine 7    : Harbor — migration registry + cleanup tasks
Semaine 8    : Vault — migration secrets + VaultAdapter
Semaine 9    : Trivy scan + MFA TOTP
Semaine 10   : Alertmanager + Restore drill automatisé
```

---

## V3 — Multi-Serveur, Agents IA & ForgeStore

### Objectif

Passer à une architecture distribuée capable de gérer plusieurs serveurs (régions), introduire des agents IA pour l'assistance aux déploiements, et ouvrir un catalogue de services partagés (ForgeStore) entre workspaces.

### Livrables

| # | Livrable | Fichier de référence |
|---|---|---|
| 3.1 | ForgeStore — partage de services cross-workspace (ShortcutBinding) | `ADR-022` |
| 3.2 | Agents IA multi-serveurs (diagnostic, suggestion de rollback) | `ADR-012` |
| 3.3 | Multi-cluster Docker (région_hint + orchestration) | `ADR-005`, `ADR-015` |
| 3.4 | RBAC granulaire par environment (pas seulement par workspace) | `ADR-008` |
| 3.5 | Forge CLI (client terminal pour `forge deploy`, `forge logs`) | — |
| 3.6 | Quotas dynamiques par workspace (CPU, RAM, stockage) | `04-modeles-donnees.md` |
| 3.7 | Notifications webhook sortantes (Slack, Teams, PagerDuty natif) | `ADR-017` |
| 3.8 | Interface de gestion du catalogue public (ForgeStore UI) | — |

### Critères de sortie V3

- [ ] Un service déployé sur le serveur A est accessible comme shortcut depuis le workspace B (serveur B)
- [ ] Un agent IA génère une suggestion de rollback contextualisée dans < 30s
- [ ] `forge deploy --service my-api --env production` fonctionne depuis la CLI
- [ ] Quotas appliqués : déploiement rejeté si quota CPU dépassé
- [ ] ForgeStore affiche les services publics avec leur niveau d'endorsement

### Planning indicatif V3

```
Semaine 1-3  : Architecture multi-cluster + région_hint
Semaine 4-6  : ForgeStore (ShortcutBinding + UI catalogue)
Semaine 7-9  : Agents IA (LangChain/Claude API + ActivatorRule IA)
Semaine 10   : Forge CLI
Semaine 11-12: Quotas dynamiques + notifications webhook
Semaine 13-16: Tests E2E distribués + documentation
```

---

## Métriques de succès globales

| Métrique | Cible V1 | Cible V2 | Cible V3 |
|---|---|---|---|
| Temps de déploiement (service simple) | < 5 min | < 3 min | < 2 min |
| Disponibilité plateforme | 99% | 99.5% | 99.9% |
| MTTR (rollback automatique) | < 5 min | < 2 min | < 1 min |
| Couverture tests | ≥ 80% | ≥ 85% | ≥ 90% |
| Temps de restore PostgreSQL | < 30 min | < 15 min | < 10 min |
| Workspaces supportés | ≤ 10 | ≤ 50 | illimité |

---

## Dépendances critiques

```
V1 BLOQUE sur :
  └─ Serveur Linux dédié (min. 8 CPU, 16 GB RAM, 200 GB SSD)
  └─ Bucket S3-compatible (ex. Scaleway Object Storage)
  └─ Domaine DNS + certificat wildcard (Let's Encrypt via Traefik)
  └─ Accès Docker Hub ou registry externe pour les images de base

V2 AJOUTE :
  └─ License Harbor (gratuit, open-source) ou registry managé
  └─ Instance HashiCorp Vault (ou HCP Vault Dedicated)
  └─ PagerDuty/Slack webhook pour les alertes

V3 AJOUTE :
  └─ Accès API Claude (Anthropic) ou modèle local pour les agents IA
  └─ Deuxième serveur minimum pour le multi-cluster
  └─ CDN ou load balancer externe (Cloudflare ou HAProxy)
```

---

## Risques et mitigations

| Risque | Probabilité | Impact | Mitigation |
|---|---|---|---|
| Docker socket = vecteur d'attaque | Moyen | Critique | `cap_drop: ALL`, `no-new-privileges`, audit log de chaque appel |
| Perte de données workspace (volume supprimé) | Faible | Critique | Backup volumes quotidiens + restore drill mensuel |
| Dérive de configuration entre serveurs (V3) | Élevé | Moyen | `forge.yaml` comme source de vérité + diff automatique |
| Accumulation d'images orphelines (registry) | Élevé | Faible | `registry_cleanup` Celery task hebdomadaire |
| Surcharge Redis broker (pic de déploiements) | Moyen | Moyen | `noeviction` policy + monitoring `redis_connected_clients` |
| Fuite de secret via logs | Moyen | Critique | `redact_sensitive()` sur tous les `DeploymentEvent.message` |
