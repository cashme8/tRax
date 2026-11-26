"""
Server-side pricing: turns what the user typed (quantity, unit price, net
amount, tax treatment) into subtotals, VAT and totals, using the rules in
tax_engine. The API never accepts these computed numbers from the client.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from companies.models import Company
from tax_engine.rules import TaxRuleError
from tax_engine.vat import LineVat, round_money, vat_for_line


class PricingError(Exception):
    """The figures can't be computed (e.g. no tax profile or VAT rule). Safe to show users."""


def charges_vat_on(company: Company, on_date: date) -> bool:
    """Only a company that is VAT-registered on the sale date may charge VAT."""
    profile = company.tax_profile_on(on_date)
    if profile is None:
        raise PricingError(
            f"{company.legal_name} has no tax profile in force on {on_date:%d %b %Y}. "
            "Add one that starts on or before this date."
        )
    return profile.vat_registered


def _line_vat(net: Decimal, treatment: str, on_date: date, charge_vat: bool) -> LineVat:
    try:
        return vat_for_line(net, treatment, on_date, charge_vat=charge_vat)
    except TaxRuleError as exc:
        raise PricingError(str(exc)) from exc


@dataclass
class PricedInvoice:
    lines: list[dict]  # each: the input fields + line_subtotal, vat_rate, vat_amount, ...
    subtotal: Decimal
    vat_amount: Decimal
    total_amount: Decimal


def price_invoice(company: Company, issue_date: date, items: list[dict]) -> PricedInvoice:
    """`items` are dicts with quantity, unit_price, tax_treatment (and description)."""
    charge_vat = charges_vat_on(company, issue_date)
    lines = []
    for position, item in enumerate(items):
        net = round_money(item["quantity"] * item["unit_price"])
        vat = _line_vat(net, item["tax_treatment"], issue_date, charge_vat)
        lines.append(
            {
                **item,
                "position": position,
                "line_subtotal": vat.net,
                "vat_rate": vat.rate,
                "vat_amount": vat.vat,
                "line_total": vat.total,
                "tax_rule": vat.rule,
            }
        )
    subtotal = sum((line["line_subtotal"] for line in lines), Decimal("0.00"))
    vat_amount = sum((line["vat_amount"] for line in lines), Decimal("0.00"))
    return PricedInvoice(lines, subtotal, vat_amount, subtotal + vat_amount)


def price_spending(
    net: Decimal, treatment: str, on_date: date, *, supplier_charges_vat: bool = True
) -> dict:
    """
    Input VAT on a purchase or expense, from its VAT-exclusive amount.
    A supplier that isn't VAT-registered charges none (supplier_charges_vat=False).

    Whether that VAT can actually be *claimed* (buyer VAT-registered, supplier's
    EBM receipt present...) is decided by tax_engine.services.calculate_vat.
    """
    vat = _line_vat(net, treatment, on_date, charge_vat=supplier_charges_vat)
    return {
        "amount_excl_vat": vat.net,
        "vat_rate": vat.rate,
        "vat_amount": vat.vat,
        "total_amount": vat.total,
        "tax_rule": vat.rule,
    }
