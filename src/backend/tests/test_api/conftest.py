"""
Fixtures partagées pour les tests DRF.
Le client APIClient injecte automatiquement le header X-Workspace-Slug
et le token JWT pour l'utilisateur authentifié.
"""
import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from tests.factories import (
    WorkspaceFactory,
    WorkspaceMemberFactory,
    UserFactory,
)
from apps.workspaces.models import WorkspaceMember


@pytest.fixture
def api_client():
    return APIClient()


def _jwt(user):
    return str(RefreshToken.for_user(user).access_token)


@pytest.fixture
def admin_user(db):
    return UserFactory()


@pytest.fixture
def ws(db, admin_user):
    workspace = WorkspaceFactory()
    WorkspaceMemberFactory(workspace=workspace, user=admin_user, role=WorkspaceMember.Role.ADMIN)
    return workspace


@pytest.fixture
def auth_client(api_client, admin_user, ws):
    """APIClient authentifié en tant qu'admin du workspace ws."""
    api_client.credentials(
        HTTP_AUTHORIZATION=f"Bearer {_jwt(admin_user)}",
        HTTP_X_WORKSPACE_SLUG=ws.slug,
    )
    return api_client


@pytest.fixture
def operator_user(db):
    return UserFactory()


@pytest.fixture
def operator_client(api_client, operator_user, ws, db):
    WorkspaceMemberFactory(workspace=ws, user=operator_user, role=WorkspaceMember.Role.OPERATOR)
    api_client.credentials(
        HTTP_AUTHORIZATION=f"Bearer {_jwt(operator_user)}",
        HTTP_X_WORKSPACE_SLUG=ws.slug,
    )
    return api_client


@pytest.fixture
def viewer_user(db):
    return UserFactory()


@pytest.fixture
def viewer_client(api_client, viewer_user, ws, db):
    WorkspaceMemberFactory(workspace=ws, user=viewer_user, role=WorkspaceMember.Role.VIEWER)
    api_client.credentials(
        HTTP_AUTHORIZATION=f"Bearer {_jwt(viewer_user)}",
        HTTP_X_WORKSPACE_SLUG=ws.slug,
    )
    return api_client


@pytest.fixture
def other_ws(db):
    """Workspace isolé — les ressources ici ne doivent jamais fuiter vers ws."""
    return WorkspaceFactory()
