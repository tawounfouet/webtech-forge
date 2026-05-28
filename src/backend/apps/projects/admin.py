from django.contrib import admin

from .models import Project, ProjectRepository


class ProjectRepositoryInline(admin.TabularInline):
    model = ProjectRepository
    extra = 0
    readonly_fields = ("created_at",)
    max_num = 10


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "workspace", "created_at")
    list_filter = ("workspace",)
    search_fields = ("name", "slug", "workspace__name", "description")
    readonly_fields = ("created_at",)
    prepopulated_fields = {"slug": ("name",)}
    inlines = [ProjectRepositoryInline]


@admin.register(ProjectRepository)
class ProjectRepositoryAdmin(admin.ModelAdmin):
    list_display = ("name", "project", "repo_url", "default_branch", "is_primary", "created_at")
    list_filter = ("is_primary", "default_branch")
    search_fields = ("name", "repo_url", "project__name")
    readonly_fields = ("created_at",)
