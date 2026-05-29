import pytest
from django.urls import reverse

from tests.factories import WorkspaceFactory, WorkspaceMemberFactory, WorkspaceSecretFactory
from apps.workspaces.models import WorkspaceMember


@pytest.mark.django_db
class TestWorkspaceList:
    url = "/api/v1/workspaces/"

    def test_list_own_workspaces(self, auth_client, ws):
        resp = auth_client.get(self.url)
        assert resp.status_code == 200
        items = resp.json().get("results", resp.json())
        slugs = [w["slug"] for w in items]
        assert ws.slug in slugs

    def test_no_other_workspace_leaked(self, auth_client, other_ws):
        resp = auth_client.get(self.url)
        items = resp.json().get("results", resp.json())
        slugs = [w["slug"] for w in items]
        assert other_ws.slug not in slugs

    def test_unauthenticated_returns_401(self, api_client):
        resp = api_client.get(self.url)
        assert resp.status_code == 401


@pytest.mark.django_db
class TestWorkspaceDetail:
    def test_retrieve(self, auth_client, ws):
        resp = auth_client.get(f"/api/v1/workspaces/{ws.slug}/")
        assert resp.status_code == 200
        assert resp.json()["slug"] == ws.slug


@pytest.mark.django_db
class TestWorkspaceSecrets:
    def test_secret_value_not_exposed(self, auth_client, ws):
        WorkspaceSecretFactory(workspace=ws, key="DB_PASSWORD", value="s3cr3t")
        resp = auth_client.get(f"/api/v1/workspaces/{ws.slug}/secrets/")
        assert resp.status_code == 200
        for secret in resp.json():
            assert "value" not in secret or secret.get("value") is None

    def test_viewer_can_list_secrets(self, viewer_client, ws):
        WorkspaceSecretFactory(workspace=ws)
        resp = viewer_client.get(f"/api/v1/workspaces/{ws.slug}/secrets/")
        assert resp.status_code == 200


@pytest.mark.django_db
class TestWorkspaceMembers:
    def test_admin_can_list_members(self, auth_client, ws):
        resp = auth_client.get(f"/api/v1/workspaces/{ws.slug}/members/")
        assert resp.status_code == 200

    def test_viewer_cannot_delete_member(self, viewer_client, ws, viewer_user):
        member = WorkspaceMemberFactory(workspace=ws)
        resp = viewer_client.delete(f"/api/v1/workspaces/{ws.slug}/members/{member.id}/")
        assert resp.status_code == 403
