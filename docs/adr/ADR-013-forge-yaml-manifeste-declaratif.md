# ADR-013 — Fichier déclaratif forge.yaml par Project

- **Statut :** Accepté
- **Priorité :** P2
- **Date :** 2026-05-27
- **Décideurs :** Équipe WebTech Forge

## Contexte

Les utilisateurs doivent pouvoir décrire leur infrastructure applicative de façon déclarative, versionnée et portable — indépendamment de l'interface console. Cela permet l'automatisation CI/CD, la revue de code des changements infra, et réduit le vendor lock-in.

## Décision

Standardiser un fichier `forge.yaml` par Project, commité dans le dépôt Git du projet.

```yaml
version: "1"

project:
  name: my-app
  workspace: acme

services:
  web:
    type: web
    runtime: dockerfile
    dockerfile: ./Dockerfile
    port: 8000
    replicas: 1
    env:
      NODE_ENV: production
    secrets:
      - DATABASE_URL
      - SECRET_KEY
    domains:
      - my-app.forge.internal
    healthcheck:
      path: /health
      interval: 30s
      timeout: 5s
      retries: 3

  worker:
    type: worker
    runtime: dockerfile
    dockerfile: ./Dockerfile
    command: celery -A app worker -l info
    depends_on: [postgres]

  postgres:
    type: database
    image: postgres:16-alpine
    volumes:
      - postgres-data:/var/lib/postgresql/data
    backup:
      enabled: true
      schedule: "0 2 * * *"
      retention_days: 30

environments:
  staging:
    auto_deploy: true
    branch: main
  production:
    protected: true
    require_approval: true
    min_approvers: 1
```

Le schéma complet est publié sous `forge.yaml.schema.json` (JSON Schema) pour validation en CI et autocomplétion IDE.

## Justification

- **IaC :** align avec les approches Render Blueprints, Terraform et Pulumi — l'infrastructure est code, versionnée, reviewée, diffable.
- **Réduction du lock-in :** conformément au Data Act, un utilisateur peut exporter sa configuration et la migrer sur un autre PaaS ou self-hosted.
- **Anti-dérive :** le `forge.yaml` devient la source de vérité, réconciliée lors de chaque déploiement — détecte les drifts entre ce qui est déclaré et ce qui tourne.
- **CI/CD natif :** `forge deploy --env staging` dans GitHub Actions sans accéder à l'UI.

## Alternatives considérées

| Alternative | Rejet |
|---|---|
| Configuration uniquement via l'UI | Pas de versioning, pas de diff, pas d'automatisation, pas d'auditabilité |
| Terraform provider WebTech Forge | Plus complexe à maintenir, dépend du SDK Terraform, pas natif au workflow dev |
| Docker Compose directement | Pas de concept de Project/Environment/Workspace, pas de notion de rollback ou healthcheck plateforme |

## Conséquences

- Le `GitAdapter` lit et valide le `forge.yaml` en phase Silver du pipeline Medallion.
- Une erreur de validation `forge.yaml` produit un `DeploymentEvent` avec phase `SILVER` et niveau `error` — l'utilisateur sait exactement pourquoi le build a échoué.
- Le JSON Schema est publié et versionné (`v1`, `v2`) pour la rétrocompatibilité.
- La CLI `forge` (V2) consomme ce fichier pour les déploiements programmatiques depuis le terminal ou la CI.
