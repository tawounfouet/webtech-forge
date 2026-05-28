import pytest
from django.test import RequestFactory

from apps.workspaces.middleware import WorkspaceMiddleware
from tests.factories import UserFactory, WorkspaceFactory, WorkspaceMemberFactory


def make_request(rf: RequestFactory, path: str, user=None, slug_header: str | None = None):
    request = rf.get(path)
    request.user = user or UserFactory.build()
    if slug_header:
        request.META["HTTP_X_WORKSPACE_SLUG"] = slug_header
    return request


@pytest.mark.django_db
class TestWorkspaceMiddleware:
    def get_response(self, request):
        from django.http import HttpResponse

        return HttpResponse("ok")

    def test_sets_workspace_from_url(self, rf):
        user = UserFactory()
        ws = WorkspaceFactory(slug="acme-prod")
        WorkspaceMemberFactory(workspace=ws, user=user, role="developer")

        request = rf.get("/api/v1/workspaces/acme-prod/projects/")
        request.user = user

        middleware = WorkspaceMiddleware(self.get_response)
        middleware(request)

        assert request.workspace == ws
        assert request.workspace_role == "developer"

    def test_sets_workspace_from_header(self, rf):
        user = UserFactory()
        ws = WorkspaceFactory(slug="header-ws")
        WorkspaceMemberFactory(workspace=ws, user=user, role="admin")

        request = rf.get("/api/v1/projects/")
        request.user = user
        request.META["HTTP_X_WORKSPACE_SLUG"] = "header-ws"

        middleware = WorkspaceMiddleware(self.get_response)
        middleware(request)

        assert request.workspace == ws
        assert request.workspace_role == "admin"

    def test_no_workspace_for_unauthenticated(self, rf):
        from django.contrib.auth.models import AnonymousUser

        request = rf.get("/api/v1/workspaces/acme-prod/projects/")
        request.user = AnonymousUser()

        middleware = WorkspaceMiddleware(self.get_response)
        middleware(request)

        assert request.workspace is None

    def test_no_workspace_if_not_member(self, rf):
        user = UserFactory()
        WorkspaceFactory(slug="private-ws")

        request = rf.get("/api/v1/workspaces/private-ws/projects/")
        request.user = user

        middleware = WorkspaceMiddleware(self.get_response)
        middleware(request)

        assert request.workspace is None

    def test_extract_slug_from_url(self):
        extract = WorkspaceMiddleware._extract_from_url
        assert extract("/api/v1/workspaces/my-ws/projects/") == "my-ws"
        assert extract("/api/v1/workspaces/other-ws/") == "other-ws"
        assert extract("/api/v1/other-endpoint/") is None
        assert extract("/admin/") is None


@pytest.mark.django_db
class TestAuditMiddleware:
    def test_logs_post_on_audited_path(self, rf):
        from apps.audit.models import AuditLog

        user = UserFactory()
        ws = WorkspaceFactory()

        request = rf.post("/api/v1/deployments/")
        request.user = user
        request.workspace = ws

        from django.http import HttpResponse

        def get_response(req):
            return HttpResponse("created", status=201)

        from apps.audit.middleware import AuditMiddleware

        middleware = AuditMiddleware(get_response)
        middleware(request)

        log = AuditLog.objects.filter(user=user, workspace=ws).first()
        assert log is not None
        assert log.http_status == 201
        assert "POST" in log.action

    def test_does_not_log_get_requests(self, rf):
        from apps.audit.models import AuditLog

        user = UserFactory()
        request = rf.get("/api/v1/deployments/")
        request.user = user
        request.workspace = None

        from django.http import HttpResponse
        from apps.audit.middleware import AuditMiddleware

        middleware = AuditMiddleware(lambda req: HttpResponse("ok", status=200))
        middleware(request)

        assert AuditLog.objects.count() == 0

    def test_does_not_log_on_4xx(self, rf):
        from apps.audit.models import AuditLog

        user = UserFactory()
        request = rf.post("/api/v1/deployments/")
        request.user = user
        request.workspace = None

        from django.http import HttpResponse
        from apps.audit.middleware import AuditMiddleware

        middleware = AuditMiddleware(lambda req: HttpResponse("forbidden", status=403))
        middleware(request)

        assert AuditLog.objects.count() == 0
