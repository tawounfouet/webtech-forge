from django.http import HttpRequest, HttpResponse

from .models import AuditLog

AUDITED_METHODS = {"POST", "PATCH", "PUT", "DELETE"}
AUDITED_PATH_PREFIXES = ("/api/v1/deployments", "/api/v1/secrets", "/api/v1/members")


class AuditMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        response = self.get_response(request)
        if (
            request.method in AUDITED_METHODS
            and any(request.path.startswith(p) for p in AUDITED_PATH_PREFIXES)
            and request.user.is_authenticated
            and response.status_code < 400
        ):
            AuditLog.objects.create(
                workspace=getattr(request, "workspace", None),
                user=request.user,
                action=f"{request.method} {request.path}",
                http_status=response.status_code,
                ip_address=self._get_ip(request),
            )
        return response

    @staticmethod
    def _get_ip(request: HttpRequest) -> str:
        xff = request.META.get("HTTP_X_FORWARDED_FOR")
        return xff.split(",")[0].strip() if xff else request.META.get("REMOTE_ADDR", "")
