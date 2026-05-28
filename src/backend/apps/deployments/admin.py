from django.contrib import admin

from .models import Deployment, DeploymentEvent, RollbackRecord


class DeploymentEventInline(admin.TabularInline):
    model = DeploymentEvent
    extra = 0
    readonly_fields = ("phase", "message", "level", "emitted_at")
    can_delete = False
    max_num = 20
    ordering = ("emitted_at",)


class RollbackRecordInline(admin.TabularInline):
    model = RollbackRecord
    fk_name = "deployment"
    extra = 0
    readonly_fields = ("rolled_back_to", "triggered_by", "trigger_source", "created_at")
    can_delete = False
    max_num = 5


@admin.register(Deployment)
class DeploymentAdmin(admin.ModelAdmin):
    list_display = (
        "pk",
        "service",
        "phase",
        "status",
        "trigger_source",
        "triggered_by",
        "created_at",
        "started_at",
        "finished_at",
    )
    list_filter = ("status", "phase", "trigger_source")
    search_fields = ("service__name", "service__slug", "commit_sha", "image_ref")
    readonly_fields = ("created_at", "started_at", "finished_at")
    inlines = [DeploymentEventInline, RollbackRecordInline]
    date_hierarchy = "created_at"


@admin.register(DeploymentEvent)
class DeploymentEventAdmin(admin.ModelAdmin):
    list_display = ("deployment", "phase", "level", "message", "emitted_at")
    list_filter = ("level", "phase")
    search_fields = ("message", "deployment__service__name")
    readonly_fields = ("emitted_at",)


@admin.register(RollbackRecord)
class RollbackRecordAdmin(admin.ModelAdmin):
    list_display = ("deployment", "rolled_back_to", "trigger_source", "triggered_by", "created_at")
    list_filter = ("trigger_source",)
    search_fields = ("deployment__service__name",)
    readonly_fields = ("created_at",)
