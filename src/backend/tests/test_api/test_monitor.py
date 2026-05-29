import pytest

from tests.factories import MonitorSnapshotFactory


@pytest.mark.django_db
class TestMonitorSnapshotViewSet:
    url = "/api/v1/monitor/"

    def test_list_scoped_to_workspace(self, auth_client, ws, other_ws):
        mine = MonitorSnapshotFactory(workspace=ws)
        theirs = MonitorSnapshotFactory(workspace=other_ws)
        resp = auth_client.get(self.url)
        assert resp.status_code == 200
        items = resp.json().get("results", resp.json())
        ids = [s["id"] for s in items]
        assert mine.id in ids
        assert theirs.id not in ids

    def test_viewer_can_list(self, viewer_client, ws):
        MonitorSnapshotFactory(workspace=ws)
        resp = viewer_client.get(self.url)
        assert resp.status_code == 200

    def test_unauthenticated_returns_401(self, api_client):
        resp = api_client.get(self.url)
        assert resp.status_code == 401
