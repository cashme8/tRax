"""
Recording changes. Views call `record_change(...)` with a snapshot taken
before the change and the record after it; this works out what changed.

A snapshot is a plain dict of the record's stored values, made JSON-safe
(Decimal → "1180.00", dates → "2026-03-10", UUIDs → strings). A model can add
related data by defining `audit_snapshot_extra()` — Invoice adds its lines.
"""

import json

from django.core.serializers.json import DjangoJSONEncoder
from django.db import models

from audit.models import AuditLog

# Bookkeeping fields that change on every save and say nothing useful.
IGNORED_FIELDS = {"updated_at"}


def _json_safe(data: dict) -> dict:
    return json.loads(json.dumps(data, cls=DjangoJSONEncoder))


def snapshot(instance: models.Model | None) -> dict:
    """The record's current stored values, read fresh from the database."""
    if instance is None or instance.pk is None:
        return {}
    fresh = type(instance)._default_manager.filter(pk=instance.pk).first()
    if fresh is None:
        return {}
    data = {
        field.attname: getattr(fresh, field.attname)
        for field in fresh._meta.concrete_fields
        if field.attname not in IGNORED_FIELDS
    }
    extra = getattr(fresh, "audit_snapshot_extra", None)
    if callable(extra):
        data.update(extra())
    return _json_safe(data)


def diff(before: dict, after: dict) -> dict:
    """{field: [old, new]} for every field whose value differs."""
    return {
        key: [before.get(key), after.get(key)]
        for key in sorted(before.keys() | after.keys())
        if before.get(key) != after.get(key)
    }


def record_change(
    *,
    request,
    company,
    action: str,
    model: type[models.Model],
    entity_id,
    entity_label: str,
    before: dict,
    after: dict,
) -> AuditLog | None:
    """Write one AuditLog row. Pass ids/labels explicitly: after a delete, instance.pk is None."""
    changes = diff(before, after)
    if action == AuditLog.Action.UPDATE and not changes:
        return None  # a save that changed nothing isn't worth a log line
    user = request.user if request.user.is_authenticated else None
    return AuditLog.objects.create(
        company=company,
        user=user,
        user_email=user.email if user else "",
        action=action,
        entity_type=model._meta.label_lower,
        entity_id=entity_id,
        entity_label=entity_label[:255],
        changes=changes,
    )
