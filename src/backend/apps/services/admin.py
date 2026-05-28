from django.contrib import admin

from .models import Domain, Healthcheck, Service, ServiceBinding, ServiceEnvVar, Volume


class ServiceEnvVarInline(admin.TabularInline):
    model = ServiceEnvVar
    extra = 0
    max_num = 20


class DomainInline(admin.TabularInline):
    model = Domain
    extra = 0
    readonly_fields = ("created_at",)


class VolumeInline(admin.TabularInline):
    model = Volume
    extra = 0


class HealthcheckInline(admin.StackedInline):
    model = Healthcheck
    extra = 0
    max_num = 1
    can_delete = False


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "slug",
        "environment",
        "service_type",
        "runtime",
        "internal_port",
        "replicas",
        "active_deployment",
        "created_at",
    )
    list_filter = ("service_type", "runtime")
    search_fields = ("name", "slug", "environment__slug", "image")
    readonly_fields = ("created_at", "updated_at")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [
        ServiceEnvVarInline,
        DomainInline,
        VolumeInline,
        HealthcheckInline,
    ]


@admin.register(ServiceEnvVar)
class ServiceEnvVarAdmin(admin.ModelAdmin):
    list_display = ("service", "key", "is_secret", "secret_ref")
    list_filter = ("is_secret",)
    search_fields = ("key", "service__name", "service__slug")


@admin.register(Domain)
class DomainAdmin(admin.ModelAdmin):
    list_display = ("hostname", "service", "is_custom", "tls_enabled", "created_at")
    list_filter = ("is_custom", "tls_enabled")
    search_fields = ("hostname", "service__name")
    readonly_fields = ("created_at",)


@admin.register(Volume)
class VolumeAdmin(admin.ModelAdmin):
    list_display = ("name", "service", "mount_path", "size_gb")
    search_fields = ("name", "service__name", "mount_path")


@admin.register(Healthcheck)
class HealthcheckAdmin(admin.ModelAdmin):
    list_display = ("service", "protocol", "path", "interval_seconds", "timeout_seconds", "retries")
    list_filter = ("protocol",)
    search_fields = ("service__name", "path")


@admin.register(ServiceBinding)
class ServiceBindingAdmin(admin.ModelAdmin):
    list_display = ("source_service", "target_service", "binding_type", "env_prefix", "allowed_by")
    list_filter = ("binding_type",)
    search_fields = ("source_service__name", "target_service__name", "env_prefix")
