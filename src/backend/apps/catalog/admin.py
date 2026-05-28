from django.contrib import admin

from .models import ServiceTemplate


@admin.register(ServiceTemplate)
class ServiceTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "endorsement", "service_type", "runtime", "default_port", "endorsed_by", "created_at")
    list_filter = ("endorsement", "service_type", "runtime")
    search_fields = ("name", "slug", "description")
    readonly_fields = ("created_at", "updated_at")
    prepopulated_fields = {"slug": ("name",)}
