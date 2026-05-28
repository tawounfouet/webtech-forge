from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("action", "user", "workspace", "resource_type", "resource_id", "http_status", "created_at")
    list_filter = ("action", "resource_type", "http_status")
    search_fields = ("action", "resource_type", "resource_id", "ip_address", "user__email")
    readonly_fields = ("created_at",)
    date_hierarchy = "created_at"
