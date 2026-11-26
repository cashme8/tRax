from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models

from common.models import UUIDModel


class AuditLog(UUIDModel):
    """
    One change to one record. Append-only: rows can't be edited or deleted
    through Django. TODO(before production): also block UPDATE/DELETE on this
    table at the database level (a trigger, or a DB user without those rights).
    """

    class Action(models.TextChoices):
        CREATE = "create", "Created"
        UPDATE = "update", "Updated"
        DELETE = "delete", "Deleted"
        ISSUE = "issue", "Issued"  # invoice made final
        CANCEL = "cancel", "Cancelled"

    company = models.ForeignKey(
        "companies.Company", on_delete=models.PROTECT, related_name="audit_logs"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="audit_logs",
    )
    # Kept as text too, so the history still says who it was if the user is removed.
    user_email = models.EmailField(blank=True)
    action = models.CharField(max_length=20, choices=Action.choices)
    entity_type = models.CharField(max_length=100)  # e.g. "accounting.invoice"
    entity_id = models.UUIDField()
    entity_label = models.CharField(max_length=255, blank=True)  # e.g. "INV-0001"
    # {"field": [old, new]}. On create old is null; on delete new is null.
    changes = models.JSONField(default=dict, encoder=DjangoJSONEncoder)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["company", "-created_at"]),
            models.Index(fields=["entity_type", "entity_id"]),
        ]

    def __str__(self) -> str:
        return f"{self.user_email or 'system'} {self.action} {self.entity_type} {self.entity_label}"

    def save(self, *args, **kwargs) -> None:
        if not self._state.adding:
            raise RuntimeError("Audit log entries are permanent and can't be changed.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise RuntimeError("Audit log entries are permanent and can't be deleted.")
