"""Looking up which tax rule applies on a given date."""

from datetime import date

from django.db.models import Q

from tax_engine.models import TaxRule


class TaxRuleError(Exception):
    """No usable rule for a tax on a date. Messages are safe to show to users."""


def rule_in_force(tax_type: str, on_date: date) -> TaxRule:
    rules = list(
        TaxRule.objects.filter(tax_type=tax_type, effective_from__lte=on_date)
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=on_date))
        .order_by("-effective_from")[:2]
    )
    if not rules:
        raise TaxRuleError(f"No {tax_type.upper()} rule is in force on {on_date:%d %b %Y}.")
    if len(rules) > 1:
        # TaxRule.clean() prevents this; if it happens anyway, refuse to guess.
        raise TaxRuleError(
            f"More than one {tax_type.upper()} rule is in force on {on_date:%d %b %Y}. "
            "An administrator must fix the tax rules."
        )
    return rules[0]
