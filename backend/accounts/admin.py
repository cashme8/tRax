from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from accounts.models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Django's user admin, adapted for email login (no username field)."""

    ordering = ["email"]
    list_display = ["email", "full_name", "is_active", "is_staff", "created_at"]
    search_fields = ["email", "full_name"]
    readonly_fields = ["created_at", "last_login"]
    fieldsets = [
        (None, {"fields": ["email", "password"]}),
        ("Profile", {"fields": ["full_name"]}),
        ("Permissions", {"fields": ["is_active", "is_staff", "is_superuser", "groups"]}),
        ("Dates", {"fields": ["last_login", "created_at"]}),
    ]
    add_fieldsets = [
        (None, {"classes": ["wide"], "fields": ["email", "full_name", "password1", "password2"]}),
    ]
