"""VAT on one line: rate lookup, treatments and per-line whole-RWF rounding."""

import datetime
from decimal import Decimal

import pytest

from tax_engine.rules import TaxRuleError
from tax_engine.vat import vat_for_line

pytestmark = pytest.mark.django_db

DAY = datetime.date(2026, 3, 15)


@pytest.mark.parametrize(
    ("net", "expected_vat"),
    [
        ("1000.00", "180.00"),
        ("25.00", "5.00"),  # 4.50 → rounds half UP to 5
        ("99.99", "18.00"),  # 17.9982 → 18
        ("2.50", "0.00"),  # 0.45 → 0
        ("2.78", "1.00"),  # 0.5004 → 1
        ("0.00", "0.00"),
    ],
)
def test_standard_rate_rounds_per_line_to_whole_rwf(vat_18, net, expected_vat):
    line = vat_for_line(Decimal(net), "standard", DAY)
    assert line.vat == Decimal(expected_vat)
    assert line.total == Decimal(net) + Decimal(expected_vat)
    assert line.rate == Decimal("0.1800")
    assert line.rule == vat_18


@pytest.mark.parametrize("treatment", ["zero_rated", "exempt", "non_taxable"])
def test_non_standard_treatments_carry_no_vat(vat_18, treatment):
    line = vat_for_line(Decimal("1000"), treatment, DAY)
    assert line.vat == Decimal("0.00")
    assert line.rate == Decimal("0")
    assert line.total == Decimal("1000.00")
    assert line.rule is None


def test_seller_not_vat_registered_charges_no_vat(vat_18):
    line = vat_for_line(Decimal("1000"), "standard", DAY, charge_vat=False)
    assert line.vat == Decimal("0.00")
    assert line.rule is None


def test_floats_are_refused(vat_18):
    with pytest.raises(TypeError):
        vat_for_line(1000.0, "standard", DAY)  # type: ignore[arg-type]


def test_unknown_treatment_is_refused(vat_18):
    with pytest.raises(ValueError):
        vat_for_line(Decimal("1000"), "luxury", DAY)


def test_standard_line_without_a_rule_fails_loudly(vat_18):
    with pytest.raises(TaxRuleError):
        vat_for_line(Decimal("1000"), "standard", datetime.date(1999, 1, 1))
