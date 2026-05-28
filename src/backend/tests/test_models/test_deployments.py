import pytest

from tests.factories import (
    DeploymentEventFactory,
    DeploymentFactory,
    RollbackRecordFactory,
    ServiceFactory,
    SuccessfulDeploymentFactory,
)


@pytest.mark.django_db
class TestDeployment:
    def test_default_status_is_pending(self):
        d = DeploymentFactory()
        assert d.status == "pending"

    def test_default_phase_is_bronze(self):
        d = DeploymentFactory()
        assert d.phase == "bronze"

    def test_str_contains_status(self):
        d = DeploymentFactory(status="building")
        assert "building" in str(d)

    def test_successful_deployment_factory(self):
        d = SuccessfulDeploymentFactory()
        assert d.status == "success"
        assert d.phase == "gold"
        assert d.started_at is not None
        assert d.finished_at is not None

    def test_indexes_exist(self):
        from django.db import connection

        table = "deployments_deployment"
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT indexname FROM pg_indexes WHERE tablename = %s", [table]
            )
            indexes = {row[0] for row in cursor.fetchall()}
        assert any("status" in idx for idx in indexes)


@pytest.mark.django_db
class TestDeploymentEvent:
    def test_events_ordered_by_emitted_at(self):
        d = DeploymentFactory()
        e1 = DeploymentEventFactory(deployment=d, message="first")
        e2 = DeploymentEventFactory(deployment=d, message="second")
        events = list(d.events.all())
        assert events[0].pk == e1.pk
        assert events[1].pk == e2.pk

    def test_level_choices(self):
        from apps.deployments.models import DeploymentEvent

        for level in DeploymentEvent.Level:
            e = DeploymentEventFactory(level=level)
            assert e.level == level


@pytest.mark.django_db
class TestServiceDeployLock:
    def test_acquire_lock_sets_active_deployment(self):
        from apps.services.models import Service

        service = ServiceFactory()
        deployment = DeploymentFactory(service=service)
        service.acquire_deploy_lock(deployment)
        service.refresh_from_db()
        assert service.active_deployment_id == deployment.pk

    def test_acquire_lock_raises_when_locked(self):
        from django.core.exceptions import ValidationError

        service = ServiceFactory()
        d1 = DeploymentFactory(service=service)
        d2 = DeploymentFactory(service=service)
        service.acquire_deploy_lock(d1)
        with pytest.raises(ValidationError, match="already has an active deployment"):
            service.acquire_deploy_lock(d2)


@pytest.mark.django_db
class TestRollbackRecord:
    def test_rollback_links_two_deployments(self):
        service = ServiceFactory()
        d_failed = DeploymentFactory(service=service, status="failed")
        d_previous = SuccessfulDeploymentFactory(service=service)
        record = RollbackRecordFactory(deployment=d_failed, rolled_back_to=d_previous)
        assert record.deployment == d_failed
        assert record.rolled_back_to == d_previous
