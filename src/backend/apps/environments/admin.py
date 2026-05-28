from django.contrib import admin

from .models import Environment, PromotionPolicy


class PromotionPolicyInline(admin.StackedInline):
    model = PromotionPolicy
    fk_name = "environment"
    extra = 0
    max_num = 1
    can_delete = False


@admin.register(Environment)
class EnvironmentAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "project", "kind", "protected", "auto_deploy_branch", "created_at")
    list_filter = ("kind", "protected")
    search_fields = ("name", "slug", "project__name", "project__slug")
    readonly_fields = ("created_at",)
    prepopulated_fields = {"slug": ("name",)}
    inlines = [PromotionPolicyInline]


@admin.register(PromotionPolicy)
class PromotionPolicyAdmin(admin.ModelAdmin):
    list_display = ("environment", "require_approval", "min_approvers", "auto_promote_from")
    list_filter = ("require_approval",)
    search_fields = ("environment__name", "environment__slug")
