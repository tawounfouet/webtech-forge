# ADR-014 — CI/CD via GitHub Actions, OIDC et attestations d'artefacts

- **Statut :** Accepté
- **Priorité :** P2
- **Date :** 2026-05-27
- **Décideurs :** Équipe WebTech Forge

## Contexte

WebTech Forge lui-même (le control plane et la console) doit être buildé, testé et déployé de façon automatisée et sécurisée. Il faut choisir une plateforme CI/CD et une stratégie de sécurisation de la chaîne de delivery.

## Décision

Utiliser **GitHub Actions** pour la CI/CD du projet WebTech Forge, avec :
- **OIDC** pour l'authentification aux services cloud (S3, registry) sans secrets statiques dans CI.
- **Artifact attestations** (SLSA) pour tracer la provenance des images buildées.
- **Trivy** pour le scan de vulnérabilités des images (V2).

### Structure des workflows

```
.github/workflows/
├── ci.yml          # lint, tests, coverage — sur chaque PR
├── build.yml       # build image + push registry + attestation — sur merge main
├── deploy.yml      # déploiement sur VPS via Ansible — sur tag de release
└── scan.yml        # scan Trivy quotidien des images en production (V2)
```

### OIDC sans secrets statiques

```yaml
# build.yml (extrait)
permissions:
  id-token: write
  contents: read
  attestations: write

steps:
  - uses: aws-actions/configure-aws-credentials@v4
    with:
      role-to-assume: arn:aws:iam::ACCOUNT:role/webtech-forge-ci
      aws-region: eu-west-3
```

## Justification

- **GitHub Actions :** plateforme mature, intégrée à GitHub, large marché de runners community.
- **OIDC :** élimine les secrets statiques dans CI (pas de `AWS_ACCESS_KEY_ID` hardcodé). Les credentials sont dérivés dynamiquement du token OIDC du workflow.
- **Attestations SLSA :** améliorent la provenance logicielle — chaque image buildée est signée avec un attestation vérifiable.
- **Ansible pour le déploiement VPS :** agentless, idempotent, adapté aux petits parcs de serveurs.

## Alternatives considérées

| Alternative | Rejet |
|---|---|
| GitLab CI | Pas natif à GitHub, migration du dépôt non souhaitée |
| Jenkins | Maintenance lourde, pas de cloud-native OIDC |
| CircleCI | Coût, pas d'OIDC natif aussi mature |

## Conséquences

- Les secrets de déploiement (SSH key VPS, Ansible vault password) sont stockés dans GitHub Secrets chiffrés — pas dans le code.
- Le workflow `deploy.yml` utilise OIDC pour accéder au bucket S3 de backups et au registry.
- Les images buildées en CI sont taguées `{sha7}` et `latest` — le tag `sha7` est immuable et référencé dans chaque `Deployment`.
- Les attestations sont vérifiables avec `gh attestation verify` — utilisées pour auditer la chaîne de delivery en V2.
