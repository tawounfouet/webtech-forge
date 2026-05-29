"""
Adapter Git — clone, checkout, validation de la configuration de build.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import subprocess
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)


class GitAdapter:
    # ── Pipeline interface ────────────────────────────────────────────────────

    def clone_and_checkout(self, service) -> tuple[Path, str]:
        """Clone le dépôt primaire du projet et retourne (repo_path, commit_sha)."""
        repo = (
            service.environment.project.repositories.filter(is_primary=True).first()
            or service.environment.project.repositories.first()
        )
        if not repo:
            raise ValueError(f"No repository configured for service {service.slug}")

        tmp_dir = tempfile.mkdtemp(prefix=f"forge-clone-{service.slug}-")
        dest = Path(tmp_dir)

        self.clone(repo.repo_url, dest, branch=repo.default_branch)
        commit_sha = self.get_commit_sha(dest)
        logger.info("cloned", extra={"service": service.slug, "commit": commit_sha[:8]})
        return dest, commit_sha

    def validate_build_config(self, repo_path: Path, service) -> None:
        """Vérifie que le Dockerfile et forge.yaml existent dans le dépôt cloné."""
        dockerfile = repo_path / service.dockerfile_path
        if not dockerfile.exists():
            raise FileNotFoundError(
                f"Dockerfile not found at {service.dockerfile_path} in repository"
            )

        forge_yaml = repo_path / "forge.yaml"
        if not forge_yaml.exists():
            logger.warning("forge_yaml_missing", extra={"service": service.slug})

    def validate_webhook_signature(self, payload: bytes, signature: str, secret: str) -> bool:
        """Vérifie la signature HMAC-SHA256 d'un webhook GitHub."""
        expected = "sha256=" + hmac.new(
            secret.encode(), payload, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature)

    # ── Low-level helpers ─────────────────────────────────────────────────────

    def clone(self, repo_url: str, dest: Path, branch: str = "main") -> None:
        logger.info("git_clone", extra={"branch": branch})
        subprocess.run(
            ["git", "clone", "--depth", "1", "--branch", branch, repo_url, str(dest)],
            check=True,
            capture_output=True,
            text=True,
            timeout=300,
        )

    def get_commit_sha(self, repo_path: Path) -> str:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_path,
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()

    def get_commit_message(self, repo_path: Path) -> str:
        result = subprocess.run(
            ["git", "log", "-1", "--pretty=%s"],
            cwd=repo_path,
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()
