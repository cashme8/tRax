from django.contrib import admin

from audit.models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """Read-only: staff can search the history but never change it."""

    list_display = ["created_at", "company", "user_email", "action", "entity_type", "entity_label"]
    list_filter = ["action", "entity_type"]
    search_fields = ["user_email", "entity_label", "company__legal_name"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
