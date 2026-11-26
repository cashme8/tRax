from django.contrib import admin

from accounting.models import Customer, Expense, Invoice, InvoiceItem, Payment, Purchase, Supplier


class InvoiceItemInline(admin.TabularInline):
    model = InvoiceItem
    extra = 0
    readonly_fields = ["line_subtotal", "vat_rate", "vat_amount", "line_total", "tax_rule"]


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    """Read-mostly view for staff support. Users work through the app, where totals are computed."""

    list_display = ["invoice_number", "company", "customer", "issue_date", "status", "total_amount"]
    list_filter = ["status"]
    search_fields = ["invoice_number", "customer__name", "company__legal_name"]
    readonly_fields = ["subtotal", "vat_amount", "total_amount"]
    inlines = [InvoiceItemInline]


for model in (Customer, Supplier, Payment, Purchase, Expense):
    admin.site.register(model)
