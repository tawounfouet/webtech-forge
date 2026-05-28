from django.contrib import admin
from django.urls import include, path
from django_prometheus import exports as prometheus_exports

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/auth/", include("apps.accounts.urls")),
    path("api/v1/", include("apps.organizations.urls")),
    path("api/v1/", include("apps.workspaces.urls")),
    path("api/v1/", include("apps.projects.urls")),
    path("api/v1/", include("apps.environments.urls")),
    path("api/v1/", include("apps.services.urls")),
    path("api/v1/", include("apps.deployments.urls")),
    path("api/v1/", include("apps.activator.urls")),
    path("api/v1/", include("apps.monitor.urls")),
    path("api/v1/", include("apps.catalog.urls")),
    path("api/v1/", include("apps.audit.urls")),
    # Prometheus metrics endpoint (accès interne uniquement via Traefik)
    path("metrics/", prometheus_exports.ExportToDjangoView, name="prometheus-metrics"),
]
