"""Invoices: server-computed VAT and totals, and the draft → issued → cancelled lifecycle."""

import datetime
from decimal import Decimal

import pytest

from accounting.models import Invoice
from accounting.tests.factories import CustomerFactory
from companies.models import Role
from companies.tests.factories import CompanyFactory, TaxProfileFactory, member_of
from tax_engine.models import TaxRule

pytestmark = pytest.mark.django_db

URL = "/api/invoices/"


def detail(invoice_id) -> str:
    return f"{URL}{invoice_id}/"


def line(qty="1", price="1000.00", treatment="standard", description="Item") -> dict:
    return {
        "description": description,
        "quantity": qty,
        "unit_price": price,
        "tax_treatment": treatment,
    }


@pytest.fixture
def customer(owner):
    return CustomerFactory(company=owner.company)


@pytest.fixture
def payload(customer):
    def make(**overrides) -> dict:
        data = {
            "invoice_number": "INV-0001",
            "customer": str(customer.pk),
            "issue_date": "2026-03-10",
            "due_date": "2026-04-10",
            "items": [line()],
        }
        data.update(overrides)
        return data

    return make


def create(api, data) -> dict:
    response = api.post(URL, data, format="json")
    assert response.status_code == 201, response.json()
    return response.json()


# --- server-side calculation -------------------------------------------


def test_server_computes_line_vat_and_totals(api, payload):
    body = create(
        api,
        payload(
            items=[
                line(qty="2", price="1500.00"),  # 3000 net, 540 VAT
                line(qty="3", price="99.99"),  # 299.97 net, 53.9946 → 54 VAT
            ]
        ),
    )
    assert [i["line_subtotal"] for i in body["items"]] == ["3000.00", "299.97"]
    assert [i["vat_amount"] for i in body["items"]] == ["540.00", "54.00"]
    assert body["subtotal"] == "3299.97"
    assert body["vat_amount"] == "594.00"
    assert body["total_amount"] == "3893.97"
    assert body["items"][0]["rule_version"] == "test-vat-18"
    assert body["status"] == "draft"


def test_mixed_treatments_on_one_invoice(api, payload):
    body = create(
        api,
        payload(
            items=[
                line(price="1000", treatment="standard"),
                line(price="1000", treatment="zero_rated"),
                line(price="1000", treatment="exempt"),
                line(price="1000", treatment="non_taxable"),
            ]
        ),
    )
    assert [i["vat_amount"] for i in body["items"]] == ["180.00", "0.00", "0.00", "0.00"]
    assert body["vat_amount"] == "180.00"
    assert body["total_amount"] == "4180.00"


def test_totals_sent_by_the_client_are_ignored(api, payload):
    data = payload(subtotal="1.00", vat_amount="0.00", total_amount="1.00")
    data["items"][0].update({"vat_amount": "0.00", "line_total": "1.00", "vat_rate": "0"})
    body = create(api, data)
    assert body["vat_amount"] == "180.00"
    assert body["total_amount"] == "1180.00"


def test_money_is_returned_as_strings(api, payload):
    body = create(api, payload())
    assert isinstance(body["total_amount"], str)


def test_company_not_vat_registered_charges_no_vat(client_for, vat_18):
    company = CompanyFactory()
    TaxProfileFactory(
        company=company, vat_registered=False, effective_from=datetime.date(2020, 1, 1)
    )
    m = member_of(company)
    customer = CustomerFactory(company=company)
    response = client_for(m.user, company).post(
        URL,
        {
            "invoice_number": "A1",
            "customer": str(customer.pk),
            "issue_date": "2026-03-10",
            "items": [line()],
        },
        format="json",
    )
    assert response.status_code == 201
    assert response.json()["vat_amount"] == "0.00"


def test_invoice_dated_before_any_tax_profile_is_rejected(api, payload):
    response = api.post(URL, payload(issue_date="2019-06-01", due_date=None), format="json")
    assert response.status_code == 400
    assert "no tax profile" in response.json()["non_field_errors"][0]


def test_invoice_dated_when_no_vat_rule_exists_is_rejected(api, payload):
    TaxRule.objects.all().delete()
    response = api.post(URL, payload(), format="json")
    assert response.status_code == 400
    assert "No VAT rule" in response.json()["non_field_errors"][0]


# --- validation --------------------------------------------------------


def test_customer_of_another_company_is_rejected(api, payload):
    foreign_customer = CustomerFactory(company=CompanyFactory())
    response = api.post(URL, payload(customer=str(foreign_customer.pk)), format="json")
    assert response.status_code == 400
    assert "customer" in response.json()


def test_invoice_numbers_are_unique_per_company(api, payload):
    create(api, payload())
    response = api.post(URL, payload(), format="json")
    assert response.status_code == 400
    assert "invoice_number" in response.json()


def test_due_date_cannot_be_before_issue_date(api, payload):
    response = api.post(URL, payload(due_date="2026-03-01"), format="json")
    assert response.status_code == 400
    assert "due_date" in response.json()


def test_invoice_needs_at_least_one_line(api, payload):
    response = api.post(URL, payload(items=[]), format="json")
    assert response.status_code == 400
    assert "items" in response.json()


@pytest.mark.parametrize(("field", "bad"), [("quantity", "0"), ("unit_price", "-5")])
def test_line_amounts_must_be_sensible(api, payload, field, bad):
    item = line()
    item[field] = bad
    response = api.post(URL, payload(items=[item]), format="json")
    assert response.status_code == 400


# --- editing drafts ----------------------------------------------------


def test_editing_a_draft_replaces_lines_and_reprices(api, payload):
    invoice = create(api, payload())
    response = api.patch(
        detail(invoice["id"]), {"items": [line(qty="2"), line(price="500")]}, format="json"
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 2
    assert body["subtotal"] == "2500.00"
    assert body["vat_amount"] == "450.00"


def test_changing_the_date_reprices_with_the_rule_in_force(api, payload, vat_18):
    vat_18.effective_to = datetime.date(2026, 6, 30)
    vat_18.save()
    TaxRule.objects.create(
        tax_type="vat",
        rate=Decimal("0.16"),
        effective_from=datetime.date(2026, 7, 1),
        rule_version="test-vat-16",
    )
    invoice = create(api, payload(due_date=None))
    assert invoice["vat_amount"] == "180.00"

    response = api.patch(detail(invoice["id"]), {"issue_date": "2026-07-15"}, format="json")

    assert response.json()["vat_amount"] == "160.00"
    assert response.json()["items"][0]["rule_version"] == "test-vat-16"


def test_draft_can_be_deleted(api, payload):
    invoice = create(api, payload())
    assert api.delete(detail(invoice["id"])).status_code == 204


# --- lifecycle ---------------------------------------------------------


def test_issue_then_it_is_locked(api, payload):
    invoice = create(api, payload())
    response = api.post(f"{detail(invoice['id'])}issue/")
    assert response.status_code == 200
    assert response.json()["status"] == "issued"

    assert api.patch(detail(invoice["id"]), {"notes": "x"}, format="json").status_code == 400
    assert api.delete(detail(invoice["id"])).status_code == 400
    assert api.post(f"{detail(invoice['id'])}issue/").status_code == 400


def test_issue_reprices_if_the_rule_changed_since_the_draft(api, payload, vat_18):
    invoice = create(api, payload())
    vat_18.rate = Decimal("0.20")  # an admin corrected the rule before issuing
    vat_18.save()
    response = api.post(f"{detail(invoice['id'])}issue/")
    assert response.json()["vat_amount"] == "200.00"


def test_cancel_an_issued_invoice(api, payload):
    invoice = create(api, payload())
    api.post(f"{detail(invoice['id'])}issue/")
    response = api.post(f"{detail(invoice['id'])}cancel/")
    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"
    assert Invoice.objects.get(pk=invoice["id"]).status == Invoice.Status.CANCELLED


def test_drafts_are_deleted_not_cancelled(api, payload):
    invoice = create(api, payload())
    assert api.post(f"{detail(invoice['id'])}cancel/").status_code == 400


def test_status_cannot_be_set_directly(api, payload):
    invoice = create(api, payload(status="issued"))
    assert invoice["status"] == "draft"


def test_filter_by_status(api, payload):
    first = create(api, payload(invoice_number="A"))
    create(api, payload(invoice_number="B"))
    api.post(f"{detail(first['id'])}issue/")
    numbers = [i["invoice_number"] for i in api.get(f"{URL}?status=issued").json()["results"]]
    assert numbers == ["A"]


# --- roles -------------------------------------------------------------


def test_viewer_can_read_but_not_create_or_issue(client_for, owner, api, payload):
    invoice = create(api, payload())
    viewer = client_for(member_of(owner.company, Role.VIEWER).user, owner.company)
    assert viewer.get(detail(invoice["id"])).status_code == 200
    assert viewer.post(URL, payload(invoice_number="V1"), format="json").status_code == 403
    assert viewer.post(f"{detail(invoice['id'])}issue/").status_code == 403


def test_accountant_can_create(client_for, owner, payload):
    accountant = client_for(member_of(owner.company, Role.ACCOUNTANT).user, owner.company)
    assert accountant.post(URL, payload(), format="json").status_code == 201
