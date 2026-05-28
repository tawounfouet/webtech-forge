# 22 — Stratégie de test

> **ADR de référence :** ADR-008, ADR-015, ADR-018
> **Dépendances :** toutes les implémentations

---

## Niveaux de test

| Niveau | Outil | Scope | Vitesse | Environnement |
|---|---|---|---|---|
| **Unit** | pytest + pytest-django | Models, sérializers, services métier, Activator | < 1s/test | Sans DB ni Docker |
| **Integration** | pytest + TestContainers | Endpoints DRF, tâches Celery, Channels | 1-10s/test | PostgreSQL réel |
| **Permissions** | pytest-django | Scoping multi-tenant, RBAC | < 5s/test | PostgreSQL réel |
| **Network isolation** | pytest + docker-py | Isolation réseau Docker entre workspaces | ~30s | Docker-in-Docker |
| **E2E** | Playwright | Golden path utilisateur complet | 30-120s | Stack complète |
| **Chaos** | pytest + métriques mockées | Activator, rollback automatique, healthcheck failure | ~60s | Docker + Prometheus mock |

---

## Configuration pytest

```ini
# pytest.ini
[pytest]
DJANGO_SETTINGS_MODULE = config.settings.test
python_files = tests/test_*.py tests/**/test_*.py
python_classes = Test*
python_functions = test_*
asyncio_mode = auto
markers =
    integration: Tests nécessitant une vraie base de données
    network: Tests nécessitant Docker
    chaos: Tests de résilience
    e2e: Tests end-to-end
```

```python
# config/settings/test.py
from .base import *

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "forge_test",
        "USER": "forge",
        "PASSWORD": "forge",
        "HOST": "localhost",
        "PORT": "5432",
    }
}

CELERY_TASK_ALWAYS_EAGER = True  # Exécution synchrone en tests
CELERY_TASK_EAGER_PROPAGATES = True
CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}
```

---

## Factories

```python
# tests/factories.py
import factory
from factory.django import DjangoModelFactory
from apps.accounts.models import User
from apps.organizations.models import Organization
from apps.workspaces.models import Workspace, WorkspaceMember
from apps.projects.models import Project
from apps.environments.models import Environment
from apps.services.models import Service
from apps.deployments.models import Deployment


class UserFactory(DjangoModelFactory):
    class Meta:
        model = User

    email = factory.Sequence(lambda n: f"user{n}@test.forge")
    username = factory.Sequence(lambda n: f"user{n}")
    password = factory.PostGenerationMethodCall("set_password", "testpass123")


class OrganizationFactory(DjangoModelFactory):
    class Meta:
        model = Organization

    name = factory.Sequence(lambda n: f"Org {n}")
    slug = factory.Sequence(lambda n: f"org-{n}")


class WorkspaceFactory(DjangoModelFactory):
    class Meta:
        model = Workspace

    organization = factory.SubFactory(OrganizationFactory)
    name = factory.Sequence(lambda n: f"Workspace {n}")
    slug = factory.Sequence(lambda n: f"ws-{n}")


class WorkspaceMemberFactory(DjangoModelFactory):
    class Meta:
        model = WorkspaceMember

    workspace = factory.SubFactory(WorkspaceFactory)
    user = factory.SubFactory(UserFactory)
    role = "developer"


class ProjectFactory(DjangoModelFactory):
    class Meta:
        model = Project

    workspace = factory.SubFactory(WorkspaceFactory)
    name = factory.Sequence(lambda n: f"Project {n}")
    slug = factory.Sequence(lambda n: f"project-{n}")


class EnvironmentFactory(DjangoModelFactory):
    class Meta:
        model = Environment

    project = factory.SubFactory(ProjectFactory)
    name = "Production"
    slug = "production"
    kind = Environment.Kind.PRODUCTION


class ServiceFactory(DjangoModelFactory):
    class Meta:
        model = Service

    environment = factory.SubFactory(EnvironmentFactory)
    name = factory.Sequence(lambda n: f"Service {n}")
    slug = factory.Sequence(lambda n: f"service-{n}")
    service_type = "web"
    runtime = "dockerfile"


class DeploymentFactory(DjangoModelFactory):
    class Meta:
        model = Deployment

    service = factory.SubFactory(ServiceFactory)
    status = Deployment.Status.PENDING
    phase = Deployment.Phase.BRONZE
```

---

## Tests de permissions multi-tenant (critiques)

```python
# tests/test_permissions.py
import pytest
from rest_framework.test import APIClient
from tests.factories import (
    UserFactory, WorkspaceFactory, WorkspaceMemberFactory,
    ProjectFactory, EnvironmentFactory, ServiceFactory, DeploymentFactory,
)


@pytest.mark.integration
@pytest.mark.django_db
class TestWorkspaceIsolation:
    def setup_method(self):
        self.client = APIClient()

        # Workspace A avec utilisateur A
        self.user_a = UserFactory()
        self.ws_a = WorkspaceFactory()
        WorkspaceMemberFactory(workspace=self.ws_a, user=self.user_a, role="admin")

        # Workspace B avec utilisateur B
        self.user_b = UserFactory()
        self.ws_b = WorkspaceFactory()
        WorkspaceMemberFactory(workspace=self.ws_b, user=self.user_b, role="admin")

        # Service dans workspace A
        self.project_a = ProjectFactory(workspace=self.ws_a)
        self.env_a = EnvironmentFactory(project=self.project_a)
        self.service_a = ServiceFactory(environment=self.env_a)

    def _auth(self, user, workspace):
        from rest_framework_simplejwt.tokens import RefreshToken
        token = str(RefreshToken.for_user(user).access_token)
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {token}",
            HTTP_X_WORKSPACE_SLUG=workspace.slug,
        )

    def test_user_b_cannot_see_services_from_ws_a(self):
        self._auth(self.user_b, self.ws_b)
        response = self.client.get(f"/api/v1/environments/{self.env_a.pk}/services/")
        # Doit retourner 404 (workspace A non accessible) ou liste vide
        assert response.status_code in (404, 200)
        if response.status_code == 200:
            assert len(response.data["results"]) == 0

    def test_user_b_cannot_deploy_service_from_ws_a(self):
        self._auth(self.user_b, self.ws_b)
        response = self.client.post(f"/api/v1/services/{self.service_a.pk}/deploy/")
        assert response.status_code in (403, 404)

    def test_user_b_cannot_access_ws_a_secrets(self):
        self._auth(self.user_b, self.ws_b)
        response = self.client.get(f"/api/v1/workspaces/{self.ws_a.slug}/secrets/")
        assert response.status_code in (403, 404)

    def test_user_a_can_see_own_services(self):
        self._auth(self.user_a, self.ws_a)
        response = self.client.get(f"/api/v1/environments/{self.env_a.pk}/services/")
        assert response.status_code == 200
        assert any(s["id"] == self.service_a.pk for s in response.data["results"])
```

---

## Tests du Forge Activator

```python
# tests/test_activator.py
import pytest
from unittest.mock import patch, MagicMock
from apps.activator.models import ActivatorRule, ActivatorExecution
from apps.activator.tasks import evaluate_activator_rules
from tests.factories import WorkspaceFactory, ServiceFactory


@pytest.mark.django_db
class TestActivatorRuleEvaluation:
    def test_gt_operator_triggers_when_above_threshold(self):
        rule = ActivatorRule(
            condition_operator="gt",
            condition_threshold=80.0,
        )
        assert rule.evaluate(85.0) is True
        assert rule.evaluate(75.0) is False

    def test_circuit_breaker_prevents_excessive_executions(self):
        ws = WorkspaceFactory()
        rule = ActivatorRule.objects.create(
            workspace=ws,
            name="Test Rule",
            target_type="service",
            condition_metric="cpu_usage",
            condition_operator="gt",
            condition_threshold=50.0,
            action_type="alert_email",
            circuit_breaker_limit=3,
            action_payload={"recipients": ["ops@test.forge"]},
        )
        # Créer 3 exécutions récentes (atteint la limite)
        for _ in range(3):
            ActivatorExecution.objects.create(rule=rule, metric_value=80.0)

        with patch("apps.activator.tasks.MetricsAdapter.query", return_value=85.0):
            with patch("apps.activator.tasks.execute_activator_action.apply_async") as mock_exec:
                evaluate_activator_rules()
                mock_exec.assert_not_called()  # circuit-breaker actif


@pytest.mark.django_db
class TestActivatorAutoRollback:
    def test_rollback_triggered_on_high_error_rate(self):
        ws = WorkspaceFactory()
        service = ServiceFactory(environment__project__workspace=ws)
        # Créer un déploiement SUCCESS pour pouvoir rollback
        DeploymentFactory(service=service, status="success", image_ref="localhost:5000/ws/svc:abc123")

        rule = ActivatorRule.objects.create(
            workspace=ws,
            name="Auto-rollback on error rate",
            target_type="service",
            target_id=service.pk,
            condition_metric="error_rate",
            condition_operator="gt",
            condition_threshold=0.05,
            action_type="rollback",
        )

        with patch("apps.activator.tasks.MetricsAdapter.query", return_value=0.1):
            with patch("apps.deployments.services.DeploymentService.rollback") as mock_rollback:
                evaluate_activator_rules()
                mock_rollback.assert_called_once()
```

---

## Tests chaos — Rollback automatique sur healthcheck failure

```python
# tests/chaos/test_deployment_rollback.py
import pytest
from unittest.mock import patch, MagicMock
from apps.deployments.tasks import run_deployment_pipeline
from tests.factories import DeploymentFactory, ServiceFactory


@pytest.mark.chaos
@pytest.mark.django_db
def test_automatic_rollback_on_healthcheck_failure():
    service = ServiceFactory()
    deployment = DeploymentFactory(service=service, status="pending", phase="bronze")

    with patch("adapters.git_adapter.GitAdapter.clone_and_checkout", return_value=("/tmp/repo", "abc1234")):
        with patch("adapters.git_adapter.GitAdapter.validate_build_config"):
            with patch("adapters.registry_adapter.RegistryAdapter.build_and_push", return_value="localhost:5000/ws/svc:abc1234"):
                with patch("adapters.docker_adapter.DockerAdapter.run_service") as mock_run:
                    with patch("adapters.docker_adapter.DockerAdapter.wait_for_healthy", return_value=False):
                        with patch("adapters.docker_adapter.DockerAdapter.stop_container"):
                            with patch("adapters.docker_adapter.DockerAdapter.restore_previous_container") as mock_restore:
                                run_deployment_pipeline(deployment.id)

                                deployment.refresh_from_db()
                                assert deployment.status in ("failed", "rolled_back")
                                assert deployment.phase == "gold"
                                mock_restore.assert_called_once()
```

---

## Pipeline CI

```yaml
# .github/workflows/ci.yml
name: CI

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_DB: forge_test
          POSTGRES_USER: forge
          POSTGRES_PASSWORD: forge
        options: >-
          --health-cmd pg_isready
          --health-interval 10s

    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install dependencies
        run: pip install -r backend/requirements/dev.txt
      - name: Lint
        run: cd backend && ruff check . && mypy apps/
      - name: Unit tests
        run: cd backend && pytest -m "not integration and not network and not chaos" --cov=apps
      - name: Integration tests
        run: cd backend && pytest -m integration --cov=apps --cov-append
      - name: Upload coverage
        uses: codecov/codecov-action@v4
```
