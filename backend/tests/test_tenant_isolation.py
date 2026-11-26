"""
Milestone 1 acceptance test: user A cannot see or touch company B's data.

Company B gets a full, realistic data set created through the API by its
owner (so audit rows exist too). User A — owner of company A, with data of
their own — then tries every way in: lists, detail URLs, edits, deletes,
custom actions, the X-Company-ID header, company URLs, linking to B's
records from A's own, and the VAT summary and audit log.
"""

from decimal import Decimal

import pytest

from accounts.tests.factories import UserFactory
from companies.models import CompanyMember, Role

pytestmark = pytest.mark.django_db

PERIOD = {"start": "2026-03-01", "end": "2026-03-31"}


def make_company(client, name, tin) -> dict:
    response = client.post(
        "/api/companies/",
        {
            "legal_name": name,
            "tin": tin,
            "business_type": "limited_company",
            "tax_profile": {
                "tax_regime": "real",
                "vat_registered": True,
                "filing_frequency": "monthly",
                "effective_from": "2026-01-01",
            },
        },
        format="json",
    )
    assert response.status_code == 201, response.json()
    return response.json()


def populate(client) -> dict:
    """Create one of everything in the client's active company; return their ids."""

    def post(url, data):
        response = client.post(url, data, format="json")
        assert response.status_code == 201, (url, response.json())
        return response.json()

    customer = post("/api/customers/", {"name": "Customer"})
    supplier = post("/api/suppliers/", {"name": "Supplier", "vat_registered": True})
    invoice = post(
        "/api/invoices/",
        {
            "invoice_number": "INV-1",
            "customer": customer["id"],
            "issue_date": "2026-03-10",
            "items": [
                {
                    "description": "Goods",
                    "quantity": "10",
                    "unit_price": "100000",
                    "tax_treatment": "standard",
                }
            ],
        },
    )
    assert client.post(f"/api/invoices/{invoice['id']}/issue/").status_code == 200
    draft = post(
        "/api/invoices/",
        {
            "invoice_number": "INV-2",
            "customer": customer["id"],
            "issue_date": "2026-03-11",
            "items": [
                {"description": "x", "quantity": "1", "unit_price": "1", "tax_treatment": "exempt"}
            ],
        },
    )
    payment = post(
        "/api/payments/",
        {
            "invoice": invoice["id"],
            "amount": "1000",
            "payment_date": "2026-03-15",
            "payment_method": "bank_transfer",
        },
    )
    purchase = post(
        "/api/purchases/",
        {"supplier": supplier["id"], "purchase_date": "2026-03-12", "amount_excl_vat": "200000"},
    )
    expense = post(
        "/api/expenses/",
        {"expense_date": "2026-03-13", "category": "rent", "amount_excl_vat": "50000"},
    )
    return {
        "customers": customer["id"],
        "suppliers": supplier["id"],
        "invoices": invoice["id"],
        "draft": draft["id"],
        "payments": payment["id"],
        "purchases": purchase["id"],
        "expenses": expense["id"],
    }


@pytest.fixture
def world(client_for, vat_18):
    """Two companies, each with an owner and a full data set."""
    a_user, b_user = UserFactory(), UserFactory()
    company_a = make_company(client_for(a_user), "A Ltd", "111111111")
    company_b = make_company(client_for(b_user), "B Ltd", "222222222")
    a = client_for(a_user)
    a.credentials(HTTP_X_COMPANY_ID=company_a["id"])
    b = client_for(b_user)
    b.credentials(HTTP_X_COMPANY_ID=company_b["id"])
    a_data = populate(a)
    b_data = populate(b)
    b_member = CompanyMember.objects.get(company_id=company_b["id"], user=b_user)
    return {
        "a": a,
        "a_user": a_user,
        "company_a": company_a,
        "a_data": a_data,
        "company_b": company_b,
        "b_data": b_data,
        "b_user": b_user,
        "b_member": b_member,
        "client_for": client_for,
    }


COLLECTIONS = ["customers", "suppliers", "invoices", "payments", "purchases", "expenses"]


def ids(response) -> set[str]:
    assert response.status_code == 200, response.json()
    return {row["id"] for row in response.json()["results"]}


# --- lists ------------------------------------------------------------------


@pytest.mark.parametrize("collection", COLLECTIONS)
def test_a_lists_only_own_records(world, collection):
    listed = ids(world["a"].get(f"/api/{collection}/"))
    assert world["b_data"][collection] not in listed
    assert world["a_data"][collection] in listed  # and A does see their own


def test_a_lists_only_own_companies(world):
    names = [c["legal_name"] for c in world["a"].get("/api/companies/").json()["results"]]
    assert names == ["A Ltd"]


# --- detail / edit / delete ---------------------------------------------------


@pytest.mark.parametrize("collection", COLLECTIONS)
def test_a_cannot_read_edit_or_delete_bs_records(world, collection):
    url = f"/api/{collection}/{world['b_data'][collection]}/"
    a = world["a"]
    assert a.get(url).status_code == 404
    assert a.patch(url, {"name": "hacked", "notes": "hacked"}, format="json").status_code in (
        404,
        405,  # payments can't be edited by anyone
    )
    assert a.delete(url).status_code == 404


def test_bs_records_are_untouched_after_the_attempts(world, client_for):
    for collection in COLLECTIONS:
        world["a"].delete(f"/api/{collection}/{world['b_data'][collection]}/")
    b = client_for(world["b_user"])
    b.credentials(HTTP_X_COMPANY_ID=world["company_b"]["id"])
    for collection in COLLECTIONS:
        assert b.get(f"/api/{collection}/{world['b_data'][collection]}/").status_code == 200


@pytest.mark.parametrize("action", ["issue", "cancel"])
def test_a_cannot_issue_or_cancel_bs_invoices(world, action):
    for key in ("invoices", "draft"):
        url = f"/api/invoices/{world['b_data'][key]}/{action}/"
        assert world["a"].post(url).status_code == 404


# --- switching company via the header ----------------------------------------


@pytest.mark.parametrize(
    "url",
    [f"/api/{c}/" for c in COLLECTIONS] + ["/api/audit-log/", "/api/tax/vat-summary/"],
)
def test_a_cannot_switch_to_b_with_the_header(world, url):
    a = world["client_for"](world["a_user"], None)
    a.credentials(HTTP_X_COMPANY_ID=world["company_b"]["id"])
    assert a.get(url, PERIOD).status_code == 404


# --- company-level URLs --------------------------------------------------------


@pytest.mark.parametrize("suffix", ["", "members/", "tax-profiles/"])
def test_a_cannot_open_company_b_urls(world, suffix):
    url = f"/api/companies/{world['company_b']['id']}/{suffix}"
    assert world["a"].get(url).status_code == 404
    assert world["a"].post(url, {}, format="json").status_code in (404, 405)


def test_a_cannot_change_bs_members(world):
    url = f"/api/companies/{world['company_b']['id']}/members/{world['b_member'].pk}/"
    assert world["a"].patch(url, {"role": "viewer"}, format="json").status_code == 404
    world["b_member"].refresh_from_db()
    assert world["b_member"].role == Role.OWNER


def test_a_cannot_join_b(world):
    url = f"/api/companies/{world['company_b']['id']}/members/"
    response = world["a"].post(url, {"email": world["a_user"].email, "role": "owner"})
    assert response.status_code == 404
    assert not CompanyMember.objects.filter(
        company_id=world["company_b"]["id"], user=world["a_user"]
    ).exists()


# --- linking A's records to B's ---------------------------------------------------


def test_a_cannot_link_own_records_to_bs(world):
    a, b = world["a"], world["b_data"]
    line = {"description": "x", "quantity": "1", "unit_price": "1", "tax_treatment": "standard"}
    attempts = {
        "/api/invoices/": (
            {
                "invoice_number": "X",
                "customer": b["customers"],
                "issue_date": "2026-03-10",
                "items": [line],
            },
            "customer",
        ),
        "/api/payments/": (
            {
                "invoice": b["invoices"],
                "amount": "1",
                "payment_date": "2026-03-20",
                "payment_method": "cash",
            },
            "invoice",
        ),
        "/api/purchases/": (
            {"supplier": b["suppliers"], "purchase_date": "2026-03-10", "amount_excl_vat": "1"},
            "supplier",
        ),
        "/api/expenses/": (
            {
                "supplier": b["suppliers"],
                "expense_date": "2026-03-10",
                "category": "rent",
                "amount_excl_vat": "1",
            },
            "supplier",
        ),
    }
    for url, (payload, field) in attempts.items():
        response = a.post(url, payload, format="json")
        assert response.status_code == 400, url
        assert field in response.json(), url


def test_create_ignores_a_company_named_in_the_body(world):
    response = world["a"].post(
        "/api/customers/", {"name": "Sneaky", "company": world["company_b"]["id"]}, format="json"
    )
    assert response.status_code == 201
    b = world["client_for"](world["b_user"])
    b.credentials(HTTP_X_COMPANY_ID=world["company_b"]["id"])
    assert "Sneaky" not in {c["name"] for c in b.get("/api/customers/").json()["results"]}


# --- VAT summary and audit log ------------------------------------------------------


def test_a_vat_summary_counts_only_as_own_records(world):
    summary = world["a"].get("/api/tax/vat-summary/", PERIOD).json()
    # A's own data only: 1,000,000 sale → 180,000; purchases 200,000 + expense 50,000 → 45,000.
    assert Decimal(summary["output_vat"]) == Decimal("180000")
    assert Decimal(summary["input_vat"]) == Decimal("45000")


def test_a_audit_log_contains_only_as_history(world):
    rows = world["a"].get("/api/audit-log/").json()["results"]
    entity_ids = {row["entity_id"] for row in rows}
    assert not entity_ids & set(world["b_data"].values())
    assert world["company_b"]["id"] not in entity_ids
    assert world["a_data"]["invoices"] in entity_ids


# --- membership changes take effect immediately -------------------------------------


def test_removed_member_loses_access_to_everything(world, client_for):
    # B's owner invites A's owner as accountant...
    b = client_for(world["b_user"])
    members = f"/api/companies/{world['company_b']['id']}/members/"
    response = b.post(members, {"email": world["a_user"].email, "role": "accountant"})
    assert response.status_code == 201, response.json()
    joined = response.json()
    insider = client_for(world["a_user"])
    insider.credentials(HTTP_X_COMPANY_ID=world["company_b"]["id"])
    assert insider.get("/api/invoices/").status_code == 200

    # ...then deactivates them.
    b.patch(f"{members}{joined['id']}/", {"is_active": False})
    for collection in COLLECTIONS:
        assert insider.get(f"/api/{collection}/").status_code == 404
    assert insider.get(f"/api/companies/{world['company_b']['id']}/").status_code == 404


# --- logged-out visitors -------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [f"/api/{c}/" for c in COLLECTIONS]
    + ["/api/companies/", "/api/audit-log/", "/api/tax/vat-summary/", "/api/auth/me/"],
)
def test_logged_out_requests_are_refused(api_client, world, url):
    api_client.credentials(HTTP_X_COMPANY_ID=world["company_b"]["id"])
    assert api_client.get(url, PERIOD).status_code == 401
