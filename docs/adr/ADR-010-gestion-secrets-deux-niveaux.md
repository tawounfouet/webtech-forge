# ADR-010 — Gestion des secrets en deux niveaux : chiffrage applicatif V1, Vault V2

- **Statut :** Accepté
- **Priorité :** P1
- **Date :** 2026-05-27
- **Décideurs :** Équipe WebTech Forge

## Contexte

WebTech Forge gère deux types de secrets :
1. **Secrets plateforme** : clés Django `SECRET_KEY`, credentials PostgreSQL, credentials Redis, tokens GitHub — secrets du control plane lui-même.
2. **Secrets workloads** : `DATABASE_URL`, `API_KEY`, `STRIPE_SECRET` — secrets des services déployés par les utilisateurs.

La gestion de ces secrets doit être sécurisée dès V1 sans introduire une complexité opérationnelle excessive.

## Décision

### V1 — Chiffrage applicatif + Compose secrets

- Les secrets workloads sont stockés dans PostgreSQL dans un champ **chiffré au repos** via `django-encrypted-fields` (AES-256, clé dérivée de `SECRET_KEY` ou d'une clé dédiée).
- À l'exécution, les secrets sont injectés dans les conteneurs via **Docker Compose secrets** (fichiers montés dans `/run/secrets/`) plutôt qu'en variables d'environnement.
- Les secrets ne sont jamais affichés dans les logs, les réponses API ou les interfaces utilisateur — uniquement leur nom.

```python
class WorkspaceSecret(models.Model):
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE)
    key = models.CharField(max_length=255)
    value = EncryptedTextField()  # chiffré au repos
    created_at = models.DateTimeField(auto_now_add=True)
    last_rotated_at = models.DateTimeField(null=True)
```

### V2 — Vault KV v2

Migration vers **HashiCorp Vault KV v2** pour :
- Versioning des secrets avec historique d'accès.
- Rotation automatique des credentials techniques.
- Audit trail natif (qui a lu quel secret, quand).
- Dynamic secrets pour PostgreSQL (credentials éphémères).

## Justification

- **V1 :** le chiffrage applicatif est suffisant pour un usage interne sans contrainte de conformité audit externe. Complexité opérationnelle faible — Vault nécessite son propre déploiement, son initialisation (unseal), sa HA en V3.
- **V2 :** quand la criticité augmente (clients externes, audit), Vault devient nécessaire pour les dynamic secrets et l'audit trail granulaire.
- **CNIL :** les secrets d'accès aux données sont des données sensibles à chiffrer au repos et à journaliser lors des accès.
- **NIST SP 800-190 :** les variables d'environnement Docker sont lisibles dans `docker inspect` — les secrets montés en fichiers sont plus sûrs.

## Alternatives considérées

| Alternative | Rejet |
|---|---|
| Vault dès V1 | Complexité opérationnelle élevée (unseal, HA, policies) non justifiée en V1 |
| Variables d'environnement Docker non chiffrées | Lisibles via `docker inspect`, exportées dans les logs si `printenv` est exécuté |
| AWS Secrets Manager / GCP Secret Manager | Vendor lock-in, coût, dépendance cloud pour un VPS self-hosted |

## Conséquences

- Les secrets ne sont jamais retournés dans les réponses API — uniquement les clés (noms).
- Une tâche Celery de rotation de secrets est planifiée trimestriellement et documentée dans le runbook.
- La révocation immédiate d'un secret (en cas d'incident) déclenche un re-déploiement automatique de tous les services qui l'utilisent.
- En V2, le passage à Vault implique de migrer les secrets chiffrés depuis PostgreSQL vers Vault KV — une tâche de migration one-shot documentée.
