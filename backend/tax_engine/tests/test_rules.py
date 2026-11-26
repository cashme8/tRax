import datetime
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from tax_engine.models import TaxRule
from tax_engine.rules import TaxRuleError, rule_in_force

pytestmark = pytest.mark.django_db

D = datetime.date


def make_rule(rate, start, end=None, version=None) -> TaxRule:
    return TaxRule.objects.create(
        tax_type="vat",
        rate=Decimal(rate),
        effective_from=start,
        effective_to=end,
        rule_version=version or f"v-{start}",
    )


def test_seeded_vat_rule_is_18_percent_and_flagged_unverified():
    rule = TaxRule.objects.get(rule_version="vat-std-v1")
    assert rule.rate == Decimal("0.1800")
    assert rule.is_verified is False
    assert "TO BE VERIFIED WITH RRA" in rule.source_note


@pytest.fixture
def rate_change():
    """18% until 30 June 2026, then (hypothetically) 16% from 1 July."""
    TaxRule.objects.all().delete()
    old = make_rule("0.18", D(2001, 1, 1), D(2026, 6, 30), "old")
    new = make_rule("0.16", D(2026, 7, 1), None, "new")
    return old, new


def test_rule_in_force_follows_the_date(rate_change):
    old, new = rate_change
    assert rule_in_force("vat", D(2026, 6, 30)) == old  # end date is inclusive
    assert rule_in_force("vat", D(2026, 7, 1)) == new
    assert rule_in_force("vat", D(2030, 1, 1)) == new  # open-ended


def test_no_rule_before_the_first_one(rate_change):
    with pytest.raises(TaxRuleError, match="No VAT rule"):
        rule_in_force("vat", D(2000, 12, 31))


def test_overlapping_rules_are_rejected_by_validation(rate_change):
    overlapping = TaxRule(
        tax_type="vat", rate=Decimal("0.2"), effective_from=D(2026, 6, 1), rule_version="bad"
    )
    with pytest.raises(ValidationError, match="overlaps"):
        overlapping.full_clean()


def test_adjacent_rules_are_fine():
    TaxRule.objects.all().delete()
    make_rule("0.18", D(2001, 1, 1), D(2026, 6, 30), "a")
    adjacent = TaxRule(
        tax_type="vat", rate=Decimal("0.16"), effective_from=D(2026, 7, 1), rule_version="b"
    )
    adjacent.full_clean()  # no error


def test_engine_refuses_to_guess_if_overlap_slips_into_the_db():
    TaxRule.objects.all().delete()
    make_rule("0.18", D(2001, 1, 1), None, "a")
    make_rule("0.16", D(2026, 1, 1), None, "b")  # .create() skips clean()
    with pytest.raises(TaxRuleError, match="More than one"):
        rule_in_force("vat", D(2026, 3, 1))
