# ADR-020 — Monitor Hub centralisé (distinct de Grafana)

- **Statut :** Accepté
- **Priorité :** P1
- **Date :** 2026-05-27
- **Décideurs :** Équipe WebTech Forge

## Contexte

Grafana/Prometheus couvrent bien la couche **infra** (CPU, mémoire, latence réseau), mais pas la couche **business** de la plateforme : qui a déployé quoi, quand, avec quel résultat, quelle est la capacité consommée par workspace, quelles alertes Activator ont été déclenchées.

Inspiré du **Monitor Hub de Microsoft Fabric** (vue centralisée des activités de tous les workspaces), WebTech Forge a besoin d'une vue équivalente.

## Décision

Implémenter un **Monitor Hub** en V1 durcie comme :
1. Une **API dédiée** dans le control plane Django (endpoint `/api/v1/monitor/`).
2. Une **section de la console Next.js** (`/monitor`) avec deux niveaux d'accès.

### Données sources

Le Monitor Hub agrège des données déjà présentes dans PostgreSQL :
- `Deployment` + `DeploymentEvent` → historique des déploiements
- `AuditLog` → actions administratives
- `ActivatorExecution` → alertes et actions déclenchées
- `WorkspaceQuota` → consommation de ressources

**Aucune duplication de données** — c'est une vue sur des données existantes.

### Niveaux d'accès

**OrganizationOwner** — vue cross-workspace :
```
GET /api/v1/monitor/activity?org={id}&since=24h&kind=deployment,backup,rollback
GET /api/v1/monitor/capacity?org={id}          → consommation par workspace
GET /api/v1/monitor/alerts?org={id}&status=triggered
GET /api/v1/monitor/degraded?org={id}          → services dégradés ou en échec
```

**WorkspaceAdmin / Operator** — vue workspace :
```
GET /api/v1/monitor/activity?workspace={id}&since=7d
GET /api/v1/monitor/deployments?workspace={id}&status=failed&phase=gold
GET /api/v1/monitor/alerts?workspace={id}&since=48h
```

### Exemple de réponse activity

```json
{
  "events": [
    {
      "type": "deployment",
      "workspace": "acme",
      "service": "web",
      "status": "success",
      "phase": "gold",
      "triggered_by": "thomas@webtech.fr",
      "at": "2026-05-27T14:32:00Z"
    },
    {
      "type": "activator_action",
      "rule": "auto-rollback on error rate",
      "service": "api",
      "action": "rollback",
      "at": "2026-05-27T13:55:00Z"
    }
  ]
}
```

## Justification

- **Fabric Monitor Hub :** démontre la valeur d'une vue d'activité business centralisée pour les équipes ops et les administrateurs de plateforme.
- **Séparation des préoccupations :** Grafana = métriques infra techniques. Monitor Hub = activité business de la plateforme (déploiements, rollbacks, promotions, alertes Activator).
- **Implémentation légère :** pas de nouveau stockage, pas de nouveau composant — uniquement des endpoints DRF qui requêtent des données existantes.
- **RBAC respecté :** les OrganizationOwners voient tout ; les WorkspaceAdmins voient uniquement leur workspace.

## Alternatives considérées

| Alternative | Rejet |
|---|---|
| Grafana uniquement | Grafana est orienté métriques time-series — pas adapté à la vue "qui a déployé quoi" |
| Kibana / ELK | Trop lourd, coût d'indexation élevé (voir ADR-009) |
| Audit log brut dans l'admin Django | Pas d'UX, pas de filtres business, pas accessible aux non-admins |

## Conséquences

- L'app Django `monitor` expose des endpoints en lecture seule, sans état propre.
- La section `/monitor` de la console Next.js est accessible depuis le menu principal de la console.
- Les données du Monitor Hub sont exportables en CSV pour les rapports ops et les audits.
- En V3, le Monitor Hub intègre la vue capacité des `ServerTarget` (nœuds agents) pour les OrganizationOwners.
