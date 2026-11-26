from django.db.models import Sum
from rest_framework import serializers

from accounting.models import (
    ZERO,
    Customer,
    Expense,
    Invoice,
    InvoiceItem,
    Payment,
    Purchase,
    Supplier,
)
from accounting.pricing import PricingError, price_invoice, price_spending
from common.serializers import ExplicitBooleanField
from companies.scoping import CompanyScopedPrimaryKeyRelatedField as ScopedPK

MONEY_READ = {"max_digits": 16, "decimal_places": 2, "read_only": True}


def _pricing_error(exc: PricingError) -> serializers.ValidationError:
    return serializers.ValidationError({"non_field_errors": [str(exc)]})


# --- Parties ----------------------------------------------------------------

PARTY_FIELDS = ["id", "name", "tin", "email", "phone", "address", "created_at"]


class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = PARTY_FIELDS
        read_only_fields = ["id", "created_at"]


class SupplierSerializer(serializers.ModelSerializer):
    # Must be chosen explicitly: it decides whether purchases carry input VAT.
    vat_registered = ExplicitBooleanField(required=True)

    class Meta:
        model = Supplier
        fields = [*PARTY_FIELDS, "vat_registered"]
        read_only_fields = ["id", "created_at"]

    def get_fields(self):
        fields = super().get_fields()
        if self.instance is not None:  # PATCH may leave it unchanged
            fields["vat_registered"].required = False
        return fields


# --- Invoices ---------------------------------------------------------------

ITEM_INPUT_FIELDS = ["description", "quantity", "unit_price", "tax_treatment"]


class InvoiceItemSerializer(serializers.ModelSerializer):
    rule_version = serializers.CharField(
        source="tax_rule.rule_version", read_only=True, default=None
    )

    class Meta:
        model = InvoiceItem
        fields = [
            "id",
            *ITEM_INPUT_FIELDS,
            # computed by the server (model fields are editable=False → read-only here)
            "line_subtotal",
            "vat_rate",
            "vat_amount",
            "line_total",
            "rule_version",
        ]
        read_only_fields = ["id"]


class InvoiceSerializer(serializers.ModelSerializer):
    customer = ScopedPK(queryset=Customer.objects.all())
    customer_name = serializers.CharField(source="customer.name", read_only=True)
    items = InvoiceItemSerializer(many=True, required=False)
    amount_paid = serializers.DecimalField(**MONEY_READ)
    balance_due = serializers.DecimalField(**MONEY_READ)
    payment_status = serializers.CharField(read_only=True)

    class Meta:
        model = Invoice
        fields = [
            "id",
            "invoice_number",
            "customer",
            "customer_name",
            "issue_date",
            "due_date",
            "status",
            "ebm_receipt_number",
            "notes",
            "items",
            "subtotal",
            "vat_amount",
            "total_amount",
            "amount_paid",
            "balance_due",
            "payment_status",
            "created_at",
            "updated_at",
        ]
        # status changes only via /issue/ and /cancel/; EBM number comes from EBM (later).
        read_only_fields = ["id", "status", "ebm_receipt_number", "created_at", "updated_at"]

    def validate_invoice_number(self, value: str) -> str:
        clash = Invoice.objects.filter(company=self.context["company"], invoice_number=value)
        if self.instance is not None:
            clash = clash.exclude(pk=self.instance.pk)
        if clash.exists():
            raise serializers.ValidationError(
                "This company already has an invoice with this number."
            )
        return value

    def validate(self, attrs: dict) -> dict:
        invoice = self.instance
        if invoice is not None and invoice.status != Invoice.Status.DRAFT:
            raise serializers.ValidationError(
                {"non_field_errors": [f"A {invoice.status} invoice can't be changed."]}
            )

        issue_date = attrs.get("issue_date", getattr(invoice, "issue_date", None))
        due_date = attrs.get("due_date", getattr(invoice, "due_date", None))
        if due_date and issue_date and due_date < issue_date:
            raise serializers.ValidationError({"due_date": "Can't be before the issue date."})

        if "items" in attrs:
            items = attrs["items"]
        elif invoice is not None:  # editing other fields: re-price the existing lines
            items = [
                {field: getattr(item, field) for field in ITEM_INPUT_FIELDS}
                for item in invoice.items.all()
            ]
        else:
            items = []
        if not items:
            raise serializers.ValidationError({"items": "An invoice needs at least one line."})

        try:
            attrs["priced"] = price_invoice(self.context["company"], issue_date, items)
        except PricingError as exc:
            raise _pricing_error(exc) from exc
        return attrs

    def create(self, validated_data: dict) -> Invoice:
        priced = validated_data.pop("priced")
        validated_data.pop("items", None)
        invoice = Invoice.objects.create(**validated_data)
        return self._store_lines(invoice, priced)

    def update(self, invoice: Invoice, validated_data: dict) -> Invoice:
        priced = validated_data.pop("priced")
        validated_data.pop("items", None)
        for field, value in validated_data.items():
            setattr(invoice, field, value)
        return self._store_lines(invoice, priced)

    @staticmethod
    def _store_lines(invoice: Invoice, priced) -> Invoice:
        """Replace all lines with the freshly priced ones and store the totals."""
        invoice.items.all().delete()
        InvoiceItem.objects.bulk_create(
            InvoiceItem(invoice=invoice, company=invoice.company, **line) for line in priced.lines
        )
        invoice.subtotal = priced.subtotal
        invoice.vat_amount = priced.vat_amount
        invoice.total_amount = priced.total_amount
        invoice.save()
        # Drop any cached prefetch so the response shows the new lines.
        if hasattr(invoice, "_prefetched_objects_cache"):
            invoice._prefetched_objects_cache.clear()
        return invoice


# --- Payments ---------------------------------------------------------------


class PaymentSerializer(serializers.ModelSerializer):
    invoice = ScopedPK(queryset=Invoice.objects.all())
    invoice_number = serializers.CharField(source="invoice.invoice_number", read_only=True)

    class Meta:
        model = Payment
        fields = [
            "id",
            "invoice",
            "invoice_number",
            "amount",
            "payment_date",
            "payment_method",
            "reference",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def validate(self, attrs: dict) -> dict:
        # Lock the invoice row so two payments recorded at the same moment
        # can't both pass the "not more than the balance" check.
        invoice = Invoice.objects.select_for_update().get(pk=attrs["invoice"].pk)
        if invoice.status != Invoice.Status.ISSUED:
            raise serializers.ValidationError(
                {
                    "invoice": "Payments can only be recorded on issued invoices "
                    f"(this one is {invoice.status})."
                }
            )
        paid = invoice.payments.aggregate(total=Sum("amount"))["total"] or ZERO
        balance = invoice.total_amount - paid
        if attrs["amount"] > balance:
            raise serializers.ValidationError(
                {"amount": f"More than the balance due ({balance} RWF)."}
            )
        if attrs["payment_date"] < invoice.issue_date:
            raise serializers.ValidationError(
                {"payment_date": "Can't be before the invoice's issue date."}
            )
        return attrs


# --- Purchases and expenses -------------------------------------------------

SPENDING_COMPUTED = ["vat_rate", "vat_amount", "total_amount", "rule_version"]


class SpendingSerializer(serializers.ModelSerializer):
    """Shared by purchases and expenses: price the line on every create/update."""

    date_field: str  # set by subclasses
    rule_version = serializers.CharField(
        source="tax_rule.rule_version", read_only=True, default=None
    )

    def validate(self, attrs: dict) -> dict:
        def current(field):
            """Value being sent, else the saved value, else the model's default."""
            if field in attrs:
                return attrs[field]
            if self.instance is not None:
                return getattr(self.instance, field)
            return self.Meta.model._meta.get_field(field).get_default()

        supplier = current("supplier")
        try:
            attrs.update(
                price_spending(
                    current("amount_excl_vat"),
                    current("tax_treatment"),
                    current(self.date_field),
                    supplier_charges_vat=supplier.vat_registered if supplier else True,
                )
            )
        except PricingError as exc:
            raise _pricing_error(exc) from exc
        return attrs


class PurchaseSerializer(SpendingSerializer):
    date_field = "purchase_date"
    supplier = ScopedPK(queryset=Supplier.objects.all())
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)

    class Meta:
        model = Purchase
        fields = [
            "id",
            "supplier",
            "supplier_name",
            "reference_number",
            "ebm_receipt_number",
            "purchase_date",
            "description",
            "tax_treatment",
            "amount_excl_vat",
            *SPENDING_COMPUTED,
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class ExpenseSerializer(SpendingSerializer):
    date_field = "expense_date"
    supplier = ScopedPK(queryset=Supplier.objects.all(), required=False, allow_null=True)
    supplier_name = serializers.CharField(source="supplier.name", read_only=True, default=None)

    class Meta:
        model = Expense
        fields = [
            "id",
            "expense_date",
            "category",
            "description",
            "supplier",
            "supplier_name",
            "ebm_receipt_number",
            "tax_treatment",
            "amount_excl_vat",
            *SPENDING_COMPUTED,
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]
