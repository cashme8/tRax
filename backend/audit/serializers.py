from rest_framework import serializers

from audit.models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditLog
        fields = [
            "id",
            "created_at",
            "user_email",
            "action",
            "entity_type",
            "entity_id",
            "entity_label",
            "changes",
        ]
        read_only_fields = fields
