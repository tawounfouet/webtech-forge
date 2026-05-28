"""
Adapter S3 — backups PostgreSQL et volumes vers bucket S3-compatible.
Implémentation complète dans 20-backups-restore.md.
"""
from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class StorageAdapter:
    def __init__(self, bucket: str, endpoint_url: str | None = None) -> None:
        import boto3

        self.bucket = bucket
        self._s3 = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
        )

    def upload(self, local_path: Path, s3_key: str) -> str:
        logger.info("s3_upload", extra={"key": s3_key, "bucket": self.bucket})
        self._s3.upload_file(str(local_path), self.bucket, s3_key)
        return f"s3://{self.bucket}/{s3_key}"

    def download(self, s3_key: str, local_path: Path) -> None:
        logger.info("s3_download", extra={"key": s3_key, "bucket": self.bucket})
        self._s3.download_file(self.bucket, s3_key, str(local_path))

    def list_objects(self, prefix: str) -> list[str]:
        resp = self._s3.list_objects_v2(Bucket=self.bucket, Prefix=prefix)
        return [obj["Key"] for obj in resp.get("Contents", [])]

    def delete(self, s3_key: str) -> None:
        self._s3.delete_object(Bucket=self.bucket, Key=s3_key)
