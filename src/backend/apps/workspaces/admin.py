from django.contrib import admin

from .models import Workspace, WorkspaceMember, WorkspaceQuota, WorkspaceSecret


class WorkspaceMemberInline(admin.TabularInline):
    model = WorkspaceMember
    extra = 0
    readonly_fields = ("added_at",)
    max_num = 20


class WorkspaceSecretInline(admin.TabularInline):
    model = WorkspaceSecret
    extra = 0
    readonly_fields = ("created_at", "last_rotated_at")


class WorkspaceQuotaInline(admin.StackedInline):
    model = WorkspaceQuota
    extra = 0
    max_num = 1
    can_delete = False


@admin.register(Workspace)
class WorkspaceAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "organization", "created_at")
    list_filter = ("organization",)
    search_fields = ("name", "slug", "description", "organization__name")
    readonly_fields = ("created_at",)
    prepopulated_fields = {"slug": ("name",)}
    inlines = [
        WorkspaceMemberInline,
        WorkspaceSecretInline,
        WorkspaceQuotaInline,
    ]


@admin.register(WorkspaceMember)
class WorkspaceMemberAdmin(admin.ModelAdmin):
    list_display = ("user", "workspace", "role", "added_at", "added_by")
    list_filter = ("role",)
    search_fields = ("user__email", "user__username", "workspace__name", "workspace__slug")
    readonly_fields = ("added_at",)


@admin.register(WorkspaceSecret)
class WorkspaceSecretAdmin(admin.ModelAdmin):
    list_display = ("key", "workspace", "description", "last_rotated_at", "created_at")
    search_fields = ("key", "workspace__name", "description")
    readonly_fields = ("created_at",)


@admin.register(WorkspaceQuota)
class WorkspaceQuotaAdmin(admin.ModelAdmin):
    list_display = (
        "workspace",
        "max_services",
        "max_cpu_cores",
        "max_memory_gb",
        "max_storage_gb",
        "max_deployments_kept",
        "log_retention_days",
    )
    search_fields = ("workspace__name", "workspace__slug")
