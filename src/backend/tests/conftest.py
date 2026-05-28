import pytest
from django.test import RequestFactory

from tests.factories import (
    DeploymentFactory,
    EnvironmentFactory,
    OrganizationFactory,
    ProjectFactory,
    ServiceFactory,
    UserFactory,
    WorkspaceFactory,
    WorkspaceMemberFactory,
)


@pytest.fixture
def rf():
    return RequestFactory()


@pytest.fixture
def user(db):
    return UserFactory()


@pytest.fixture
def superuser(db):
    return UserFactory(is_staff=True, is_superuser=True)


@pytest.fixture
def organization(db):
    return OrganizationFactory()


@pytest.fixture
def workspace(db, organization):
    return WorkspaceFactory(organization=organization)


@pytest.fixture
def member(db, workspace, user):
    return WorkspaceMemberFactory(workspace=workspace, user=user)


@pytest.fixture
def project(db, workspace):
    return ProjectFactory(workspace=workspace)


@pytest.fixture
def environment(db, project):
    return EnvironmentFactory(project=project)


@pytest.fixture
def service(db, environment):
    return ServiceFactory(environment=environment)


@pytest.fixture
def deployment(db, service, user):
    return DeploymentFactory(service=service, triggered_by=user)
