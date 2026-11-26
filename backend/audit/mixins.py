"""
AuditedMixin: gives a view `audited_create / audited_update / audited_destroy
/ audited_action`. The shared base views (CompanyScopedViewSet and friends)
call these from perform_create/update/destroy, so every endpoint built on
them is audited without having to remember to be.

Each audit row is written in the same database transaction as the change
(ATOMIC_REQUESTS), so there's never a change without its log line, or the reverse.
"""

from collections.abc import Callable

from django.db import models

from audit.models import AuditLog
from audit.services import record_change, snapshot


class AuditedMixin:
    def audit_company(self, instance: models.Model):
        """Which company a log row belongs to. Company-scoped views: the active company."""
        return self.company

    def _log(self, action, instance, before, after, entity_id=None, label=None, company=None):
        record_change(
            request=self.request,
            company=company or self.audit_company(instance),
            action=action,
            model=type(instance),
            entity_id=entity_id or instance.pk,
            entity_label=label if label is not None else str(instance),
            before=before,
            after=after,
        )

    def audited_create(self, serializer, **save_kwargs) -> models.Model:
        instance = serializer.save(**save_kwargs)
        self._log(AuditLog.Action.CREATE, instance, {}, snapshot(instance))
        return instance

    def audited_update(self, serializer, **save_kwargs) -> models.Model:
        before = snapshot(serializer.instance)
        instance = serializer.save(**save_kwargs)
        self._log(AuditLog.Action.UPDATE, instance, before, snapshot(instance))
        return instance

    def audited_destroy(self, instance, delete: Callable[[], object] | None = None) -> None:
        before = snapshot(instance)
        entity_id, label = instance.pk, str(instance)  # pk is cleared by delete()
        company = self.audit_company(instance)
        (delete or instance.delete)()
        self._log(
            AuditLog.Action.DELETE,
            instance,
            before,
            {},
            entity_id=entity_id,
            label=label,
            company=company,
        )

    def audited_action(self, action: str, instance, change: Callable[[], object]):
        """For custom actions like issuing an invoice: snapshot, run `change`, log."""
        before = snapshot(instance)
        result = change()
        self._log(action, instance, before, snapshot(instance))
        return result
