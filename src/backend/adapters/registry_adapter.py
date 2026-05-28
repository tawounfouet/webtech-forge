"""
Adapter Registry Docker local (distribution v2).
Implémentation Harbor dans 16-registre-images.md.
"""
from __future__ import annotations

import logging
import urllib.request
import json

logger = logging.getLogger(__name__)


class RegistryAdapter:
    def __init__(self, host: str) -> None:
        self.host = host.rstrip("/")

    def _get(self, path: str) -> dict:
        url = f"http://{self.host}/v2{path}"
        with urllib.request.urlopen(url, timeout=10) as resp:  # noqa: S310
            return json.loads(resp.read())

    def list_tags(self, repository: str) -> list[str]:
        data = self._get(f"/{repository}/tags/list")
        return data.get("tags") or []

    def delete_tag(self, repository: str, digest: str) -> None:
        import urllib.request

        url = f"http://{self.host}/v2/{repository}/manifests/{digest}"
        req = urllib.request.Request(url, method="DELETE")
        req.add_header("Accept", "application/vnd.docker.distribution.manifest.v2+json")
        with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310
            logger.info("registry_tag_deleted", extra={"repo": repository, "digest": digest, "status": resp.status})

    def get_image_tag(self, workspace_slug: str, service_slug: str, commit_sha: str) -> str:
        return f"{self.host}/{workspace_slug}/{service_slug}:{commit_sha[:12]}"
