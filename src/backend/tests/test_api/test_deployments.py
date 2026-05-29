import pytest
from unittest.mock import patch

from tests.factories import (
    DeploymentFactory,
    EnvironmentFactory,
    ProjectFactory,
    ServiceFactory,
    SuccessfulDeploymentFactory,
)
from apps.deployments.models import Deployment


def _service(ws):
    return ServiceFactory(environment=EnvironmentFactory(project=ProjectFactory(workspace=ws)))


@pytest.mark.django_db
class TestDeploymentList:
    url = "/api/v1/deployments/"

    def test_scoped_to_workspace(self, operator_client, ws, other_ws):
        mine = DeploymentFactory(service=_service(ws))
        theirs = DeploymentFactory(service=_service(other_ws))
        resp = operator_client.get(self.url)
        assert resp.status_code == 200
        items = resp.json().get("results", resp.json())
        ids = [d["id"] for d in items]
        assert mine.id in ids
        assert theirs.id not in ids

    def test_viewer_cannot_list(self, viewer_client):
        resp = viewer_client.get(self.url)
        assert resp.status_code == 403

    def test_unauthenticated_returns_401(self, api_client):
        resp = api_client.get(self.url)
        assert resp.status_code == 401


@pytest.mark.django_db
class TestDeploymentDetail:
    def test_retrieve_includes_events(self, operator_client, ws):
        from tests.factories import DeploymentEventFactory
        d = DeploymentFactory(service=_service(ws))
        DeploymentEventFactory(deployment=d)
        resp = operator_client.get(f"/api/v1/deployments/{d.id}/")
        assert resp.status_code == 200
        assert "events" in resp.json()


@pytest.mark.django_db
class TestDeploymentRollback:
    def test_operator_can_rollback(self, operator_client, ws):
        svc = _service(ws)
        source = SuccessfulDeploymentFactory(service=svc)
        new_dep = DeploymentFactory(service=svc)
        with patch("apps.deployments.services.DeploymentService.rollback") as mock_rb:
            mock_rb.return_value = new_dep
            resp = operator_client.post(f"/api/v1/deployments/{source.id}/rollback/")
        assert resp.status_code == 202
        assert resp.json()["deployment_id"] == new_dep.id

    def test_rollback_returns_400_when_no_success(self, operator_client, ws):
        svc = _service(ws)
        dep = DeploymentFactory(service=svc, status=Deployment.Status.FAILED)
        with patch(
            "apps.deployments.services.DeploymentService.rollback",
            side_effect=ValueError("no successful deployment"),
        ):
            resp = operator_client.post(f"/api/v1/deployments/{dep.id}/rollback/")
        assert resp.status_code == 400

    def test_viewer_cannot_rollback(self, viewer_client, ws):
        dep = DeploymentFactory(service=_service(ws))
        resp = viewer_client.post(f"/api/v1/deployments/{dep.id}/rollback/")
        assert resp.status_code == 403
