# 03 — Backend Django

> **ADR de référence :** ADR-002, ADR-008
> **Dépendances :** 02-monorepo-setup.md

---

## Custom User Model

À définir **avant la première migration** — impossible à changer après sans réinitialiser la base.

```python
# apps/accounts/models.py
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    email = models.EmailField(unique=True)
    mfa_enabled = models.BooleanField(default=False)
    last_active_at = models.DateTimeField(null=True, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    def __str__(self):
        return self.email
```

```python
# config/settings/base.py
AUTH_USER_MODEL = "accounts.User"
```

---

## Structure des settings

```python
# config/settings/base.py
from pathlib import Path
import environ

env = environ.Env()
BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = env("SECRET_KEY")
DEBUG = env.bool("DEBUG", default=False)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party
    "rest_framework",
    "rest_framework_simplejwt",
    "django_filters",
    "channels",
    "django_otp",
    "django_otp.plugins.otp_totp",
    # Apps métier
    "apps.accounts",
    "apps.organizations",
    "apps.workspaces",
    "apps.projects",
    "apps.environments",
    "apps.services",
    "apps.deployments",
    "apps.activator",
    "apps.monitor",
    "apps.catalog",
    "apps.audit",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "apps.workspaces.middleware.WorkspaceMiddleware",   # résout request.workspace
    "apps.audit.middleware.AuditMiddleware",             # logue les actions sensibles
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

DATABASES = {
    "default": env.db("DATABASE_URL"),
}
DATABASES["default"]["CONN_MAX_AGE"] = 60
DATABASES["default"]["OPTIONS"] = {"connect_timeout": 5}

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {"hosts": [env("REDIS_CHANNELS_URL")]},
    }
}

CELERY_BROKER_URL = env("REDIS_BROKER_URL")
CELERY_RESULT_BACKEND = env("REDIS_BROKER_URL")
CELERY_TASK_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TIMEZONE = "Europe/Paris"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 50,
    "DEFAULT_FILTER_BACKENDS": ["django_filters.rest_framework.DjangoFilterBackend"],
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {"user": "300/minute"},
}

# Sécurité production
SECURE_SSL_REDIRECT = not DEBUG
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
```

---

## WorkspaceMiddleware

Résout le workspace courant depuis l'URL ou le JWT et le place dans `request.workspace`.

```python
# apps/workspaces/middleware.py
from django.http import Http404
from .models import Workspace, WorkspaceMember


class WorkspaceMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.workspace = None
        workspace_slug = request.headers.get("X-Workspace-Slug") or \
                         self._extract_from_url(request.path)
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

    def _extract_from_url(self, path: str) -> str | None:
        # /api/v1/workspaces/{slug}/... → slug
        parts = path.strip("/").split("/")
        if len(parts) >= 4 and parts[2] == "workspaces":
            return parts[3]
        return None
```

---

## AuditMiddleware

Logue automatiquement les méthodes mutantes sur les endpoints sensibles.

```python
# apps/audit/middleware.py
from .models import AuditLog


AUDITED_METHODS = {"POST", "PATCH", "PUT", "DELETE"}
AUDITED_PATH_PREFIXES = ("/api/v1/deployments", "/api/v1/secrets", "/api/v1/members")


class AuditMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
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

    def _get_ip(self, request) -> str:
        xff = request.META.get("HTTP_X_FORWARDED_FOR")
        return xff.split(",")[0].strip() if xff else request.META.get("REMOTE_ADDR", "")
```

---

## AuditLog Model

```python
# apps/audit/models.py
from django.db import models
from django.conf import settings


class AuditLog(models.Model):
    workspace = models.ForeignKey(
        "workspaces.Workspace", null=True, on_delete=models.SET_NULL
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL
    )
    action = models.CharField(max_length=512)
    resource_type = models.CharField(max_length=64, blank=True)
    resource_id = models.CharField(max_length=64, blank=True)
    http_status = models.PositiveSmallIntegerField(null=True)
    ip_address = models.GenericIPAddressField(null=True)
    metadata = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["workspace", "created_at"]),
            models.Index(fields=["user", "created_at"]),
        ]
```

---

## ASGI — Configuration Channels

```python
# config/asgi.py
import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")

django_asgi_app = get_asgi_application()

from apps.deployments.routing import websocket_urlpatterns  # noqa: E402

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AllowedHostsOriginValidator(
        URLRouter(websocket_urlpatterns)
    ),
})
```

```python
# apps/deployments/routing.py
from django.urls import re_path
from .consumers import DeploymentLogConsumer

websocket_urlpatterns = [
    re_path(r"^ws/logs/(?P<deployment_id>\d+)/$", DeploymentLogConsumer.as_asgi()),
]
```

---

## Configuration Celery

```python
# config/celery.py
import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")

app = Celery("forge")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

app.conf.task_routes = {
    "apps.deployments.tasks.*": {"queue": "deployments"},
    "apps.activator.tasks.*": {"queue": "activator"},
    "apps.deployments.tasks.backup_*": {"queue": "backups"},
}

app.conf.beat_schedule = {
    "evaluate-activator-rules": {
        "task": "apps.activator.tasks.evaluate_activator_rules",
        "schedule": 60.0,  # toutes les 60 secondes
    },
    "backup-postgres-daily": {
        "task": "apps.deployments.tasks.backup_postgres",
        "schedule": crontab(hour=2, minute=0),
    },
    "registry-cleanup-weekly": {
        "task": "apps.deployments.tasks.registry_cleanup",
        "schedule": crontab(day_of_week=0, hour=3, minute=0),
    },
}
```
