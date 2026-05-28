from django.http import HttpRequest, HttpResponse

from .models import WorkspaceMember


class WorkspaceMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        request.workspace = None
        request.workspace_role = None

        workspace_slug = request.headers.get("X-Workspace-Slug") or self._extract_from_url(
            request.path
        )
        if workspace_slug and request.user.is_authenticated:
            try:
                membership = WorkspaceMember.objects.select_related("workspace").get(
                    workspace__slug=workspace_slug,
                    user=request.user,
                )
                request.workspace = membership.workspace
                request.workspace_role = membership.role
            except WorkspaceMember.DoesNotExist:
                pass

        return self.get_response(request)

    @staticmethod
    def _extract_from_url(path: str) -> str | None:
        # /api/v1/workspaces/{slug}/... → slug
        parts = path.strip("/").split("/")
        if len(parts) >= 4 and parts[2] == "workspaces":
            return parts[3]
        return None
