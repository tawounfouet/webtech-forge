# ADR-008 — Tenancy par Workspace avec scoping dur dans l'API et l'audit

- **Statut :** Accepté
- **Priorité :** P1
- **Date :** 2026-05-27
- **Décideurs :** Équipe WebTech Forge

## Contexte

WebTech Forge est une plateforme multi-tenant : plusieurs équipes (workspaces) partagent la même infrastructure control plane. Il faut définir quelle entité est la **frontière d'isolation** — et s'assurer que cette frontière est appliquée de façon systématique et non optionnelle.

## Décision

Le **Workspace** est la frontière de tenancy unique. Toutes les ressources opérationnelles (Projects, Environments, Services, Secrets, Audit logs, Quotas, Templates, Activator rules) appartiennent à un Workspace.

### Règles de scoping obligatoires

1. **Tout queryset DRF** filtre par `workspace` avant tout autre filtre :
   ```python
   def get_queryset(self):
       return super().get_queryset().filter(
           environment__project__workspace=self.request.workspace
       )
   ```

2. **Les permissions object-level** vérifient que l'objet appartient au workspace de l'utilisateur :
   ```python
   def has_object_permission(self, request, view, obj):
       return obj.get_workspace() == request.workspace
   ```

3. **Les migrations Django** incluent des contraintes de base de données (`ForeignKey` avec `CASCADE`) pour garantir l'intégrité même en cas de bug applicatif.

### Rôles RBAC

| Rôle | Périmètre | Droits principaux |
|---|---|---|
| `OrganizationOwner` | Organization | Tout, y compris créer/supprimer des Workspaces |
| `WorkspaceAdmin` | Workspace | Tout dans le Workspace, gestion des membres |
| `ProjectMaintainer` | Project | Déploiements, environments, services |
| `Operator` | Workspace | Déployer, rollback, voir les logs |
| `Developer` | Project | Voir, créer des services, trigger des deploys |
| `Viewer` | Workspace | Lecture seule |
| `Auditor` | Workspace | Lecture des audit logs uniquement |

## Justification

- **Azure multitenancy :** insiste sur l'importance de clarifier l'identité, l'autorisation et l'isolation à un niveau stable.
- **CNIL :** recommande les profils d'habilitation, la séparation des rôles, la revue périodique des droits et la journalisation des accès.
- Faire porter la tenancy au `Project` rendrait la gestion des membres, des secrets et des quotas cross-projects impossible sans dupliquer la logique.

## Conséquences

- Les tests d'intégration **doivent** inclure des scénarios de fuite inter-tenant : un utilisateur du Workspace A essaie d'accéder aux ressources du Workspace B → doit retourner 403 ou 404 (jamais 200).
- La revue trimestrielle des rôles Workspace est documentée dans `runbooks/` et tracée dans l'AuditLog.
- Toute nouvelle ressource ajoutée au modèle de données **doit** avoir une relation `ForeignKey` (directe ou indirecte) vers `Workspace`.
- Un middleware Django `WorkspaceMiddleware` résout le workspace courant depuis le JWT ou l'URL et le place dans `request.workspace`.
