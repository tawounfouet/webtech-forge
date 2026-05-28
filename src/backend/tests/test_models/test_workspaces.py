import pytest

from tests.factories import (
    OrganizationFactory,
    WorkspaceFactory,
    WorkspaceMemberFactory,
    WorkspaceSecretFactory,
)


@pytest.mark.django_db
class TestWorkspace:
    def test_create(self):
        ws = WorkspaceFactory(slug="my-ws")
        assert ws.pk is not None
        assert ws.slug == "my-ws"

    def test_docker_network_name(self):
        ws = WorkspaceFactory(slug="acme-prod")
        assert ws.docker_network_name == "forge-ws-acme-prod"

    def test_str(self):
        org = OrganizationFactory(slug="acme")
        ws = WorkspaceFactory(organization=org, slug="prod")
        assert str(ws) == "acme/prod"

    def test_unique_slug_per_org(self):
        from django.db import IntegrityError

        org = OrganizationFactory()
        WorkspaceFactory(organization=org, slug="dup")
        with pytest.raises(IntegrityError):
            WorkspaceFactory(organization=org, slug="dup")

    def test_same_slug_different_org(self):
        org1 = OrganizationFactory()
        org2 = OrganizationFactory()
        ws1 = WorkspaceFactory(organization=org1, slug="shared")
        ws2 = WorkspaceFactory(organization=org2, slug="shared")
        assert ws1.pk != ws2.pk


@pytest.mark.django_db
class TestWorkspaceMember:
    def test_unique_membership(self):
        from django.db import IntegrityError

        ws = WorkspaceFactory()
        member = WorkspaceMemberFactory(workspace=ws)
        with pytest.raises(IntegrityError):
            WorkspaceMemberFactory(workspace=ws, user=member.user)

    def test_str_format(self):
        m = WorkspaceMemberFactory(role="developer")
        assert "developer" in str(m)

    def test_role_choices(self):
        from apps.workspaces.models import WorkspaceMember

        for role in WorkspaceMember.Role:
            m = WorkspaceMemberFactory(role=role)
            assert m.role == role


@pytest.mark.django_db
class TestWorkspaceSecret:
    def test_value_is_encrypted_at_rest(self):
        from django.db import connection

        secret = WorkspaceSecretFactory(key="DB_PASSWORD", value="super-secret")
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT value FROM workspaces_workspacesecret WHERE id = %s", [secret.pk]
            )
            raw = cursor.fetchone()[0]
        assert raw != "super-secret", "Secret doit être chiffré en base"

    def test_value_readable_via_orm(self):
        secret = WorkspaceSecretFactory(value="readable-in-orm")
        from apps.workspaces.models import WorkspaceSecret

        refreshed = WorkspaceSecret.objects.get(pk=secret.pk)
        assert refreshed.value == "readable-in-orm"

    def test_unique_key_per_workspace(self):
        from django.db import IntegrityError

        ws = WorkspaceFactory()
        WorkspaceSecretFactory(workspace=ws, key="MY_KEY")
        with pytest.raises(IntegrityError):
            WorkspaceSecretFactory(workspace=ws, key="MY_KEY")
