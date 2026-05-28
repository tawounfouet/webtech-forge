# ADR-022 — ForgeStore Shortcuts : services partagés cross-workspace (V3)

- **Statut :** Proposé
- **Priorité :** P3
- **Date :** 2026-05-27
- **Décideurs :** Équipe WebTech Forge

## Contexte

Dans les organisations avec plusieurs workspaces, certains services d'infrastructure sont mutualisés — un Redis partagé, un PostgreSQL managé commun, un service d'authentification centralisé. Sans mécanisme de partage formel, chaque workspace duplique l'infrastructure, ce qui crée des coûts et des incohérences.

Inspiré des **Shortcuts OneLake de Microsoft Fabric** (référencer des données d'un autre workspace sans les copier), WebTech Forge peut offrir un mécanisme de partage de services entre workspaces.

## Décision

Implémenter **ForgeStore Shortcuts** en V3 comme mécanisme permettant à un workspace d'exposer un service (Redis, PostgreSQL, API interne) à d'autres workspaces, sans répliquer l'infrastructure.

### Contraintes de sécurité

1. Un shortcut est **créé par le workspace source** (`WorkspaceAdmin`) et **accepté par le workspace cible**.
2. La **liaison réseau** est créée via un réseau Docker dédié `forge-link-{src-slug}-{tgt-slug}`.
3. Le workspace cible accède aux **credentials** du service en lecture seule (pas à la configuration interne).
4. Le shortcut est **révocable à tout moment par la source** — la révocation déclenche un re-déploiement des services liés dans le workspace cible.

### Modèle

```python
class ForgeStoreShortcut(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending"    # demande envoyée, non acceptée
        ACTIVE = "active"      # acceptée, réseau créé
        REVOKED = "revoked"    # révoquée par la source

    source_service = models.ForeignKey(
        Service, related_name="shortcuts_offered", on_delete=models.CASCADE
    )
    target_workspace = models.ForeignKey(
        Workspace, related_name="shortcuts_received", on_delete=models.CASCADE
    )
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    link_network_name = models.CharField(max_length=255)  # forge-link-{src}-{tgt}
    accepted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL
    )
    created_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
```

### Endpoints (V3)

```
POST /api/v1/workspaces/{id}/shortcuts           → Proposer un shortcut (source WorkspaceAdmin)
POST /api/v1/shortcuts/{id}/accept               → Accepter (target WorkspaceAdmin)
DELETE /api/v1/shortcuts/{id}                    → Révoquer (source WorkspaceAdmin)
GET  /api/v1/workspaces/{id}/shortcuts/offered   → Shortcuts proposés par ce workspace
GET  /api/v1/workspaces/{id}/shortcuts/received  → Shortcuts reçus par ce workspace
```

### Cas d'usage typiques

| Service partagé | Workspace source | Workspaces bénéficiaires |
|---|---|---|
| Redis partagé (cache/session) | Workspace "Platform" | Tous les workspaces applicatifs |
| PostgreSQL commun | Workspace "DBA" | Workspaces des équipes produit |
| Service d'authentification SSO | Workspace "Auth" | Tous les workspaces |

## Justification

- **Fabric OneLake Shortcuts :** valide le concept de référencer un asset d'un autre workspace sans le dupliquer — réduit les coûts et améliore la cohérence.
- **Réduction de la duplication :** un Redis partagé pour 10 workspaces vs 10 Redis dédiés — 10x moins de ressources et de maintenance.
- **Gouvernance explicite :** le modèle de shortcut avec acceptation et révocation rend les dépendances inter-workspaces visibles et auditables.

## Raison du différé à V3

- **Complexité réseau :** la gestion des réseaux Docker cross-workspace (`forge-link-X-Y`) et leur révocation propre sont des opérations délicates à tester.
- **Sécurité :** le modèle de partage de credentials entre workspaces nécessite une revue de sécurité approfondie.
- **Priorité :** les fonctionnalités V1/V2 apportent plus de valeur que le partage cross-workspace à court terme.

## Alternatives considérées

| Alternative | Rejet |
|---|---|
| Partage de credentials manuellement | Pas de traçabilité, révocation impossible, antipattern sécurité |
| Kubernetes Network Policies (V3 K8s) | Différé avec K8s — si K8s est adopté en V3, réévaluer |

## Conséquences

- En attendant V3, les workspaces qui ont besoin d'un service partagé doivent le dupliquer ou utiliser un service externe à la plateforme.
- Cette ADR doit être réévaluée en V3 en fonction de la maturité du modèle réseau multi-hôtes (ADR-012).
- L'implémentation V3 nécessitera des tests de chaos spécifiques : révocation d'un shortcut pendant qu'un service cible est en cours de déploiement.
