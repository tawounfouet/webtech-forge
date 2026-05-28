# ADR-017 — Forge Activator : rules engine event-driven en V2

- **Statut :** Accepté
- **Priorité :** P2
- **Date :** 2026-05-27
- **Décideurs :** Équipe WebTech Forge

## Contexte

Les PaaS modernes ne se contentent pas de déployer des services — ils réagissent aux conditions anormales. Un taux d'erreur élevé, une CPU saturée, des healthchecks qui échouent en cascade : dans l'état actuel des specs V1, ces situations nécessitent une intervention humaine manuelle.

Inspiré du **Microsoft Fabric Activator** (moteur d'automatisation event-driven sur des Objects, Properties, Rules et Actions), WebTech Forge peut intégrer un composant similaire centré sur les déploiements et les services.

## Décision

Implémenter **Forge Activator** en V2 comme un **Celery Beat worker dédié** qui évalue périodiquement des règles configurées par les utilisateurs et déclenche des actions automatiques.

### Modèle conceptuel (inspiré de Fabric Activator)

```
Object      → Service | Deployment | Workspace
Property    → cpu_usage | memory_pct | error_rate | response_time_p99 | deploy_fail_count
Rule        → Condition sur une Property d'un Object (seuil, durée, opérateur)
Action      → auto-rollback | alert_email | alert_slack | webhook | redeploy
```

### Cycle d'évaluation

```python
# Toutes les 60 secondes (configurable)
@app.task
def evaluate_activator_rules():
    for rule in ActivatorRule.objects.filter(enabled=True):
        # Circuit-breaker : max 5 exécutions par heure par règle
        if rule.executions_last_hour() >= rule.circuit_breaker_limit:
            continue
        value = MetricsAdapter.query_prometheus(rule.condition_metric, rule.target_id)
        if rule.evaluate(value):
            execute_action.delay(rule.id, value)
```

### Règles de sécurité

- Les règles de type `ROLLBACK` ou `REDEPLOY` nécessitent le rôle `WorkspaceAdmin` pour être créées.
- Toute exécution est tracée dans `ActivatorExecution` et dans `AuditLog`.
- Un circuit-breaker empêche les boucles : max N exécutions par règle par heure (défaut : 5, configurable).

### Cas d'usage priorisés

| Condition | Action |
|---|---|
| `error_rate > 5%` sur 3 derniers déploiements | Auto-rollback |
| `cpu_usage > 85%` pendant 10 min | Alert email + Slack |
| Container `unhealthy` depuis 2 min | Redeploy automatique |
| `deploy_fail_count >= 3` sur 24h | Alert + désactivation auto-deploy |

## Justification

- **Fabric Activator :** démontre la valeur d'un moteur de règles event-driven pour les plateformes de données et de déploiement.
- **Réduction du toil opérationnel :** les rollbacks manuels après un déploiement cassé représentent du toil répétitif — l'automatisation libère l'équipe ops.
- **SRE Google :** le toil doit être réduit au maximum via l'automatisation ; les alertes sans action automatique associée sont un antipattern.
- **Implémentation sobre :** Celery Beat + `MetricsAdapter` (PromQL) — aucun nouveau composant d'infrastructure.

## Alternatives considérées

| Alternative | Rejet |
|---|---|
| Alertmanager uniquement | Peut notifier mais ne peut pas déclencher un rollback applicatif |
| Outil externe (PagerDuty, OpsGenie) | Dépendance externe, pas d'accès au control plane pour les actions |
| NATS / Kafka pour les events | Surcoût d'infrastructure non justifié |

## Conséquences

- Un worker Celery dédié `activator-worker` est ajouté au `docker-compose.platform.yml` avec une queue dédiée `activator`.
- L'interface UI Activator dans la console Next.js permet de créer/modifier/désactiver les règles et de voir l'historique des exécutions.
- Le `MetricsAdapter` expose une méthode `query_prometheus(metric, target_id)` qui appelle l'API Prometheus PromQL.
- Le SLO Activator est : délai entre condition déclenchée et action exécutée < 120 secondes.
- En V3, les règles peuvent cibler des `ServerTarget` (nœuds) en plus des `Service` et `Deployment`.
