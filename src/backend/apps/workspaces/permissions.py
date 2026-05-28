from rest_framework.permissions import BasePermission

ROLE_HIERARCHY: dict[str, int] = {
    "admin": 6,
    "maintainer": 5,
    "operator": 4,
    "developer": 3,
    "viewer": 2,
    "auditor": 1,
}


class WorkspacePermission(BasePermission):
    """
    Base RBAC permission tied to the workspace resolved by WorkspaceMiddleware.

    Subclass and set required_role to enforce a minimum level.
    has_object_permission delegates to has_permission — object-level isolation
    is enforced at the queryset level (get_queryset always filters by workspace).
    """

    required_role = "viewer"

    def has_permission(self, request, view) -> bool:
        if not getattr(request, "workspace", None):
            return False
        user_role = getattr(request, "workspace_role", None)
        if not user_role:
            return False
        return ROLE_HIERARCHY.get(user_role, 0) >= ROLE_HIERARCHY.get(self.required_role, 0)

    def has_object_permission(self, request, view, obj) -> bool:
        return self.has_permission(request, view)


class IsWorkspaceAdmin(WorkspacePermission):
    required_role = "admin"


class IsMaintainerOrAbove(WorkspacePermission):
    required_role = "maintainer"


class IsOperatorOrAbove(WorkspacePermission):
    required_role = "operator"


class IsDeveloperOrAbove(WorkspacePermission):
    required_role = "developer"


class IsViewerOrAbove(WorkspacePermission):
    required_role = "viewer"
