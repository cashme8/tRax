"""
All endpoints here subclass CompanyScopedViewSet, so each one is automatically:
filtered to the X-Company-ID company, saved to that company, and role-checked
(viewers read; owners and accountants write).
"""

from django.db.models import Sum
from rest_framework import exceptions
from rest_framework.decorators import action
from rest_framework.response import Response

from accounting.models import Customer, Expense, Invoice, Payment, Purchase, Supplier
from accounting.serializers import (
    CustomerSerializer,
    ExpenseSerializer,
    InvoiceSerializer,
    PaymentSerializer,
    PurchaseSerializer,
    SupplierSerializer,
)
from companies.scoping import CompanyScopedViewSet

NO_PUT = ["get", "post", "patch", "delete", "head", "options"]


class CustomerViewSet(CompanyScopedViewSet):
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer
    http_method_names = NO_PUT


class SupplierViewSet(CompanyScopedViewSet):
    queryset = Supplier.objects.all()
    serializer_class = SupplierSerializer
    http_method_names = NO_PUT


class InvoiceViewSet(CompanyScopedViewSet):
    """
    Drafts can be edited and deleted. POST .../issue/ makes an invoice final
    (it then counts for VAT and can be paid); POST .../cancel/ voids an issued,
    unpaid invoice. Optional filter: ?status=draft|issued|cancelled
    """

    queryset = (
        Invoice.objects.select_related("customer")
        .prefetch_related("items__tax_rule")
        .annotate(paid_sum=Sum("payments__amount"))
        # Explicit: Django drops Meta.ordering on queries with aggregates (GROUP BY).
        .order_by("-issue_date", "-created_at")
    )
    serializer_class = InvoiceSerializer
    http_method_names = NO_PUT

    def get_queryset(self):
        queryset = super().get_queryset()
        status = self.request.query_params.get("status")
        if status:
            queryset = queryset.filter(status=status)
        return queryset

    def perform_destroy(self, invoice: Invoice) -> None:
        if invoice.status != Invoice.Status.DRAFT:
            raise exceptions.ValidationError(
                {"detail": "Only draft invoices can be deleted. Cancel an issued invoice instead."}
            )
        super().perform_destroy(invoice)

    @action(detail=True, methods=["post"])
    def issue(self, request, pk=None):
        invoice = self.get_object()
        if invoice.status != Invoice.Status.DRAFT:
            raise exceptions.ValidationError(
                {"detail": f"This invoice is already {invoice.status}."}
            )
        # Re-price with the rules in force now, in case they changed since the draft was saved.
        serializer = self.get_serializer(invoice, data={}, partial=True)
        serializer.is_valid(raise_exception=True)
        invoice = serializer.save()
        invoice.status = Invoice.Status.ISSUED
        invoice.save(update_fields=["status", "updated_at"])
        # TODO(EBM/VSDC): send the invoice to VSDC here and store ebm_receipt_number.
        return Response(self.get_serializer(invoice).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        invoice = self.get_object()
        if invoice.status != Invoice.Status.ISSUED:
            raise exceptions.ValidationError(
                {"detail": "Only issued invoices can be cancelled (delete a draft instead)."}
            )
        if invoice.payments.exists():
            raise exceptions.ValidationError(
                {"detail": "This invoice has payments. Remove them before cancelling."}
            )
        # TODO(EBM/VSDC): issue the matching EBM refund/credit note.
        invoice.status = Invoice.Status.CANCELLED
        invoice.save(update_fields=["status", "updated_at"])
        return Response(self.get_serializer(invoice).data)


class PaymentViewSet(CompanyScopedViewSet):
    """Record or remove payments. Not editable: delete a wrong one and record it again."""

    queryset = Payment.objects.select_related("invoice")
    serializer_class = PaymentSerializer
    http_method_names = ["get", "post", "delete", "head", "options"]


class PurchaseViewSet(CompanyScopedViewSet):
    queryset = Purchase.objects.select_related("supplier", "tax_rule")
    serializer_class = PurchaseSerializer
    http_method_names = NO_PUT


class ExpenseViewSet(CompanyScopedViewSet):
    queryset = Expense.objects.select_related("supplier", "tax_rule")
    serializer_class = ExpenseSerializer
    http_method_names = NO_PUT
