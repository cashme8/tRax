"""
Business records. Every one inherits CompanyOwnedModel (so it has `company`).

Amounts the user types (quantity, unit price, net amount) are inputs; every
VAT and total field is computed on the server by accounting/pricing.py and
can't be set through the API.
"""

from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q, Sum

from companies.models import CompanyOwnedModel, tin_validator
from tax_engine.models import TaxRule, TaxTreatment

ZERO = Decimal("0.00")


def money_field(**kwargs) -> models.DecimalField:
    """RWF amount: exact decimal, up to 99 trillion, 2 decimal places. Never a float."""
    kwargs.setdefault("max_digits", 16)
    kwargs.setdefault("decimal_places", 2)
    return models.DecimalField(**kwargs)


def computed_money() -> models.DecimalField:
    return money_field(default=ZERO, editable=False)


def rate_field() -> models.DecimalField:
    return models.DecimalField(max_digits=7, decimal_places=4, default=Decimal("0"), editable=False)


def treatment_field() -> models.CharField:
    return models.CharField(
        max_length=20, choices=TaxTreatment.choices, default=TaxTreatment.STANDARD
    )


non_negative = MinValueValidator(Decimal("0"))
positive = MinValueValidator(Decimal("0.01"))


# --- Parties ----------------------------------------------------------------


class Party(CompanyOwnedModel):
    name = models.CharField(max_length=255)
    tin = models.CharField("TIN", max_length=9, blank=True, validators=[tin_validator])
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    address = models.CharField(max_length=255, blank=True)

    class Meta:
        abstract = True
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Customer(Party):
    pass


class Supplier(Party):
    # A supplier that isn't VAT-registered can't charge VAT, so its bills carry no input VAT.
    # Changing this later doesn't re-price purchases already recorded.
    vat_registered = models.BooleanField("VAT-registered", default=True)


# --- Sales ------------------------------------------------------------------


class Invoice(CompanyOwnedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"  # editable
        ISSUED = "issued", "Issued"  # final: counts for VAT, can receive payments
        CANCELLED = "cancelled", "Cancelled"  # final: kept for the record, ignored for VAT

    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="invoices")
    invoice_number = models.CharField(max_length=50)
    # TODO(EBM/VSDC): filled from the EBM receipt when the invoice is issued.
    # NULL = no EBM receipt yet (lets a future per-company unique constraint skip blanks).
    ebm_receipt_number = models.CharField(max_length=100, null=True, blank=True)  # noqa: DJ001
    issue_date = models.DateField()
    due_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    notes = models.TextField(blank=True)

    subtotal = computed_money()
    vat_amount = computed_money()
    total_amount = computed_money()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["company", "invoice_number"], name="unique_invoice_number_per_company"
            )
        ]
        ordering = ["-issue_date", "-created_at"]

    def __str__(self) -> str:
        return self.invoice_number

    def audit_snapshot_extra(self) -> dict:
        """The audit log records an invoice together with its lines."""
        return {
            "items": [
                {
                    "description": item.description,
                    "quantity": item.quantity,
                    "unit_price": item.unit_price,
                    "tax_treatment": item.tax_treatment,
                    "vat_amount": item.vat_amount,
                    "line_total": item.line_total,
                }
                for item in self.items.order_by("position")
            ]
        }

    @property
    def amount_paid(self) -> Decimal:
        # The list view pre-computes `paid_sum` in one query; otherwise ask the DB.
        paid = getattr(self, "paid_sum", None)
        if paid is None:
            paid = self.payments.aggregate(total=Sum("amount"))["total"]
        return paid or ZERO

    @property
    def balance_due(self) -> Decimal:
        return self.total_amount - self.amount_paid

    @property
    def payment_status(self) -> str:
        paid = self.amount_paid
        if paid <= 0:
            return "unpaid"
        return "paid" if paid >= self.total_amount else "partially_paid"


class InvoiceItem(CompanyOwnedModel):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="items")
    position = models.PositiveIntegerField(default=0)
    description = models.CharField(max_length=255)
    quantity = models.DecimalField(max_digits=12, decimal_places=3, validators=[positive])
    unit_price = money_field(validators=[non_negative])  # VAT-exclusive
    tax_treatment = treatment_field()

    line_subtotal = computed_money()
    vat_rate = rate_field()
    vat_amount = computed_money()
    line_total = computed_money()
    # Which rule produced vat_rate, so any past figure can be explained.
    tax_rule = models.ForeignKey(
        TaxRule, on_delete=models.PROTECT, null=True, blank=True, editable=False, related_name="+"
    )

    class Meta:
        ordering = ["invoice", "position"]

    def __str__(self) -> str:
        return self.description


class Payment(CompanyOwnedModel):
    class Method(models.TextChoices):
        CASH = "cash", "Cash"
        BANK_TRANSFER = "bank_transfer", "Bank transfer"
        MOBILE_MONEY = "mobile_money", "Mobile money"  # TODO(MoMo): link to MTN/Airtel API
        CHEQUE = "cheque", "Cheque"
        CARD = "card", "Card"
        OTHER = "other", "Other"

    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name="payments")
    amount = money_field(validators=[positive])
    payment_date = models.DateField()
    payment_method = models.CharField(max_length=20, choices=Method.choices)
    reference = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ["-payment_date", "-created_at"]
        constraints = [models.CheckConstraint(condition=Q(amount__gt=0), name="payment_positive")]


# --- Spending ---------------------------------------------------------------


class PricedLine(CompanyOwnedModel):
    """Shared shape of a purchase and an expense: net amount in, VAT and total computed."""

    description = models.CharField(max_length=255, blank=True)
    tax_treatment = treatment_field()
    amount_excl_vat = money_field(validators=[non_negative])
    vat_rate = rate_field()
    vat_amount = computed_money()  # input VAT
    total_amount = computed_money()
    tax_rule = models.ForeignKey(
        TaxRule, on_delete=models.PROTECT, null=True, blank=True, editable=False, related_name="+"
    )
    # The supplier's EBM receipt. TODO(EBM): RRA requires one to claim input VAT;
    # the tax engine will warn when it's missing.
    # NULL = no EBM receipt yet (lets a future per-company unique constraint skip blanks).
    ebm_receipt_number = models.CharField(max_length=100, null=True, blank=True)  # noqa: DJ001

    class Meta:
        abstract = True


class Purchase(PricedLine):
    """Goods or services bought for resale or production (bills from suppliers)."""

    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name="purchases")
    reference_number = models.CharField(max_length=100, blank=True)
    purchase_date = models.DateField()

    class Meta:
        ordering = ["-purchase_date", "-created_at"]


class Expense(PricedLine):
    """Running costs: rent, utilities, transport, fees..."""

    class Category(models.TextChoices):
        RENT = "rent", "Rent"
        UTILITIES = "utilities", "Utilities"
        TRANSPORT = "transport", "Transport"
        OFFICE = "office", "Office supplies"
        PROFESSIONAL_FEES = "professional_fees", "Professional fees"
        COMMUNICATION = "communication", "Phone and internet"
        MAINTENANCE = "maintenance", "Repairs and maintenance"
        BANK_CHARGES = "bank_charges", "Bank charges"
        OTHER = "other", "Other"

    expense_date = models.DateField()
    category = models.CharField(max_length=30, choices=Category.choices)
    supplier = models.ForeignKey(
        Supplier, on_delete=models.PROTECT, null=True, blank=True, related_name="expenses"
    )

    class Meta:
        ordering = ["-expense_date", "-created_at"]
