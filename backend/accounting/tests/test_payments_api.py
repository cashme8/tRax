import pytest

from accounting.tests.factories import CustomerFactory, InvoiceFactory
from companies.tests.factories import CompanyFactory

pytestmark = pytest.mark.django_db

URL = "/api/payments/"


@pytest.fixture
def issued_invoice(api, owner):
    """An issued invoice for 1180.00 (1000 + 18% VAT)."""
    customer = CustomerFactory(company=owner.company)
    body = api.post(
        "/api/invoices/",
        {
            "invoice_number": "INV-1",
            "customer": str(customer.pk),
            "issue_date": "2026-03-10",
            "items": [
                {
                    "description": "Goods",
                    "quantity": "1",
                    "unit_price": "1000",
                    "tax_treatment": "standard",
                }
            ],
        },
        format="json",
    ).json()
    api.post(f"/api/invoices/{body['id']}/issue/")
    return body["id"]


def pay(api, invoice_id, amount, date="2026-03-20"):
    return api.post(
        URL,
        {
            "invoice": invoice_id,
            "amount": amount,
            "payment_date": date,
            "payment_method": "mobile_money",
        },
        format="json",
    )


def invoice(api, invoice_id) -> dict:
    return api.get(f"/api/invoices/{invoice_id}/").json()


def test_partial_then_full_payment(api, issued_invoice):
    assert pay(api, issued_invoice, "500.00").status_code == 201
    body = invoice(api, issued_invoice)
    assert body["amount_paid"] == "500.00"
    assert body["balance_due"] == "680.00"
    assert body["payment_status"] == "partially_paid"

    assert pay(api, issued_invoice, "680.00").status_code == 201
    body = invoice(api, issued_invoice)
    assert body["balance_due"] == "0.00"
    assert body["payment_status"] == "paid"


def test_cannot_pay_more_than_the_balance(api, issued_invoice):
    response = pay(api, issued_invoice, "1180.01")
    assert response.status_code == 400
    assert "amount" in response.json()


@pytest.mark.parametrize("amount", ["0", "-10"])
def test_amount_must_be_positive(api, issued_invoice, amount):
    assert pay(api, issued_invoice, amount).status_code == 400


def test_cannot_pay_a_draft(api, owner):
    draft = InvoiceFactory(company=owner.company)
    response = pay(api, str(draft.pk), "10")
    assert response.status_code == 400
    assert "invoice" in response.json()


def test_cannot_pay_before_issue_date(api, issued_invoice):
    assert pay(api, issued_invoice, "10", date="2026-03-01").status_code == 400


def test_cannot_pay_another_companys_invoice(api):
    foreign = InvoiceFactory(company=CompanyFactory(), status="issued")
    response = pay(api, str(foreign.pk), "10")
    assert response.status_code == 400
    assert "invoice" in response.json()


def test_paid_invoice_cannot_be_cancelled(api, issued_invoice):
    pay(api, issued_invoice, "100")
    assert api.post(f"/api/invoices/{issued_invoice}/cancel/").status_code == 400


def test_payments_cannot_be_edited(api, issued_invoice):
    payment = pay(api, issued_invoice, "100").json()
    assert api.patch(f"{URL}{payment['id']}/", {"amount": "1"}, format="json").status_code == 405
