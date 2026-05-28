"""
Adapter Git — clone, checkout, récupération de métadonnées de commit.
"""
from __future__ import annotations

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


class GitAdapter:
    def clone(self, repo_url: str, dest: Path, branch: str = "main") -> None:
        logger.info("git_clone", extra={"url": repo_url, "branch": branch})
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
