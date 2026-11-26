from django.contrib import admin

from tax_engine.models import TaxRule


@admin.register(TaxRule)
class TaxRuleAdmin(admin.ModelAdmin):
    """Internal staff maintain tax rules here. Saving runs TaxRule.clean() (no overlaps)."""

    list_display = [
        "tax_type",
        "rate",
        "effective_from",
        "effective_to",
        "rule_version",
        "is_verified",
    ]
    list_filter = ["tax_type", "is_verified"]
