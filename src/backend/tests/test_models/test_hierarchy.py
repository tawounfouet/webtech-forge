"""
Tests de la hiérarchie Org → Workspace → Project → Env → Service → Deployment.
Vérifie que le cascade delete se propage correctement à chaque niveau.
"""
import pytest

from tests.factories import (
    DeploymentFactory,
    EnvironmentFactory,
    OrganizationFactory,
    ProjectFactory,
    ServiceFactory,
    WorkspaceFactory,
)


@pytest.mark.django_db
class TestHierarchyCascade:
    def test_org_delete_cascades_to_workspaces(self):
        from apps.workspaces.models import Workspace

        org = OrganizationFactory()
        WorkspaceFactory(organization=org)
        WorkspaceFactory(organization=org)
        assert Workspace.objects.filter(organization=org).count() == 2
        org.delete()
        assert Workspace.objects.filter(organization=org).count() == 0

    def test_workspace_delete_cascades_to_projects(self):
        from apps.projects.models import Project

        ws = WorkspaceFactory()
        ProjectFactory(workspace=ws)
        ProjectFactory(workspace=ws)
        ws.delete()
        assert Project.objects.count() == 0

    def test_project_delete_cascades_to_environments(self):
        from apps.environments.models import Environment

        project = ProjectFactory()
        EnvironmentFactory(project=project)
        EnvironmentFactory(project=project)
        project.delete()
        assert Environment.objects.count() == 0

    def test_environment_delete_cascades_to_services(self):
        from apps.services.models import Service

        env = EnvironmentFactory()
        ServiceFactory(environment=env)
        ServiceFactory(environment=env)
        env.delete()
        assert Service.objects.count() == 0

    def test_service_delete_cascades_to_deployments(self):
        from apps.deployments.models import Deployment

        service = ServiceFactory()
        DeploymentFactory(service=service)
        DeploymentFactory(service=service)
        service.delete()
        assert Deployment.objects.count() == 0


@pytest.mark.django_db
class TestWorkspaceScopedQuerysets:
    def test_projects_scoped_to_workspace(self):
        from apps.projects.models import Project

        ws1 = WorkspaceFactory()
        ws2 = WorkspaceFactory()
        ProjectFactory(workspace=ws1)
        ProjectFactory(workspace=ws1)
        ProjectFactory(workspace=ws2)

        assert Project.objects.filter(workspace=ws1).count() == 2
        assert Project.objects.filter(workspace=ws2).count() == 1

    def test_services_not_visible_across_workspaces(self):
        from apps.services.models import Service

        ws1 = WorkspaceFactory()
        ws2 = WorkspaceFactory()
        p1 = ProjectFactory(workspace=ws1)
        p2 = ProjectFactory(workspace=ws2)
        e1 = EnvironmentFactory(project=p1)
        e2 = EnvironmentFactory(project=p2)
        ServiceFactory(environment=e1)
        ServiceFactory(environment=e2)

        ws1_services = Service.objects.filter(
            environment__project__workspace=ws1
        )
        ws2_services = Service.objects.filter(
            environment__project__workspace=ws2
        )
        assert ws1_services.count() == 1
        assert ws2_services.count() == 1
        assert ws1_services.first() != ws2_services.first()
