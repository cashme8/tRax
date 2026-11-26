"""
User A must never see or touch company B's records, on any accounting endpoint.
(Step 8 extends this file; these are the core checks.)
"""

import pytest

from accounting.tests.factories import (
    CustomerFactory,
    ExpenseFactory,
    InvoiceFactory,
    PurchaseFactory,
    SupplierFactory,
)
from companies.tests.factories import CompanyFactory, member_of

pytestmark = pytest.mark.django_db

ENDPOINTS = [
    ("/api/customers/", CustomerFactory),
    ("/api/suppliers/", SupplierFactory),
    ("/api/invoices/", InvoiceFactory),
    ("/api/purchases/", PurchaseFactory),
    ("/api/expenses/", ExpenseFactory),
]


@pytest.fixture
def b_company():
    company = CompanyFactory()
    member_of(company)
    return company


@pytest.mark.parametrize(("url", "factory"), ENDPOINTS)
def test_a_lists_none_of_bs_records(api, b_company, url, factory):
    factory(company=b_company)
    assert api.get(url).json()["results"] == []


@pytest.mark.parametrize(("url", "factory"), ENDPOINTS)
def test_a_cannot_read_change_or_delete_bs_record(api, b_company, url, factory):
    record = factory(company=b_company)
    detail = f"{url}{record.pk}/"
    assert api.get(detail).status_code == 404
    assert api.patch(detail, {}, format="json").status_code == 404
    assert api.delete(detail).status_code == 404
    assert type(record).objects.filter(pk=record.pk).exists()


@pytest.mark.parametrize(("url", "factory"), ENDPOINTS)
def test_a_cannot_switch_to_b_with_the_header(client_for, owner, b_company, url, factory):
    factory(company=b_company)
    assert client_for(owner.user, b_company).get(url).status_code == 404


def test_create_always_lands_in_the_active_company(api, owner, b_company):
    # Even if the client tries to name another company in the body.
    response = api.post(
        "/api/customers/", {"name": "Sneaky", "company": str(b_company.pk)}, format="json"
    )
    assert response.status_code == 201
    from accounting.models import Customer

    assert Customer.objects.get(name="Sneaky").company == owner.company
