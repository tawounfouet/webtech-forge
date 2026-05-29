from __future__ import annotations

import hashlib
import hmac
import json
import logging

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name="dispatch")
class GitHubWebhookView(View):
    """
    Reçoit les événements push GitHub et déclenche l'auto-deploy
    sur les services dont auto_deploy_branch correspond à la branche pushée.
    """

    def post(self, request: HttpRequest) -> HttpResponse:
        event = request.headers.get("X-GitHub-Event", "")
        if event != "push":
            return JsonResponse({"detail": "ignored"}, status=200)

        repo_name = self._get_repo_name(request)
        if not repo_name:
            return JsonResponse({"detail": "invalid payload"}, status=400)

        repo = self._find_repo(repo_name, request)
        if repo is None:
            return JsonResponse({"detail": "repository not found"}, status=404)

        if not self._verify_signature(request, repo.webhook_secret):
            return JsonResponse({"detail": "invalid signature"}, status=401)

        branch = self._extract_branch(request)
        if not branch:
            return JsonResponse({"detail": "no branch"}, status=400)

        from apps.deployments.services import DeploymentService

        deployments = DeploymentService.trigger_auto_deploy(repo, branch)
        logger.info(
            "auto_deploy_triggered",
            extra={"repo": repo_name, "branch": branch, "deployments": len(deployments)},
        )
        return JsonResponse({"triggered": len(deployments)}, status=202)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _get_repo_name(self, request: HttpRequest) -> str:
        try:
            payload = json.loads(request.body)
            return payload.get("repository", {}).get("full_name", "")
        except (json.JSONDecodeError, AttributeError):
            return ""

    def _find_repo(self, full_name: str, request: HttpRequest):
        from apps.projects.models import ProjectRepository

        return ProjectRepository.objects.filter(repo_url__icontains=full_name).first()

    def _verify_signature(self, request: HttpRequest, secret: str) -> bool:
        if not secret:
            return True
        signature = request.headers.get("X-Hub-Signature-256", "")
        if not signature:
            return False
        expected = "sha256=" + hmac.new(
            secret.encode(), request.body, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature)

    def _extract_branch(self, request: HttpRequest) -> str:
        try:
            payload = json.loads(request.body)
            ref = payload.get("ref", "")
            return ref.removeprefix("refs/heads/")
        except (json.JSONDecodeError, AttributeError):
            return ""
