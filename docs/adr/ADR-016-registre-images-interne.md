# ADR-016 — Registre d'images interne dès V1 (local → Harbor en V2)

- **Statut :** Accepté
- **Priorité :** P1
- **Date :** 2026-05-27
- **Décideurs :** Équipe WebTech Forge

## Contexte

Le pipeline de déploiement build des images Docker depuis les dépôts Git des utilisateurs. Sans registre, les images buildées sont uniquement dans le cache local du daemon Docker. Cela crée trois problèmes critiques :
1. **Rollbacks impossibles :** le cache local ne conserve pas les anciennes images indéfiniment.
2. **Pas de déduplication :** des builds identiques rebuil inutilement.
3. **Multi-hôtes impossible :** en V3, les agents sur d'autres nœuds ne peuvent pas pull une image buildée sur le nœud A.

## Décision

Déployer un **registre Docker interne** dès V1 et y pousser chaque image après build.

### V1 — Registry Docker officielle (image `registry:2`)

```yaml
# docker-compose.platform.yml
registry:
  image: registry:2
  ports: ["127.0.0.1:5000:5000"]
  volumes: ["registry-data:/var/lib/registry"]
  environment:
    REGISTRY_STORAGE_DELETE_ENABLED: "true"
    REGISTRY_HTTP_SECRET: "${REGISTRY_SECRET}"
```

**Convention de nommage des tags :**
```
localhost:5000/{workspace_slug}/{service_slug}:{commit_sha7}
localhost:5000/{workspace_slug}/{service_slug}:latest
```

**Politique de rétention :** tâche Celery Beat hebdomadaire conservant les 10 derniers tags par service (configurable par quota Workspace).

### V2 — Harbor ou Gitea Registry

Migration vers Harbor (CNCF) ou Gitea Registry pour :
- Authentification OAuth intégrée avec le control plane.
- Scan de vulnérabilités Trivy intégré.
- Interface UI pour parcourir les images.
- Garbage collection automatique.
- Webhooks sur push d'image.

La migration est transparente — le `RegistryAdapter` abstrait l'URL du registre.

## Justification

- **Rollbacks fiables :** chaque `Deployment.image_ref` pointe vers une image immuable dans le registre (`sha7` tag). Un rollback pull exactement la même image qu'au déploiement initial.
- **Déduplication par layer :** Docker Registry exploite le contenu-addressable storage — les layers partagés entre services ne sont stockés qu'une fois.
- **Préparation V3 :** un registre centralisé est indispensable pour les agents multi-hôtes qui doivent pull les images.
- **Audit :** chaque tag poussé est traçable avec le `commit_sha` dans l'`AuditLog`.

## Alternatives considérées

| Alternative | Rejet |
|---|---|
| Cache local daemon Docker uniquement | Rollbacks fragiles, incompatible V3 multi-hôtes |
| Docker Hub | Dépendance externe, rate limiting, images privées payantes, données hors VPS |
| GitHub Container Registry | Dépendance GitHub, latence pull si hors réseau GitHub |

## Conséquences

- Le `DockerAdapter` inclut un `push()` après chaque build réussi en phase Silver.
- Le `RegistryAdapter` gère les opérations push/pull/list-tags/delete.
- Le monitoring Prometheus surveille l'espace disque du volume `registry-data` — alerte si > 80 %.
- Le runbook `registry-cleanup.md` documente la procédure de garbage collection manuelle.
- En V2, la migration vers Harbor nécessite un re-tagging et push des images existantes — procédure documentée dans le runbook de migration.
