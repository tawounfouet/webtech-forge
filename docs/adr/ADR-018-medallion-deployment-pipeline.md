# ADR-018 — Pipeline de déploiement structuré en phases Medallion (Bronze → Silver → Gold)

- **Statut :** Accepté
- **Priorité :** P1
- **Date :** 2026-05-27
- **Décideurs :** Équipe WebTech Forge

## Contexte

Le pipeline de déploiement actuel (v0) avait une machine à états plate avec des statuts comme `BUILDING`, `RELEASING`, `HEALTHCHECKING`. En cas d'échec, l'utilisateur voyait `FAILED` sans savoir si le problème venait du dépôt Git inaccessible, d'un Dockerfile invalide, d'un secret manquant ou d'un healthcheck raté.

Inspiré de l'**architecture Medallion de Microsoft Fabric** (Bronze → Silver → Gold pour les données), le pipeline de déploiement peut être structuré en trois phases de qualité croissante.

## Décision

Structurer le pipeline Medallion en **trois phases explicites**, chacune avec des statuts, des `DeploymentEvent` et une sémantique d'échec précise :

### Phase Bronze — Artefact

**Objectif :** récupérer et figer l'artefact source immuable.

| Statut | Description |
|---|---|
| `PENDING` | Déploiement créé, en attente d'enqueue |
| `QUEUED` | Tâche Celery enqueue, attente d'un worker |
| `CLONING` | Clone/fetch du dépôt Git |

**Échec Bronze :** dépôt inaccessible, branch inconnue, token Git invalide.

### Phase Silver — Validation + Build

**Objectif :** valider la configuration, résoudre les secrets, builder et pousser l'image.

| Statut | Description |
|---|---|
| `VALIDATING` | Validation `forge.yaml`, Dockerfile, Compose |
| `BUILDING` | Build de l'image Docker (ou pull si image externe) |
| `RELEASING` | Push de l'image vers le registre, génération de la spec runtime |

**Échec Silver :** `forge.yaml` invalide, Dockerfile avec erreur de syntax, secret manquant, build fail, registre inaccessible.

### Phase Gold — Live

**Objectif :** démarrer le service, vérifier sa santé, basculer le trafic.

| Statut | Description |
|---|---|
| `HEALTHCHECKING` | Démarrage du conteneur et évaluation des healthchecks |
| `SUCCESS` | Service sain, trafic basculé, ancien conteneur arrêté |
| `FAILED` | Healthchecks échoués, rollback déclenché |
| `ROLLED_BACK` | Rollback automatique vers le dernier `SUCCESS` réussi |

**Échec Gold :** healthcheck timeout, port non ouvert, crash au démarrage, OOM kill.

### Implémentation

```python
class Deployment(models.Model):
    class Phase(models.TextChoices):
        BRONZE = "bronze"
        SILVER = "silver"
        GOLD = "gold"

    phase = models.CharField(max_length=16, choices=Phase.choices, default=Phase.BRONZE)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.PENDING)
    failure_reason = models.TextField(blank=True)  # message précis de l'échec
```

## Justification

- **UX d'erreur :** l'utilisateur sait exactement où son déploiement a échoué — Bronze = problème de source, Silver = problème de build/config, Gold = problème de runtime.
- **Auditabilité :** chaque `DeploymentEvent` est taggué avec sa phase — les dashboards Monitor Hub peuvent filtrer par phase d'échec.
- **Architecture Medallion Fabric :** démontre qu'une structuration en couches de qualité croissante améliore la gouvernance et la traçabilité des données (ou ici, des déploiements).
- **Rollback ciblé :** un rollback depuis Gold est différent d'un rollback depuis Silver — le rollback Gold réactive le conteneur précédent ; un échec Silver nécessite une correction du code.

## Alternatives considérées

| Alternative | Rejet |
|---|---|
| Machine à états plate | Pas de distinction des causes d'échec, UX dégradée |
| Statuts libres sans phases | Pas de sémantique partagée, monitoring difficile |

## Conséquences

- Le champ `phase` est ajouté au modèle `Deployment` et indexé pour les requêtes Monitor Hub.
- La console Next.js affiche la phase courante avec un indicateur visuel (🟤 Bronze / ⚪ Silver / 🟡 Gold).
- Les alertes Activator peuvent se déclencher sur `phase=GOLD, status=FAILED` (rollback automatique) ou `phase=SILVER, status=FAILED` (notification build cassé).
- Les métriques Prometheus exportent `forge_deployment_failures_total{phase="bronze|silver|gold"}` pour analyser les patterns d'échec.
