from django.contrib import admin

from .models import ActivatorExecution, ActivatorRule


class ActivatorExecutionInline(admin.TabularInline):
    model = ActivatorExecution
    extra = 0
    readonly_fields = ("measured_value", "result", "action_taken", "error_message", "executed_at")
    can_delete = False
    max_num = 10
    ordering = ("-executed_at",)


@admin.register(ActivatorRule)
class ActivatorRuleAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "workspace",
        "service",
        "metric",
        "operator",
        "threshold",
        "action",
        "is_active",
        "circuit_open",
        "created_at",
    )
    list_filter = ("is_active", "circuit_open", "metric", "operator", "action")
    search_fields = ("name", "workspace__slug", "service__name")
    readonly_fields = ("circuit_opened_at", "created_at")
    inlines = [ActivatorExecutionInline]


@admin.register(ActivatorExecution)
class ActivatorExecutionAdmin(admin.ModelAdmin):
    list_display = ("rule", "measured_value", "result", "action_taken", "executed_at")
    list_filter = ("result",)
    search_fields = ("rule__name", "action_taken", "error_message")
    readonly_fields = ("executed_at",)
