from django.contrib import admin

from .models import MonitorSnapshot


@admin.register(MonitorSnapshot)
class MonitorSnapshotAdmin(admin.ModelAdmin):
    list_display = (
        "workspace",
        "total_services",
        "running_services",
        "failed_services",
        "total_deployments_last_24h",
        "failed_deployments_last_24h",
        "cpu_usage_percent",
        "memory_usage_percent",
        "captured_at",
    )
    list_filter = ("workspace",)
    search_fields = ("workspace__name", "workspace__slug")
    readonly_fields = ("captured_at",)
    date_hierarchy = "captured_at"
