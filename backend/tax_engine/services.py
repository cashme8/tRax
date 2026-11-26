"""
VAT for a period: output VAT on sales minus claimable input VAT on purchases
and expenses. Works only from records already priced by the server, so every
figure traces back to stored lines and the TaxRule each one used.

This is a preparation aid: the company or its accountant reviews and files
the return on RRA e-Tax. TODO(e-Tax): export in the format e-Tax accepts.
TODO(compliance): store each run as a TaxCalculation linked to a TaxPeriod.
"""

from dataclasses import asdict, dataclass, field
from datetime import date
from decimal import Decimal

from django.db.models import Count, Sum

from accounting.models import Expense, Invoice, InvoiceItem, Purchase
from companies.models import Company
from tax_engine.models import TaxRule, TaxTreatment

ZERO = Decimal("0.00")


@dataclass
class Totals:
    net: Decimal = ZERO  # VAT-exclusive amount
    vat: Decimal = ZERO
    count: int = 0  # number of lines / records

    def add(self, net: Decimal, vat: Decimal, count: int = 1) -> None:
        self.net += net
        self.vat += vat
        self.count += count


def _by_treatment() -> dict[str, Totals]:
    return {treatment: Totals() for treatment in TaxTreatment.values}


@dataclass
class VatWarning:
    code: str
    message: str
    count: int = 0


@dataclass
class VatSummary:
    company_id: str
    period_start: date
    period_end: date
    output_vat: Decimal  # VAT charged on issued sales invoices
    input_vat: Decimal  # input VAT that can be claimed
    input_vat_not_claimable: Decimal  # VAT paid but not claimable (e.g. not registered)
    net_vat: Decimal  # output - input; negative = credit
    net_payable: Decimal  # what to pay RRA (0 if in credit)
    credit: Decimal  # excess input VAT (0 if payable). TODO: carry forward between periods.
    output_by_treatment: dict[str, Totals]
    purchases_by_treatment: dict[str, Totals]
    expenses_by_treatment: dict[str, Totals]
    rule_versions: list[str]
    warnings: list[VatWarning] = field(default_factory=list)

    def as_dict(self) -> dict:
        """JSON-friendly: decimals and dates as strings."""

        def convert(value):
            if isinstance(value, Decimal):
                return f"{value:.2f}"
            if isinstance(value, date):
                return value.isoformat()
            if isinstance(value, dict):
                return {k: convert(v) for k, v in value.items()}
            if isinstance(value, list):
                return [convert(v) for v in value]
            return value

        return convert(asdict(self))


class _Registration:
    """Answers "was the company VAT-registered on this date?" from its profile history."""

    def __init__(self, company: Company):
        self.profiles = list(company.tax_profiles.order_by("-effective_from"))

    def on(self, day: date) -> bool:
        for profile in self.profiles:
            if profile.effective_from <= day:
                return profile.vat_registered
        return False  # no profile yet → treated as not registered


def calculate_vat(company: Company, period_start: date, period_end: date) -> VatSummary:
    """VAT position for `company` from period_start to period_end (both inclusive)."""
    if period_start > period_end:
        raise ValueError("period_start must be on or before period_end.")
    period = (period_start, period_end)
    registration = _Registration(company)
    warnings: list[VatWarning] = []

    # --- Output VAT: lines of ISSUED invoices dated in the period ---------------
    # Drafts aren't final and cancelled invoices are void, so neither counts.
    output = _by_treatment()
    issued_lines = InvoiceItem.objects.filter(
        company=company,
        invoice__status=Invoice.Status.ISSUED,
        invoice__issue_date__range=period,
    )
    for row in issued_lines.values("tax_treatment").annotate(
        net=Sum("line_subtotal"), vat=Sum("vat_amount"), n=Count("id")
    ):
        output[row["tax_treatment"]].add(row["net"], row["vat"], row["n"])
    output_vat = sum((t.vat for t in output.values()), ZERO)

    # --- Input VAT: purchases and expenses dated in the period ------------------
    purchases = _by_treatment()
    expenses = _by_treatment()
    claimable = ZERO
    not_claimable = ZERO
    unregistered_records = 0
    missing_receipts = 0

    spending = [
        (
            purchases,
            Purchase.objects.filter(company=company, purchase_date__range=period),
            "purchase_date",
        ),
        (
            expenses,
            Expense.objects.filter(company=company, expense_date__range=period),
            "expense_date",
        ),
    ]
    for totals, records, date_field in spending:
        for record in records:
            totals[record.tax_treatment].add(record.amount_excl_vat, record.vat_amount)
            if record.vat_amount <= 0:
                continue
            if not registration.on(getattr(record, date_field)):
                # Only a VAT-registered business can claim input VAT.
                not_claimable += record.vat_amount
                unregistered_records += 1
                continue
            claimable += record.vat_amount
            if not record.ebm_receipt_number:
                missing_receipts += 1

    # --- Warnings ---------------------------------------------------------------
    if unregistered_records:
        warnings.append(
            VatWarning(
                "input_vat_not_registered",
                "Input VAT on these records isn't claimable: the company wasn't "
                "VAT-registered on their dates.",
                unregistered_records,
            )
        )
    if missing_receipts:
        # Counted for now (EBM integration doesn't exist yet), but RRA requires an
        # EBM receipt to claim input VAT. TODO(EBM): make this strict.
        warnings.append(
            VatWarning(
                "input_vat_missing_ebm_receipt",
                "Input VAT is counted on records with no supplier EBM receipt number. "
                "RRA requires one to claim it: add the receipt numbers before filing.",
                missing_receipts,
            )
        )
    drafts = Invoice.objects.filter(
        company=company, status=Invoice.Status.DRAFT, issue_date__range=period
    ).count()
    if drafts:
        warnings.append(
            VatWarning(
                "draft_invoices_excluded",
                "Draft invoices dated in this period aren't included. Issue or delete them.",
                drafts,
            )
        )
    no_ebm = Invoice.objects.filter(
        company=company,
        status=Invoice.Status.ISSUED,
        issue_date__range=period,
        ebm_receipt_number__isnull=True,
    ).count()
    if no_ebm:
        warnings.append(
            VatWarning(
                "sales_missing_ebm_receipt",
                "Issued invoices with no EBM receipt number. Every sale needs an EBM receipt.",
                no_ebm,
            )
        )

    # --- Which rules produced these numbers -------------------------------------
    rule_ids = set(issued_lines.exclude(tax_rule=None).values_list("tax_rule", flat=True))
    for _, records, _ in spending:
        rule_ids |= set(records.exclude(tax_rule=None).values_list("tax_rule", flat=True))
    rules = TaxRule.objects.filter(pk__in=rule_ids)
    unverified = [r.rule_version for r in rules if not r.is_verified]
    if unverified:
        warnings.append(
            VatWarning(
                "unverified_tax_rules",
                "Some rates used haven't been verified with RRA yet: "
                + ", ".join(sorted(unverified)),
                len(unverified),
            )
        )

    net_vat = output_vat - claimable
    return VatSummary(
        company_id=str(company.pk),
        period_start=period_start,
        period_end=period_end,
        output_vat=output_vat,
        input_vat=claimable,
        input_vat_not_claimable=not_claimable,
        net_vat=net_vat,
        net_payable=max(net_vat, ZERO),
        credit=max(-net_vat, ZERO),
        output_by_treatment=output,
        purchases_by_treatment=purchases,
        expenses_by_treatment=expenses,
        rule_versions=sorted(r.rule_version for r in rules),
        warnings=warnings,
    )
