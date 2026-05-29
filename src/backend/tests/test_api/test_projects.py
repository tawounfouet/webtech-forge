import pytest

from tests.factories import ProjectFactory, ProjectRepositoryFactory


@pytest.mark.django_db
class TestProjectViewSet:
    url = "/api/v1/projects/"

    def test_list_scoped_to_workspace(self, auth_client, ws, other_ws):
        mine = ProjectFactory(workspace=ws)
        theirs = ProjectFactory(workspace=other_ws)
        resp = auth_client.get(self.url)
        assert resp.status_code == 200
        items = resp.json().get("results", resp.json())
        slugs = [p["slug"] for p in items]
        assert mine.slug in slugs
        assert theirs.slug not in slugs

    def test_create_project(self, auth_client, ws):
        resp = auth_client.post(self.url, {"name": "New Project", "slug": "new-project"})
        assert resp.status_code == 201
        assert resp.json()["slug"] == "new-project"

    def test_retrieve(self, auth_client, ws):
        project = ProjectFactory(workspace=ws)
        resp = auth_client.get(f"{self.url}{project.slug}/")
        assert resp.status_code == 200

    def test_delete(self, auth_client, ws):
        project = ProjectFactory(workspace=ws)
        resp = auth_client.delete(f"{self.url}{project.slug}/")
        assert resp.status_code == 204

    def test_unauthenticated_returns_401(self, api_client):
        resp = api_client.get(self.url)
        assert resp.status_code == 401


@pytest.mark.django_db
class TestProjectRepositories:
    def test_list_repositories(self, auth_client, ws):
        from tests.factories import ProjectFactory
        project = ProjectFactory(workspace=ws)
        ProjectRepositoryFactory(project=project)
        resp = auth_client.get(f"/api/v1/projects/{project.slug}/repositories/")
        assert resp.status_code == 200
        assert len(resp.json()) == 1
