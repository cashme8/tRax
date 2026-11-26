"""
VAT on a single line (an invoice item, a purchase or an expense).

Decisions (see CLAUDE.md; confirm with RRA):
  * Prices are VAT-exclusive: VAT is added on top of the net amount.
  * VAT is rounded per line, ROUND_HALF_UP, to whole RWF.
  * Net amounts are kept to 2 decimal places.
"""

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from tax_engine.models import TaxRule, TaxTreatment, TaxType
from tax_engine.rules import rule_in_force

CENTS = Decimal("0.01")
WHOLE_RWF = Decimal("1")
ZERO = Decimal("0")


def round_money(amount: Decimal) -> Decimal:
    return amount.quantize(CENTS, rounding=ROUND_HALF_UP)


def round_vat(amount: Decimal) -> Decimal:
    """Whole RWF, half-up, then shown with 2 decimals (e.g. 18.00)."""
    return amount.quantize(WHOLE_RWF, rounding=ROUND_HALF_UP).quantize(CENTS)


@dataclass(frozen=True)
class LineVat:
    net: Decimal
    rate: Decimal  # fraction, e.g. 0.1800
    vat: Decimal
    total: Decimal
    rule: TaxRule | None  # the rule used (None when no VAT applies)


def vat_for_line(
    net: Decimal, treatment: str, on_date: date, *, charge_vat: bool = True
) -> LineVat:
    """
    VAT for one line.

    `charge_vat=False` is for sales by a company that isn't VAT-registered on
    that date: it can't charge VAT, so every line gets 0.

    Raises TaxRuleError if a standard-rated line has no rule in force.
    """
    if not isinstance(net, Decimal):
        raise TypeError("Money must be a Decimal, never a float.")
    net = round_money(net)

    if treatment == TaxTreatment.STANDARD and charge_vat:
        rule = rule_in_force(TaxType.VAT, on_date)
        vat = round_vat(net * rule.rate)
        return LineVat(net=net, rate=rule.rate, vat=vat, total=net + vat, rule=rule)

    if treatment not in TaxTreatment.values:
        raise ValueError(f"Unknown tax treatment: {treatment!r}")
    # zero_rated / exempt / non_taxable, or a seller that can't charge VAT.
    return LineVat(net=net, rate=ZERO, vat=ZERO.quantize(CENTS), total=net, rule=None)
