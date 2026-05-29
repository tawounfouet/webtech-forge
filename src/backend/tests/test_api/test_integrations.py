import hashlib
import hmac
import json
import pytest

from tests.factories import ProjectRepositoryFactory, ProjectFactory, EnvironmentFactory, ServiceFactory
from apps.services.models import Service


def _gh_headers(payload: bytes, secret: str = "") -> dict:
    sig = "sha256=" + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return {
        "HTTP_X_GITHUB_EVENT": "push",
        "HTTP_X_HUB_SIGNATURE_256": sig,
        "content_type": "application/json",
    }


PUSH_PAYLOAD = json.dumps({
    "ref": "refs/heads/main",
    "repository": {"full_name": "webtech/myrepo"},
}).encode()


@pytest.mark.django_db
class TestGitHubWebhook:
    url = "/api/v1/integrations/github/webhook/"

    def test_non_push_event_ignored(self, api_client):
        resp = api_client.post(
            self.url,
            data=PUSH_PAYLOAD,
            content_type="application/json",
            HTTP_X_GITHUB_EVENT="pull_request",
        )
        assert resp.status_code == 200
        assert resp.json()["detail"] == "ignored"

    def test_push_triggers_deploy(self, api_client, ws, db):
        project = ProjectFactory(workspace=ws)
        repo = ProjectRepositoryFactory(
            project=project,
            repo_url="https://github.com/webtech/myrepo.git",
            webhook_secret="",
        )
        env = EnvironmentFactory(project=project, auto_deploy_branch="main")
        ServiceFactory(environment=env, runtime=Service.Runtime.DOCKERFILE)

        with __import__("unittest.mock", fromlist=["patch"]).patch(
            "apps.deployments.services.DeploymentService.create_deployment"
        ) as mock:
            from tests.factories import DeploymentFactory
            mock.return_value = DeploymentFactory()
            resp = api_client.post(
                self.url,
                data=PUSH_PAYLOAD,
                **_gh_headers(PUSH_PAYLOAD),
            )
        assert resp.status_code == 202
        assert resp.json()["triggered"] >= 1

    def test_invalid_signature_returns_401(self, api_client, db):
        ProjectRepositoryFactory(
            repo_url="https://github.com/webtech/myrepo.git",
            webhook_secret="mysecret",
        )
        resp = api_client.post(
            self.url,
            data=PUSH_PAYLOAD,
            content_type="application/json",
            HTTP_X_GITHUB_EVENT="push",
            HTTP_X_HUB_SIGNATURE_256="sha256=invalidsig",
        )
        assert resp.status_code == 401
