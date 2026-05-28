# 20 — Backups & Restore

> **ADR de référence :** ADR-011
> **Dépendances :** 06-workers-celery.md, 13-infrastructure-compose.md

---

## Stratégie de backup

| Cible | Outil | Fréquence | Rétention | SLO |
|---|---|---|---|---|
| PostgreSQL control plane | `pg_dump` + gzip | Quotidien 2h00 | 30 jours | 100% succès/jour |
| Volumes de données workloads | tar + gzip | Quotidien 3h00 | 14 jours | 100% succès/jour |
| Images Registry (tags actifs) | Tag SHA7 dans registry | À chaque build | 10 tags/service | — |
| Configuration plateforme | `forge.yaml` exporté | À chaque changement | Illimité (versionné) | — |

---

## Tâches Celery de backup

```python
# apps/deployments/tasks.py
import subprocess
import gzip
import hashlib
from pathlib import Path
from celery import shared_task
from django.conf import settings
from django.utils import timezone


@shared_task(queue="backups", max_retries=3, default_retry_delay=300)
def backup_postgres():
    date_str = timezone.now().strftime("%Y-%m-%dT%H-%M-%S")
    dump_path = Path(f"/tmp/forge-pg-{date_str}.sql")
    gz_path = Path(f"/tmp/forge-pg-{date_str}.sql.gz")

    # Dump
    env = {
        "PGPASSWORD": settings.DATABASES["default"]["PASSWORD"],
        "PATH": "/usr/bin:/bin",
    }
    result = subprocess.run([
        "pg_dump",
        f"--host={settings.DATABASES['default']['HOST']}",
        f"--port={settings.DATABASES['default']['PORT']}",
        f"--username={settings.DATABASES['default']['USER']}",
        "--no-password",
        "--clean",
        "--if-exists",
        "--format=plain",
        settings.DATABASES["default"]["NAME"],
    ], capture_output=True, env=env)

    if result.returncode != 0:
        raise RuntimeError(f"pg_dump failed: {result.stderr.decode()}")

    # Compress
    with open(gz_path, "wb") as gz_file:
        with gzip.GzipFile(fileobj=gz_file) as gz:
            gz.write(result.stdout)

    # Checksum
    checksum = hashlib.sha256(gz_path.read_bytes()).hexdigest()
    s3_key = f"backups/postgres/{date_str}/{checksum[:8]}.sql.gz"

    # Upload
    from adapters.storage_adapter import ObjectStorageAdapter
    storage = ObjectStorageAdapter()
    storage.upload(gz_path, s3_key)
    storage.verify_upload(s3_key, checksum)
    storage.rotate_old(prefix="backups/postgres/", keep_days=30)

    gz_path.unlink()
    _update_backup_metric()
    return {"s3_key": s3_key, "checksum": checksum}


def _update_backup_metric():
    from django.utils import timezone
    import time
    from prometheus_client import Gauge
    last_backup_ts = Gauge("forge_last_backup_timestamp_seconds", "Timestamp of last successful backup")
    last_backup_ts.set(time.time())
```

---

## ObjectStorageAdapter

```python
# adapters/storage_adapter.py
import boto3
import hashlib
from pathlib import Path
from django.conf import settings


class ObjectStorageAdapter:
    def __init__(self):
        self.client = boto3.client(
            "s3",
            endpoint_url=getattr(settings, "S3_ENDPOINT_URL", None),
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        )
        self.bucket = settings.S3_BUCKET

    def upload(self, local_path: Path, s3_key: str) -> None:
        self.client.upload_file(
            str(local_path),
            self.bucket,
            s3_key,
            ExtraArgs={"ServerSideEncryption": "AES256"},
        )

    def verify_upload(self, s3_key: str, expected_checksum: str) -> None:
        response = self.client.get_object(Bucket=self.bucket, Key=s3_key)
        content = response["Body"].read()
        actual_checksum = hashlib.sha256(content).hexdigest()
        if actual_checksum != expected_checksum:
            raise RuntimeError(f"Checksum mismatch for {s3_key}: expected {expected_checksum}, got {actual_checksum}")

    def download(self, s3_key: str, local_path: Path) -> None:
        self.client.download_file(self.bucket, s3_key, str(local_path))

    def list_backups(self, prefix: str) -> list[dict]:
        response = self.client.list_objects_v2(Bucket=self.bucket, Prefix=prefix)
        return sorted(
            response.get("Contents", []),
            key=lambda x: x["LastModified"],
            reverse=True,
        )

    def rotate_old(self, prefix: str, keep_days: int) -> int:
        from datetime import timezone as tz
        from datetime import datetime, timedelta
        cutoff = datetime.now(tz.utc) - timedelta(days=keep_days)
        objects = self.list_backups(prefix)
        deleted = 0
        for obj in objects:
            if obj["LastModified"] < cutoff:
                self.client.delete_object(Bucket=self.bucket, Key=obj["Key"])
                deleted += 1
        return deleted
```

---

## Procédure de Restore

### Restore PostgreSQL

```bash
#!/usr/bin/env bash
# runbooks/scripts/restore-postgres.sh
# Usage: ./restore-postgres.sh <s3_key>

set -euo pipefail

S3_KEY="${1:?Usage: $0 <s3_key>}"
DUMP_PATH="/tmp/restore-$(date +%s).sql.gz"

echo "=== WebTech Forge — PostgreSQL Restore ==="
echo "Downloading: $S3_KEY"

aws s3 cp "s3://${S3_BUCKET}/${S3_KEY}" "$DUMP_PATH" \
  --endpoint-url "${S3_ENDPOINT_URL:-}"

echo "Verifying checksum..."
CHECKSUM=$(sha256sum "$DUMP_PATH" | cut -d' ' -f1)
echo "SHA256: $CHECKSUM"

echo "Stopping API and workers..."
docker compose -f infra/docker-compose.platform.yml stop api celery-worker celery-activator celery-beat

echo "Restoring PostgreSQL..."
export PGPASSWORD="${POSTGRES_PASSWORD}"
gunzip -c "$DUMP_PATH" | psql \
  --host=localhost \
  --port=5432 \
  --username=forge \
  forge

echo "Restarting services..."
docker compose -f infra/docker-compose.platform.yml start api celery-worker celery-activator celery-beat

echo "Running migrations (idempotent)..."
docker compose -f infra/docker-compose.platform.yml exec api python manage.py migrate --no-input

echo "=== Restore complete ==="
rm -f "$DUMP_PATH"
```

---

## Drill mensuel de restauration

```bash
#!/usr/bin/env bash
# runbooks/scripts/restore-drill.sh
# Teste la restauration vers une base de données isolée

set -euo pipefail

DRILL_DB="forge_drill_$(date +%s)"
LATEST_BACKUP=$(aws s3 ls "s3://${S3_BUCKET}/backups/postgres/" --recursive \
  | sort | tail -n 1 | awk '{print $4}')

echo "=== Restore Drill — $(date) ==="
echo "Latest backup: $LATEST_BACKUP"

# Télécharger
aws s3 cp "s3://${S3_BUCKET}/${LATEST_BACKUP}" /tmp/drill.sql.gz

# Créer une base temporaire
export PGPASSWORD="${POSTGRES_PASSWORD}"
psql -h localhost -U forge -c "CREATE DATABASE $DRILL_DB;"

# Restaurer
gunzip -c /tmp/drill.sql.gz | psql -h localhost -U forge "$DRILL_DB"

# Vérifier l'intégrité basique
TABLE_COUNT=$(psql -h localhost -U forge "$DRILL_DB" -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public';")
echo "Tables restored: $TABLE_COUNT"

if [ "$TABLE_COUNT" -lt 10 ]; then
  echo "FAIL: Less than 10 tables restored — restore may be incomplete"
  exit 1
fi

# Cleanup
psql -h localhost -U forge -c "DROP DATABASE $DRILL_DB;"
rm -f /tmp/drill.sql.gz

# Logger le résultat dans AuditLog via API
curl -s -X POST "${FORGE_API_URL}/api/v1/monitor/drill-result" \
  -H "Authorization: Bearer ${FORGE_INTERNAL_TOKEN}" \
  -H "Content-Type: application/json" \
  -d "{\"backup_key\": \"$LATEST_BACKUP\", \"success\": true, \"tables\": $TABLE_COUNT}"

echo "=== Drill complete ✓ ==="
```

Le drill est exécuté mensuellement via Celery Beat et son résultat est tracé dans l'AuditLog.
