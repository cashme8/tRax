"""
Abstract base models. "Abstract" means Django creates no table for these;
each model that inherits them gets the fields in its own table.
"""

import uuid

from django.db import models


class UUIDModel(models.Model):
    """UUID primary key: IDs can't be guessed or counted (unlike 1, 2, 3...)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class TimeStampedModel(UUIDModel):
    """UUID primary key plus created/updated timestamps, set automatically."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
