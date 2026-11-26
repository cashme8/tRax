"""
calculate_vat(company, period_start, period_end): output VAT, input VAT, net
payable, the breakdown by tax treatment, and warnings.

Records are built with the same pricing code the API uses, so these tests
exercise the real numbers, not hand-typed ones.
"""

import datetime
from decimal import Decimal

import pytest

from accounting.models import Expense, Invoice, InvoiceItem, Purchase
from accounting.pricing import price_invoice, price_spending
from accounting.tests.factories import CustomerFactory, SupplierFactory
from companies.tests.factories import CompanyFactory, TaxProfileFactory
from tax_engine.services import calculate_vat

pytestmark = pytest.mark.django_db

D = datetime.date
MARCH = (D(2026, 3, 1), D(2026, 3, 31))


# --- builders -------------------------------------------------------------


@pytest.fixture
def company(vat_18):
    company = CompanyFactory()
    TaxProfileFactory(company=company, vat_registered=True, effective_from=D(2020, 1, 1))
    return company


def sale(company, day, *lines, status=Invoice.Status.ISSUED, ebm="EBM-1") -> Invoice:
    """lines: (net amount, treatment) pairs; each becomes 1 × net."""
    items = [
        {
            "description": "x",
            "quantity": Decimal("1"),
            "unit_price": Decimal(net),
            "tax_treatment": t,
        }
        for net, t in lines
    ]
    priced = price_invoice(company, day, items)
    invoice = Invoice.objects.create(
        company=company,
        customer=CustomerFactory(company=company),
        invoice_number=f"INV-{Invoice.objects.count() + 1}",
        issue_date=day,
        status=status,
        ebm_receipt_number=ebm,
        subtotal=priced.subtotal,
        vat_amount=priced.vat_amount,
        total_amount=priced.total_amount,
    )
    InvoiceItem.objects.bulk_create(
        InvoiceItem(company=company, invoice=invoice, **line) for line in priced.lines
    )
    return invoice


def purchase(company, day, net, treatment="standard", ebm="EBM-P", supplier_registered=True):
    supplier = SupplierFactory(company=company, vat_registered=supplier_registered)
    return Purchase.objects.create(
        company=company,
        supplier=supplier,
        purchase_date=day,
        ebm_receipt_number=ebm,
        tax_treatment=treatment,
        **price_spending(Decimal(net), treatment, day, supplier_charges_vat=supplier_registered),
    )


def expense(company, day, net, treatment="standard", ebm="EBM-E"):
    return Expense.objects.create(
        company=company,
        expense_date=day,
        category=Expense.Category.RENT,
        ebm_receipt_number=ebm,
        tax_treatment=treatment,
        **price_spending(Decimal(net), treatment, day),
    )


def codes(summary) -> set[str]:
    return {w.code for w in summary.warnings}


# --- the core sum ---------------------------------------------------------


def test_output_minus_input_gives_net_payable(company):
    sale(company, D(2026, 3, 10), ("1000000", "standard"))  # 180,000 output VAT
    purchase(company, D(2026, 3, 12), "400000")  # 72,000 input VAT
    expense(company, D(2026, 3, 15), "100000")  # 18,000 input VAT

    s = calculate_vat(company, *MARCH)

    assert s.output_vat == Decimal("180000.00")
    assert s.input_vat == Decimal("90000.00")
    assert s.net_vat == Decimal("90000.00")
    assert s.net_payable == Decimal("90000.00")
    assert s.credit == Decimal("0.00")


def test_more_input_than_output_is_a_credit(company):
    sale(company, D(2026, 3, 10), ("100000", "standard"))  # 18,000
    purchase(company, D(2026, 3, 12), "500000")  # 90,000

    s = calculate_vat(company, *MARCH)

    assert s.net_vat == Decimal("-72000.00")
    assert s.net_payable == Decimal("0.00")
    assert s.credit == Decimal("72000.00")


def test_empty_period_is_all_zero(company):
    s = calculate_vat(company, *MARCH)
    assert (s.output_vat, s.input_vat, s.net_payable, s.credit) == (Decimal("0.00"),) * 4
    assert s.warnings == []


# --- treatments -------------------------------------------------------------


def test_output_breakdown_by_treatment_including_zero_rated_and_exempt(company):
    sale(
        company,
        D(2026, 3, 10),
        ("1000", "standard"),
        ("2000", "zero_rated"),
        ("3000", "exempt"),
        ("4000", "non_taxable"),
    )
    sale(company, D(2026, 3, 20), ("500", "standard"), ("700", "zero_rated"))

    s = calculate_vat(company, *MARCH)
    b = s.output_by_treatment

    assert (b["standard"].net, b["standard"].vat, b["standard"].count) == (
        Decimal("1500.00"),
        Decimal("270.00"),
        2,
    )
    assert (b["zero_rated"].net, b["zero_rated"].vat) == (Decimal("2700.00"), Decimal("0.00"))
    assert (b["exempt"].net, b["exempt"].vat) == (Decimal("3000.00"), Decimal("0.00"))
    assert (b["non_taxable"].net, b["non_taxable"].vat) == (Decimal("4000.00"), Decimal("0.00"))
    assert s.output_vat == Decimal("270.00")  # only standard lines carry VAT


def test_zero_rated_and_exempt_purchases_add_no_input_vat(company):
    purchase(company, D(2026, 3, 5), "1000", "standard")  # 180
    purchase(company, D(2026, 3, 6), "2000", "zero_rated")
    purchase(company, D(2026, 3, 7), "3000", "exempt")
    expense(company, D(2026, 3, 8), "4000", "non_taxable")

    s = calculate_vat(company, *MARCH)

    assert s.input_vat == Decimal("180.00")
    assert s.purchases_by_treatment["zero_rated"].net == Decimal("2000.00")
    assert s.purchases_by_treatment["exempt"].net == Decimal("3000.00")
    assert s.expenses_by_treatment["non_taxable"].net == Decimal("4000.00")
    assert s.purchases_by_treatment["exempt"].vat == Decimal("0.00")


def test_supplier_not_vat_registered_means_no_input_vat(company):
    purchase(company, D(2026, 3, 5), "1000", supplier_registered=False)
    assert calculate_vat(company, *MARCH).input_vat == Decimal("0.00")


# --- what's in and out of the period ---------------------------------------


def test_period_boundaries_are_inclusive(company):
    sale(company, D(2026, 2, 28), ("1000", "standard"))  # before
    sale(company, D(2026, 3, 1), ("1000", "standard"))  # first day
    sale(company, D(2026, 3, 31), ("1000", "standard"))  # last day
    sale(company, D(2026, 4, 1), ("1000", "standard"))  # after
    assert calculate_vat(company, *MARCH).output_vat == Decimal("360.00")


def test_drafts_and_cancelled_invoices_are_excluded(company):
    sale(company, D(2026, 3, 10), ("1000", "standard"))
    sale(company, D(2026, 3, 11), ("1000", "standard"), status=Invoice.Status.DRAFT)
    sale(company, D(2026, 3, 12), ("1000", "standard"), status=Invoice.Status.CANCELLED)

    s = calculate_vat(company, *MARCH)

    assert s.output_vat == Decimal("180.00")
    assert "draft_invoices_excluded" in codes(s)


def test_other_companies_records_are_never_included(company):
    other = CompanyFactory()
    TaxProfileFactory(company=other, vat_registered=True, effective_from=D(2020, 1, 1))
    sale(other, D(2026, 3, 10), ("999999", "standard"))
    purchase(other, D(2026, 3, 10), "999999")

    s = calculate_vat(company, *MARCH)

    assert s.output_vat == s.input_vat == Decimal("0.00")


def test_start_after_end_is_refused(company):
    with pytest.raises(ValueError):
        calculate_vat(company, D(2026, 3, 31), D(2026, 3, 1))


# --- registration and evidence ---------------------------------------------


def test_input_vat_not_claimable_before_vat_registration(vat_18):
    company = CompanyFactory()
    TaxProfileFactory(company=company, vat_registered=False, effective_from=D(2020, 1, 1))
    TaxProfileFactory(company=company, vat_registered=True, effective_from=D(2026, 3, 16))
    purchase(company, D(2026, 3, 10), "1000")  # before registering: 180 not claimable
    purchase(company, D(2026, 3, 20), "2000")  # after: 360 claimable

    s = calculate_vat(company, *MARCH)

    assert s.input_vat == Decimal("360.00")
    assert s.input_vat_not_claimable == Decimal("180.00")
    assert "input_vat_not_registered" in codes(s)


def test_missing_supplier_ebm_receipt_is_counted_but_warned(company):
    purchase(company, D(2026, 3, 5), "1000", ebm=None)
    s = calculate_vat(company, *MARCH)
    assert s.input_vat == Decimal("180.00")
    warning = next(w for w in s.warnings if w.code == "input_vat_missing_ebm_receipt")
    assert warning.count == 1


def test_sales_without_ebm_receipt_are_warned(company):
    sale(company, D(2026, 3, 10), ("1000", "standard"), ebm=None)
    assert "sales_missing_ebm_receipt" in codes(calculate_vat(company, *MARCH))


# --- traceability ------------------------------------------------------------


def test_lists_rule_versions_and_warns_they_are_unverified(company):
    sale(company, D(2026, 3, 10), ("1000", "standard"))
    s = calculate_vat(company, *MARCH)
    assert s.rule_versions == ["test-vat-18"]
    assert "unverified_tax_rules" in codes(s)


def test_as_dict_is_json_friendly(company):
    sale(company, D(2026, 3, 10), ("1000", "standard"))
    data = calculate_vat(company, *MARCH).as_dict()
    assert data["output_vat"] == "180.00"
    assert data["period_start"] == "2026-03-01"
    assert data["output_by_treatment"]["standard"]["vat"] == "180.00"
