from django.http import HttpRequest, HttpResponse

from .models import WorkspaceMember


class WorkspaceMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        request.workspace = None
        request.workspace_role = None

        # DRF JWT auth runs after middleware — resolve user from token if needed.
        user = request.user if request.user.is_authenticated else self._jwt_user(request)

        workspace_slug = request.headers.get("X-Workspace-Slug") or self._extract_from_url(
            request.path
        )
        if workspace_slug and user and user.is_authenticated:
            try:
                membership = WorkspaceMember.objects.select_related("workspace").get(
                    workspace__slug=workspace_slug,
                    user=user,
                )
                request.workspace = membership.workspace
                request.workspace_role = membership.role
            except WorkspaceMember.DoesNotExist:
                pass

        return self.get_response(request)

    @staticmethod
    def _jwt_user(request: HttpRequest):
        """Decode the Bearer JWT token and return the corresponding User, or None."""
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return None
        try:
            from rest_framework_simplejwt.tokens import AccessToken

            token = AccessToken(auth_header[7:])
            from django.contrib.auth import get_user_model

            return get_user_model().objects.get(pk=token["user_id"])
        except Exception:  # noqa: BLE001
            return None

    @staticmethod
    def _extract_from_url(path: str) -> str | None:
        # /api/v1/workspaces/{slug}/... → slug
        parts = path.strip("/").split("/")
        if len(parts) >= 4 and parts[2] == "workspaces":
            return parts[3]
        return None
