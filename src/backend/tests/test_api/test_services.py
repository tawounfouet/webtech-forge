import pytest
from unittest.mock import patch

from tests.factories import (
    EnvironmentFactory,
    ProjectFactory,
    ServiceFactory,
    DeploymentFactory,
)
from apps.deployments.models import Deployment


@pytest.mark.django_db
class TestServiceViewSet:
    url = "/api/v1/services/"

    def _env(self, ws):
        return EnvironmentFactory(project=ProjectFactory(workspace=ws))

    def test_list_scoped_to_workspace(self, auth_client, ws, other_ws):
        mine = ServiceFactory(environment=self._env(ws))
        theirs = ServiceFactory(environment=self._env(other_ws))
        resp = auth_client.get(self.url)
        assert resp.status_code == 200
        items = resp.json().get("results", resp.json())
        slugs = [s["slug"] for s in items]
        assert mine.slug in slugs
        assert theirs.slug not in slugs

    def test_filter_by_environment(self, auth_client, ws):
        env_a = self._env(ws)
        env_b = self._env(ws)
        ServiceFactory(environment=env_a)
        ServiceFactory(environment=env_b)
        resp = auth_client.get(f"{self.url}?environment={env_a.id}")
        assert resp.status_code == 200
        items = resp.json().get("results", resp.json())
        assert all(s["environment"] == env_a.id for s in items)

    def test_create_service(self, auth_client, ws):
        env = self._env(ws)
        payload = {
            "environment": env.id,
            "name": "My API",
            "slug": "my-api",
            "service_type": "api",
            "runtime": "dockerfile",
            "internal_port": 8080,
        }
        resp = auth_client.post(self.url, payload)
        assert resp.status_code == 201

    def test_viewer_cannot_create(self, viewer_client):
        resp = viewer_client.post(self.url, {})
        assert resp.status_code == 403

    def test_unauthenticated_returns_401(self, api_client):
        resp = api_client.get(self.url)
        assert resp.status_code == 401


@pytest.mark.django_db
class TestServiceDeploy:
    def _service(self, ws):
        env = EnvironmentFactory(project=ProjectFactory(workspace=ws))
        return ServiceFactory(environment=env)

    def test_operator_can_trigger_deploy(self, operator_client, ws):
        svc = self._service(ws)
        with patch("apps.deployments.services.DeploymentService.create_deployment") as mock_create:
            mock_create.return_value = DeploymentFactory(service=svc)
            resp = operator_client.post(f"/api/v1/services/{svc.id}/deploy/")
        assert resp.status_code == 202
        assert "deployment_id" in resp.json()

    def test_viewer_cannot_deploy(self, viewer_client, ws):
        svc = self._service(ws)
        resp = viewer_client.post(f"/api/v1/services/{svc.id}/deploy/")
        assert resp.status_code == 403

    def test_deploy_conflict_when_locked(self, operator_client, ws):
        from django.core.exceptions import ValidationError
        svc = self._service(ws)
        with patch(
            "apps.deployments.services.DeploymentService.create_deployment",
            side_effect=ValidationError("already locked"),
        ):
            resp = operator_client.post(f"/api/v1/services/{svc.id}/deploy/")
        assert resp.status_code == 409


@pytest.mark.django_db
class TestServiceDeploymentsList:
    def test_returns_last_20(self, auth_client, ws):
        env = EnvironmentFactory(project=ProjectFactory(workspace=ws))
        svc = ServiceFactory(environment=env)
        for _ in range(5):
            DeploymentFactory(service=svc, status=Deployment.Status.SUCCESS)
        resp = auth_client.get(f"/api/v1/services/{svc.id}/deployments/")
        assert resp.status_code == 200
        assert len(resp.json()) == 5
