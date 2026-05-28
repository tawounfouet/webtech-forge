# ADR-019 — Deployment Pipelines avec gate d'approbation configurable

- **Statut :** Accepté
- **Priorité :** P2
- **Date :** 2026-05-27
- **Décideurs :** Équipe WebTech Forge

## Contexte

Les utilisateurs déploient souvent manuellement en production après avoir validé en staging — sans diff automatique, sans approbation formelle, sans traçabilité de qui a autorisé la promotion. Ce processus est risqué et non auditable.

Inspiré des **Deployment Pipelines de Microsoft Fabric** (Dev → Test → Prod avec comparaison de configuration), WebTech Forge peut formaliser la promotion entre environments.

## Décision

Implémenter un mécanisme de **promotion formelle** entre environments en V2, avec :
1. **Diff automatique** des configurations avant promotion.
2. **Gate d'approbation** configurable par environment.
3. **Historique des promotions** avec approbateurs.

### Modèle `PromotionPolicy`

```python
class PromotionPolicy(models.Model):
    environment = models.OneToOneField(Environment, on_delete=models.CASCADE)
    require_approval = models.BooleanField(default=False)
    min_approvers = models.PositiveIntegerField(default=1)
    auto_promote_from = models.ForeignKey(
        Environment, null=True, blank=True,
        related_name="auto_promotes_to", on_delete=models.SET_NULL
    )
    notify_channels = models.JSONField(default=list)


class PromotionRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending"
        APPROVED = "approved"
        REJECTED = "rejected"
        CANCELLED = "cancelled"

    source_environment = models.ForeignKey(Environment, related_name="promotions_out", on_delete=models.CASCADE)
    target_environment = models.ForeignKey(Environment, related_name="promotions_in", on_delete=models.CASCADE)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    diff_snapshot = models.JSONField()  # snapshot du diff au moment de la demande
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True)


class PromotionApproval(models.Model):
    request = models.ForeignKey(PromotionRequest, related_name="approvals", on_delete=models.CASCADE)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    approved_at = models.DateTimeField(auto_now_add=True)
    comment = models.TextField(blank=True)
```

### Endpoints

```
POST /api/v1/environments/{id}/promote          → Créer une PromotionRequest
GET  /api/v1/environments/{id}/promotion-diff   → Diff source → target (configs, images, env vars)
POST /api/v1/promotions/{id}/approve            → Approuver (rôle WorkspaceAdmin requis)
POST /api/v1/promotions/{id}/reject             → Rejeter
```

### Contenu du diff automatique

```json
{
  "source": "staging",
  "target": "production",
  "services": [
    {
      "slug": "web",
      "changes": {
        "image_ref": {
          "from": "localhost:5000/acme/web:a1b2c3d",
          "to": "localhost:5000/acme/web:e4f5g6h"
        },
        "env": {
          "added": ["NEW_FEATURE_FLAG"],
          "removed": [],
          "modified": ["APP_VERSION"]
        }
      }
    }
  ]
}
```

## Justification

- **Fabric Deployment Pipelines :** valide le concept de promotion formelle avec comparaison de configuration — adopté largement dans les équipes de données pour éviter les promotions accidentelles.
- **Auditabilité :** la `PromotionRequest` avec `diff_snapshot` et `PromotionApproval` crée une trace complète de qui a promu quoi, quand et pourquoi.
- **Réduction des incidents production :** le diff automatique permet aux approbateurs de voir exactement ce qui va changer — réduit les surprises post-déploiement.
- **CNIL :** la journalisation des actions administratives sensibles (promotion vers production) est recommandée.

## Alternatives considérées

| Alternative | Rejet |
|---|---|
| Promotion manuelle via l'UI sans diff | Pas de visibilité sur ce qui change, pas de traçabilité |
| Promotion automatique sans approbation | Acceptable pour staging, risqué pour production |

## Conséquences

- L'environment `production` a `PromotionPolicy.require_approval = True` et `min_approvers = 1` par défaut.
- L'environment `staging` peut avoir `auto_promote_from = development` si souhaité.
- La notification de demande d'approbation est envoyée aux canaux configurés (`notify_channels`).
- Un `PromotionRequest` expiré sans résolution après 7 jours est automatiquement annulé (Celery Beat task).
- La promotion vers production est tracée dans l'`AuditLog` avec le diff et les approbateurs.
