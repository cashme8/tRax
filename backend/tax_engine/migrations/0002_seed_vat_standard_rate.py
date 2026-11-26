"""
Seed data: Rwanda's standard VAT rate.

⚠ TO BE VERIFIED WITH RRA. The 18% rate is from general knowledge; the start
date is an approximation (VAT replaced the old turnover tax around 2001). A
tax advisor must confirm both, then set is_verified=True in Django admin.
If RRA confirms a different start date, change it in admin; don't edit this file.
"""

import datetime
from decimal import Decimal

from django.db import migrations

RULE_VERSION = "vat-std-v1"


def seed(apps, schema_editor):
    TaxRule = apps.get_model("tax_engine", "TaxRule")
    TaxRule.objects.get_or_create(
        tax_type="vat",
        rule_version=RULE_VERSION,
        defaults={
            "rate": Decimal("0.1800"),
            "effective_from": datetime.date(2001, 1, 1),
            "effective_to": None,
            "description": "Standard VAT rate",
            "is_verified": False,
            "source_note": (
                "TO BE VERIFIED WITH RRA: rate (18%) and start date (2001-01-01, approximate) "
                "are from general knowledge, not yet checked against the VAT law."
            ),
        },
    )


def unseed(apps, schema_editor):
    apps.get_model("tax_engine", "TaxRule").objects.filter(
        tax_type="vat", rule_version=RULE_VERSION
    ).delete()


class Migration(migrations.Migration):
    dependencies = [("tax_engine", "0001_initial")]

    operations = [migrations.RunPython(seed, unseed)]
