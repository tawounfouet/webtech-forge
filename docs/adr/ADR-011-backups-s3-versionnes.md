# ADR-011 — Sauvegardes S3-compatible versionnées et immuables

- **Statut :** Accepté
- **Priorité :** P1
- **Date :** 2026-05-27
- **Décideurs :** Équipe WebTech Forge

## Contexte

WebTech Forge gère des bases de données PostgreSQL pour le control plane et potentiellement des bases managées pour les utilisateurs. La perte de ces données serait critique. Il faut une stratégie de backup robuste, testée et résiliente aux erreurs humaines et aux ransomwares.

## Décision

Stocker toutes les sauvegardes dans un **bucket S3-compatible avec versioning activé et Object Lock si disponible**.

### Stratégie de backup

| Cible | Fréquence | Outil | Rétention |
|---|---|---|---|
| PostgreSQL control plane | Quotidien à 2h00 | `pg_dump` → gzip → S3 | 30 jours |
| Volumes de données managées | Quotidien | Snapshot + tar → S3 | 14 jours |
| Images Registry | Sur chaque build réussi | Tag `latest` + SHA dans Registry | 10 derniers tags |
| Configuration plateforme | Sur chaque changement | `forge.yaml` exporté → S3 | Illimité (versionné) |

### Pipeline Celery de backup

```python
@app.task
def backup_postgres():
    dump_path = pg_dump(settings.DATABASES["default"])
    checksum = sha256(dump_path)
    s3_key = f"backups/postgres/{date.today()}/{checksum[:8]}.sql.gz"
    upload_to_s3(dump_path, s3_key)
    verify_s3_upload(s3_key, checksum)
    rotate_old_backups(prefix="backups/postgres/", keep_days=30)
```

### Restore drill mensuel

Un test de restauration complet (dump → restore sur environnement isolé → vérification intégrité) est effectué **une fois par mois minimum** et tracé dans l'AuditLog. Seul un backup avec drill réussi est considéré comme une stratégie de reprise réelle.

## Justification

- **Versioning S3 :** protège contre la suppression accidentelle et les corruptions silencieuses.
- **Object Lock :** si disponible (AWS S3, MinIO), rend les backups immuables — protection contre les ransomwares et les suppressions administratives involontaires.
- **Checksum :** garantit que l'objet uploadé est identique à ce qui a été dumpé — détecte les corruptions en transit.
- **PostgreSQL :** rappelle que chaque approche de backup a ses forces et faiblesses, et qu'une procédure non testée ne constitue pas une véritable stratégie de reprise.

## Alternatives considérées

| Alternative | Rejet |
|---|---|
| Backups sur le même VPS | Perte du VPS = perte des backups |
| Replication PostgreSQL seule | Réplique aussi les corruptions logiques et suppressions accidentelles |
| Backup sans vérification | Découverte des corruptions au moment du restore — trop tardif |

## Conséquences

- Le bucket S3 est configuré avec versioning + lifecycle policy (expire versions > 30 jours).
- La tâche Celery Beat de backup est monitored via Prometheus — une alerte Alertmanager se déclenche si le job échoue.
- Le runbook `backup-restore.md` documente précisément la procédure de restore et le script de drill.
- Le SLO de backup est : **100 % de jobs réussis par jour** — toute exception déclenche une alerte immédiate.
