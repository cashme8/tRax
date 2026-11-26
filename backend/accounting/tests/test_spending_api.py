"""Purchases, expenses, customers and suppliers."""

import pytest

from accounting.tests.factories import CustomerFactory, InvoiceFactory, SupplierFactory
from companies.tests.factories import CompanyFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def supplier(owner):
    return SupplierFactory(company=owner.company)


def test_purchase_input_vat_is_computed(api, supplier):
    response = api.post(
        "/api/purchases/",
        {
            "supplier": str(supplier.pk),
            "purchase_date": "2026-03-05",
            "tax_treatment": "standard",
            "amount_excl_vat": "250000.00",
            "vat_amount": "1.00",  # ignored
        },
        format="json",
    )
    assert response.status_code == 201, response.json()
    body = response.json()
    assert body["vat_amount"] == "45000.00"
    assert body["total_amount"] == "295000.00"
    assert body["rule_version"] == "test-vat-18"


def test_editing_a_purchase_reprices_it(api, supplier):
    purchase = api.post(
        "/api/purchases/",
        {"supplier": str(supplier.pk), "purchase_date": "2026-03-05", "amount_excl_vat": "1000"},
        format="json",
    ).json()
    response = api.patch(
        f"/api/purchases/{purchase['id']}/", {"tax_treatment": "exempt"}, format="json"
    )
    assert response.json()["vat_amount"] == "0.00"
    assert response.json()["total_amount"] == "1000.00"


def test_purchase_from_unregistered_supplier_has_no_vat(api, owner):
    supplier = SupplierFactory(company=owner.company, vat_registered=False)
    response = api.post(
        "/api/purchases/",
        {"supplier": str(supplier.pk), "purchase_date": "2026-03-05", "amount_excl_vat": "1000"},
        format="json",
    )
    assert response.status_code == 201
    assert response.json()["vat_amount"] == "0.00"
    assert response.json()["total_amount"] == "1000.00"


def test_purchase_supplier_must_belong_to_the_company(api):
    foreign = SupplierFactory(company=CompanyFactory())
    response = api.post(
        "/api/purchases/",
        {"supplier": str(foreign.pk), "purchase_date": "2026-03-05", "amount_excl_vat": "1000"},
        format="json",
    )
    assert response.status_code == 400
    assert "supplier" in response.json()


@pytest.mark.parametrize(
    ("treatment", "vat", "total"),
    [
        ("standard", "18000.00", "118000.00"),
        ("zero_rated", "0.00", "100000.00"),
        ("exempt", "0.00", "100000.00"),
        ("non_taxable", "0.00", "100000.00"),
    ],
)
def test_expense_vat_by_treatment(api, treatment, vat, total):
    response = api.post(
        "/api/expenses/",
        {
            "expense_date": "2026-03-05",
            "category": "rent",
            "tax_treatment": treatment,
            "amount_excl_vat": "100000",
        },
        format="json",
    )
    assert response.status_code == 201, response.json()
    assert response.json()["vat_amount"] == vat
    assert response.json()["total_amount"] == total


def test_expense_supplier_is_optional(api):
    response = api.post(
        "/api/expenses/",
        {"expense_date": "2026-03-05", "category": "transport", "amount_excl_vat": "5000"},
        format="json",
    )
    assert response.status_code == 201
    assert response.json()["supplier"] is None


def test_customer_with_invoices_cannot_be_deleted(api, owner):
    customer = CustomerFactory(company=owner.company)
    InvoiceFactory(company=owner.company, customer=customer)
    response = api.delete(f"/api/customers/{customer.pk}/")
    assert response.status_code == 400


def test_unused_customer_can_be_deleted(api, owner):
    customer = CustomerFactory(company=owner.company)
    assert api.delete(f"/api/customers/{customer.pk}/").status_code == 204


def test_customer_tin_must_be_nine_digits_if_given(api):
    assert api.post("/api/customers/", {"name": "X", "tin": "123"}).status_code == 400
    assert api.post("/api/customers/", {"name": "Y", "tin": ""}).status_code == 201
