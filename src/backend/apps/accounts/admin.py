from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class ForgeUserAdmin(UserAdmin):
    list_display = ("email", "username", "is_active", "mfa_enabled", "last_active_at")
    list_filter = ("is_active", "mfa_enabled", "is_staff")
    search_fields = ("email", "username")
    fieldsets = UserAdmin.fieldsets + (
        ("WebTech Forge", {"fields": ("mfa_enabled", "last_active_at")}),
    )
