import pytest

from tests.factories import AuditLogFactory


@pytest.mark.django_db
class TestAuditLogViewSet:
    url = "/api/v1/audit/"

    def test_list_scoped_to_workspace(self, auth_client, ws, other_ws):
        mine = AuditLogFactory(workspace=ws)
        theirs = AuditLogFactory(workspace=other_ws)
        resp = auth_client.get(self.url)
        assert resp.status_code == 200
        items = resp.json().get("results", resp.json())
        ids = [a["id"] for a in items]
        assert mine.id in ids
        assert theirs.id not in ids

    def test_filter_by_resource_type(self, auth_client, ws):
        AuditLogFactory(workspace=ws, resource_type="Deployment")
        AuditLogFactory(workspace=ws, resource_type="Service")
        resp = auth_client.get(f"{self.url}?resource_type=Deployment")
        assert resp.status_code == 200
        items = resp.json().get("results", resp.json())
        assert all(a["resource_type"] == "Deployment" for a in items)

    def test_viewer_can_list(self, viewer_client, ws):
        AuditLogFactory(workspace=ws)
        resp = viewer_client.get(self.url)
        assert resp.status_code == 200

    def test_unauthenticated_returns_401(self, api_client):
        resp = api_client.get(self.url)
        assert resp.status_code == 401
