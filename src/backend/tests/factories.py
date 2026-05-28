import factory
from django.utils import timezone
from factory.django import DjangoModelFactory

from apps.accounts.models import User
from apps.activator.models import ActivatorExecution, ActivatorRule
from apps.audit.models import AuditLog
from apps.catalog.models import ServiceTemplate
from apps.deployments.models import Deployment, DeploymentEvent, RollbackRecord
from apps.environments.models import Environment, PromotionPolicy
from apps.monitor.models import MonitorSnapshot
from apps.organizations.models import Organization
from apps.projects.models import Project, ProjectRepository
from apps.services.models import Domain, Healthcheck, Service, ServiceBinding, ServiceEnvVar, Volume
from apps.workspaces.models import Workspace, WorkspaceMember, WorkspaceQuota, WorkspaceSecret


class UserFactory(DjangoModelFactory):
    class Meta:
        model = User
        django_get_or_create = ("email",)

    username = factory.Sequence(lambda n: f"user{n}")
    email = factory.LazyAttribute(lambda o: f"{o.username}@forge.test")
    password = factory.PostGenerationMethodCall("set_password", "testpassword123!")
    is_active = True
    mfa_enabled = False


class OrganizationFactory(DjangoModelFactory):
    class Meta:
        model = Organization

    name = factory.Sequence(lambda n: f"Org {n}")
    slug = factory.Sequence(lambda n: f"org-{n}")
    billing_email = factory.LazyAttribute(lambda o: f"billing@{o.slug}.com")


class WorkspaceFactory(DjangoModelFactory):
    class Meta:
        model = Workspace

    organization = factory.SubFactory(OrganizationFactory)
    name = factory.Sequence(lambda n: f"Workspace {n}")
    slug = factory.Sequence(lambda n: f"ws-{n}")
    description = ""


class WorkspaceMemberFactory(DjangoModelFactory):
    class Meta:
        model = WorkspaceMember

    workspace = factory.SubFactory(WorkspaceFactory)
    user = factory.SubFactory(UserFactory)
    role = WorkspaceMember.Role.DEVELOPER
    added_by = None


class WorkspaceSecretFactory(DjangoModelFactory):
    class Meta:
        model = WorkspaceSecret

    workspace = factory.SubFactory(WorkspaceFactory)
    key = factory.Sequence(lambda n: f"SECRET_KEY_{n}")
    value = factory.Faker("password", length=32)
    description = ""


class WorkspaceQuotaFactory(DjangoModelFactory):
    class Meta:
        model = WorkspaceQuota

    workspace = factory.SubFactory(WorkspaceFactory)
    max_services = 20
    max_cpu_cores = 8
    max_memory_gb = 16.0
    max_storage_gb = 50.0


class ProjectFactory(DjangoModelFactory):
    class Meta:
        model = Project

    workspace = factory.SubFactory(WorkspaceFactory)
    name = factory.Sequence(lambda n: f"Project {n}")
    slug = factory.Sequence(lambda n: f"project-{n}")
    description = ""


class ProjectRepositoryFactory(DjangoModelFactory):
    class Meta:
        model = ProjectRepository

    project = factory.SubFactory(ProjectFactory)
    name = factory.Sequence(lambda n: f"repo-{n}")
    repo_url = factory.Sequence(lambda n: f"https://github.com/webtech/repo-{n}.git")
    default_branch = "main"
    is_primary = True


class EnvironmentFactory(DjangoModelFactory):
    class Meta:
        model = Environment

    project = factory.SubFactory(ProjectFactory)
    name = factory.Sequence(lambda n: f"env-{n}")
    slug = factory.Sequence(lambda n: f"env-{n}")
    kind = Environment.Kind.DEVELOPMENT
    protected = False
    auto_deploy_branch = ""


class ProductionEnvironmentFactory(EnvironmentFactory):
    name = "production"
    slug = "production"
    kind = Environment.Kind.PRODUCTION
    protected = True


class PromotionPolicyFactory(DjangoModelFactory):
    class Meta:
        model = PromotionPolicy

    environment = factory.SubFactory(EnvironmentFactory)
    require_approval = False
    min_approvers = 1
    notify_channels = factory.List([])


class ServiceTemplateFactory(DjangoModelFactory):
    class Meta:
        model = ServiceTemplate

    name = factory.Sequence(lambda n: f"Template {n}")
    slug = factory.Sequence(lambda n: f"template-{n}")
    endorsement = ServiceTemplate.EndorsementLevel.EXPERIMENTAL
    service_type = "web"
    runtime = "dockerfile"
    default_port = 8000


class ServiceFactory(DjangoModelFactory):
    class Meta:
        model = Service

    environment = factory.SubFactory(EnvironmentFactory)
    name = factory.Sequence(lambda n: f"service-{n}")
    slug = factory.Sequence(lambda n: f"service-{n}")
    service_type = Service.Type.WEB
    runtime = Service.Runtime.DOCKERFILE
    dockerfile_path = "Dockerfile"
    build_context = "."
    internal_port = 8000
    replicas = 1


class ServiceEnvVarFactory(DjangoModelFactory):
    class Meta:
        model = ServiceEnvVar

    service = factory.SubFactory(ServiceFactory)
    key = factory.Sequence(lambda n: f"ENV_VAR_{n}")
    value = factory.Faker("word")
    is_secret = False


class DomainFactory(DjangoModelFactory):
    class Meta:
        model = Domain

    service = factory.SubFactory(ServiceFactory)
    hostname = factory.Sequence(lambda n: f"app-{n}.forge.local")
    is_custom = False
    tls_enabled = True


class VolumeFactory(DjangoModelFactory):
    class Meta:
        model = Volume

    service = factory.SubFactory(ServiceFactory)
    name = factory.Sequence(lambda n: f"vol-{n}")
    mount_path = factory.Sequence(lambda n: f"/data/vol-{n}")
    size_gb = 1.0


class HealthcheckFactory(DjangoModelFactory):
    class Meta:
        model = Healthcheck

    service = factory.SubFactory(ServiceFactory)
    protocol = Healthcheck.Protocol.HTTP
    path = "/health"
    interval_seconds = 30
    timeout_seconds = 5
    retries = 3


class DeploymentFactory(DjangoModelFactory):
    class Meta:
        model = Deployment

    service = factory.SubFactory(ServiceFactory)
    phase = Deployment.Phase.BRONZE
    status = Deployment.Status.PENDING
    trigger_source = Deployment.TriggerSource.MANUAL
    triggered_by = factory.SubFactory(UserFactory)
    commit_sha = factory.Faker("sha1")
    failure_reason = ""


class SuccessfulDeploymentFactory(DeploymentFactory):
    phase = Deployment.Phase.GOLD
    status = Deployment.Status.SUCCESS
    started_at = factory.LazyFunction(timezone.now)
    finished_at = factory.LazyFunction(timezone.now)


class DeploymentEventFactory(DjangoModelFactory):
    class Meta:
        model = DeploymentEvent

    deployment = factory.SubFactory(DeploymentFactory)
    phase = "bronze"
    message = factory.Faker("sentence")
    level = DeploymentEvent.Level.INFO


class RollbackRecordFactory(DjangoModelFactory):
    class Meta:
        model = RollbackRecord

    deployment = factory.SubFactory(DeploymentFactory)
    rolled_back_to = factory.SubFactory(DeploymentFactory)
    triggered_by = factory.SubFactory(UserFactory)
    trigger_source = RollbackRecord.TriggerSource.MANUAL


class ActivatorRuleFactory(DjangoModelFactory):
    class Meta:
        model = ActivatorRule

    workspace = factory.SubFactory(WorkspaceFactory)
    service = factory.SubFactory(ServiceFactory)
    name = factory.Sequence(lambda n: f"Rule {n}")
    metric = ActivatorRule.Metric.CPU_PERCENT
    operator = ActivatorRule.Operator.GT
    threshold = 80.0
    action = ActivatorRule.Action.ALERT
    cooldown_seconds = 300
    is_active = True
    circuit_open = False


class ActivatorExecutionFactory(DjangoModelFactory):
    class Meta:
        model = ActivatorExecution

    rule = factory.SubFactory(ActivatorRuleFactory)
    measured_value = 85.0
    result = ActivatorExecution.Result.TRIGGERED
    action_taken = "alert"


class MonitorSnapshotFactory(DjangoModelFactory):
    class Meta:
        model = MonitorSnapshot

    workspace = factory.SubFactory(WorkspaceFactory)
    total_services = 5
    running_services = 4
    failed_services = 1
    total_deployments_last_24h = 10
    failed_deployments_last_24h = 1


class AuditLogFactory(DjangoModelFactory):
    class Meta:
        model = AuditLog

    workspace = factory.SubFactory(WorkspaceFactory)
    user = factory.SubFactory(UserFactory)
    action = factory.Sequence(lambda n: f"POST /api/v1/deployments/{n}/")
    resource_type = "Deployment"
    resource_id = factory.Sequence(str)
    http_status = 201
    ip_address = "127.0.0.1"
    metadata = factory.Dict({})
