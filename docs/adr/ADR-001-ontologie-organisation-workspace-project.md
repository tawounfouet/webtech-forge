# ADR-001 — Ontologie Organization → Workspace → Project → Environment → Service → Deployment

- **Statut :** Accepté
- **Priorité :** P1
- **Date :** 2026-05-27
- **Décideurs :** Équipe WebTech Forge

## Contexte

Le modèle de données initial de WebTech Forge était centré sur une entité `Application` qui portait à la fois la notion de produit logique, d'environnement d'exécution et d'unité déployable. Cette confusion rendait la gouvernance, la collaboration multi-utilisateurs et la promotion entre environnements difficiles à implémenter correctement.

Il fallait choisir une hiérarchie d'objets métier qui :
- reflète comment les équipes organisent réellement leur travail,
- permette d'isoler clairement la sécurité, les quotas et l'audit,
- soit cohérente avec les patterns observés sur les PaaS modernes de référence.

## Décision

Adopter la hiérarchie suivante comme ontologie normative du control plane :

```
Organization → Workspace → Project → Environment → Service → Deployment
```

| Niveau | Rôle |
|---|---|
| **Organization** | Entité propriétaire, juridique ou de facturation |
| **Workspace** | Frontière collaborative, RBAC, quotas, secrets, audit |
| **Project** | Produit logique ou application métier |
| **Environment** | Phase d'exécution : dev, staging, preview, production |
| **Service** | Unité technique déployable : web, api, worker, cron, db, cache |
| **Deployment** | Instance immuable et auditable d'une version de Service |

Le `Workspace` est la **frontière de sécurité et de tenancy** principale — pas le `Project`.

## Justification

- **Fabric / Snowflake / Databricks** utilisent le `Workspace` comme conteneur collaboratif d'assets avec isolation des droits.
- **Render** distingue explicitement Workspace, Project, Environment et Service.
- **Vercel** regroupe Deployments et domaines sous le Project.
- **Astronomer** relie explicitement Workspace et Deployment.

Faire porter la tenancy au `Project` plutôt qu'au `Workspace` obligerait à dupliquer la logique de RBAC, de quotas et de secrets à un niveau trop fin. Le `Workspace` comme frontière de sécurité est également aligné avec les recommandations Azure sur le multitenancy et les guides CNIL sur la séparation des habilitations.

## Alternatives considérées

| Alternative | Rejet |
|---|---|
| Centré sur `Application` (v0) | Trop ambigu : Application = produit ou artefact déployé ? Pas de frontière de gouvernance claire |
| `Team → Repo → Environment` | Trop technique, pas de notion de produit logique ni de collaboration cross-repo |
| Flat `Project → Service` sans Workspace | Impossible de gérer multi-équipes, quotas cross-projects et isolation fine |

## Conséquences

- Tous les modèles Django sont scoped par `Workspace` en premier niveau de filtre.
- Les querysets DRF appliquent systématiquement `filter(workspace=request.workspace)`.
- Les tests d'intégration incluent des scénarios multi-tenant (un utilisateur d'un Workspace ne peut pas voir un autre Workspace).
- Les futurs composants (Activator, Monitor Hub, Templates) respectent cette hiérarchie sans exception.
