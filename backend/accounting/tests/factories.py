import datetime
from decimal import Decimal

import factory

from accounting.models import Customer, Expense, Invoice, Purchase, Supplier
from companies.tests.factories import CompanyFactory


class CustomerFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Customer

    company = factory.SubFactory(CompanyFactory)
    name = factory.Sequence(lambda n: f"Customer {n}")


class SupplierFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Supplier

    company = factory.SubFactory(CompanyFactory)
    name = factory.Sequence(lambda n: f"Supplier {n}")


class InvoiceFactory(factory.django.DjangoModelFactory):
    """A bare invoice row (no lines, zero totals). API tests create real ones via POST."""

    class Meta:
        model = Invoice

    company = factory.SubFactory(CompanyFactory)
    customer = factory.SubFactory(CustomerFactory, company=factory.SelfAttribute("..company"))
    invoice_number = factory.Sequence(lambda n: f"INV-{n:04d}")
    issue_date = datetime.date(2026, 3, 1)


class PurchaseFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Purchase

    company = factory.SubFactory(CompanyFactory)
    supplier = factory.SubFactory(SupplierFactory, company=factory.SelfAttribute("..company"))
    purchase_date = datetime.date(2026, 3, 1)
    amount_excl_vat = Decimal("1000.00")


class ExpenseFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Expense

    company = factory.SubFactory(CompanyFactory)
    expense_date = datetime.date(2026, 3, 1)
    category = Expense.Category.RENT
    amount_excl_vat = Decimal("1000.00")
