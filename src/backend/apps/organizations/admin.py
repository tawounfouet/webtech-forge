from django.contrib import admin

from .models import Organization


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "billing_email", "created_at")
    search_fields = ("name", "slug", "billing_email")
    readonly_fields = ("created_at",)
    prepopulated_fields = {"slug": ("name",)}
