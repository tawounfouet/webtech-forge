"""
Adapter Registry Docker — build, push, liste et suppression d'images.
"""
from __future__ import annotations

import json
import logging
import subprocess
import urllib.request

from django.conf import settings

logger = logging.getLogger(__name__)


class RegistryAdapter:
    def __init__(self) -> None:
        self.host = getattr(settings, "REGISTRY_HOST", "localhost:5000").rstrip("/")

    # ── Pipeline interface ────────────────────────────────────────────────────

    def build_and_push(
        self,
        workspace_slug: str,
        service_slug: str,
        commit_sha: str,
        context_path,
        dockerfile_path: str = "Dockerfile",
    ) -> str:
        """Build l'image Docker et la pousse dans le registry. Retourne l'image_ref."""
        image_ref = self.get_image_tag(workspace_slug, service_slug, commit_sha)
        logger.info("building_image", extra={"image": image_ref})

        subprocess.run(
            [
                "docker", "build",
                "-t", image_ref,
                "-f", dockerfile_path,
                str(context_path),
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=600,
        )
        subprocess.run(
            ["docker", "push", image_ref],
            check=True,
            capture_output=True,
            text=True,
            timeout=300,
        )
        logger.info("image_pushed", extra={"image": image_ref})
        return image_ref

    def list_all_images(self) -> list[str]:
        """Liste toutes les images présentes dans le registry (format host/repo:tag)."""
        try:
            catalog = self._get("/_catalog")
            images: list[str] = []
            for repo in catalog.get("repositories", []):
                for tag in self.list_tags(repo):
                    images.append(f"{self.host}/{repo}:{tag}")
            return images
        except Exception as exc:
            logger.exception("registry_list_failed", extra={"error": str(exc)})
            return []

    def delete_image(self, image_ref: str) -> None:
        """Supprime une image du registry via son digest."""
        # image_ref format: host/workspace/service:tag
        parts = image_ref.removeprefix(f"{self.host}/").rsplit(":", 1)
        if len(parts) != 2:
            return
        repository, tag = parts
        try:
            manifest = self._get_manifest(repository, tag)
            digest = manifest.get("config", {}).get("digest", "")
            if digest:
                self.delete_tag(repository, digest)
        except Exception as exc:
            logger.warning("image_delete_failed", extra={"image": image_ref, "error": str(exc)})

    # ── Low-level helpers ─────────────────────────────────────────────────────

    def get_image_tag(self, workspace_slug: str, service_slug: str, commit_sha: str) -> str:
        return f"{self.host}/{workspace_slug}/{service_slug}:{commit_sha[:12]}"

    def list_tags(self, repository: str) -> list[str]:
        try:
            data = self._get(f"/{repository}/tags/list")
            return data.get("tags") or []
        except Exception:
            return []

    def delete_tag(self, repository: str, digest: str) -> None:
        url = f"http://{self.host}/v2/{repository}/manifests/{digest}"
        req = urllib.request.Request(url, method="DELETE")
        req.add_header("Accept", "application/vnd.docker.distribution.manifest.v2+json")
        with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310
            logger.info("registry_tag_deleted", extra={"repo": repository, "digest": digest, "status": resp.status})

    def _get(self, path: str) -> dict:
        url = f"http://{self.host}/v2{path}"
        with urllib.request.urlopen(url, timeout=10) as resp:  # noqa: S310
            return json.loads(resp.read())

    def _get_manifest(self, repository: str, tag: str) -> dict:
        url = f"http://{self.host}/v2/{repository}/manifests/{tag}"
        req = urllib.request.Request(url)
        req.add_header("Accept", "application/vnd.docker.distribution.manifest.v2+json")
        with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310
            return json.loads(resp.read())
