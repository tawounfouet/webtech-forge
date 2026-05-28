from django.contrib import admin
from django.urls import include, path
from django_prometheus import exports as prometheus_exports

API = "api/v1/"

urlpatterns = [
    path("admin/", admin.site.urls),
    path(API + "auth/", include("apps.accounts.urls")),
    path(API, include("apps.organizations.urls")),
    path(API, include("apps.workspaces.urls")),
    path(API, include("apps.projects.urls")),
    path(API, include("apps.environments.urls")),
    path(API, include("apps.services.urls")),
    path(API, include("apps.deployments.urls")),
    path(API, include("apps.activator.urls")),
    path(API, include("apps.monitor.urls")),
    path(API + "catalog/", include("apps.catalog.urls")),
    path(API, include("apps.audit.urls")),
    # Prometheus metrics endpoint (accès interne uniquement via Traefik)
    path("metrics/", prometheus_exports.ExportToDjangoView, name="prometheus-metrics"),
]
