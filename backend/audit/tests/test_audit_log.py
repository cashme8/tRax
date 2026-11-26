"""Every create, update and delete of a financial record leaves a permanent log line."""

import pytest

from accounting.models import Customer, Invoice
from accounting.tests.factories import CustomerFactory, InvoiceFactory, SupplierFactory
from accounts.tests.factories import UserFactory
from audit.models import AuditLog
from companies.models import Role
from companies.tests.factories import CompanyFactory, member_of

pytestmark = pytest.mark.django_db


def logs_for(obj) -> list[AuditLog]:
    return list(AuditLog.objects.filter(entity_id=obj.pk).order_by("created_at"))


def only_log(**filters) -> AuditLog:
    return AuditLog.objects.get(**filters)


# --- create / update / delete -------------------------------------------


def test_create_is_logged_with_who_where_what(api, owner):
    response = api.post("/api/customers/", {"name": "Kigali Hotel"}, format="json")
    customer = Customer.objects.get(pk=response.json()["id"])

    log = only_log(entity_id=customer.pk)
    assert log.action == "create"
    assert log.user == owner.user
    assert log.user_email == owner.user.email
    assert log.company == owner.company
    assert log.entity_type == "accounting.customer"
    assert log.entity_label == "Kigali Hotel"
    assert log.changes["name"] == [None, "Kigali Hotel"]


def test_update_logs_only_what_changed(api, owner):
    customer = CustomerFactory(company=owner.company, name="Old name", email="a@x.rw")
    api.patch(f"/api/customers/{customer.pk}/", {"name": "New name"}, format="json")

    log = only_log(entity_id=customer.pk, action="update")
    assert log.changes == {"name": ["Old name", "New name"]}


def test_update_that_changes_nothing_is_not_logged(api, owner):
    customer = CustomerFactory(company=owner.company, name="Same")
    api.patch(f"/api/customers/{customer.pk}/", {"name": "Same"}, format="json")
    assert logs_for(customer) == []


def test_delete_is_logged_with_the_old_values(api, owner):
    customer = CustomerFactory(company=owner.company, name="Gone Ltd")
    customer_id = customer.pk
    api.delete(f"/api/customers/{customer_id}/")

    log = only_log(entity_id=customer_id)
    assert log.action == "delete"
    assert log.entity_label == "Gone Ltd"
    assert log.changes["name"] == ["Gone Ltd", None]


def test_refused_delete_leaves_no_log(api, owner):
    customer = CustomerFactory(company=owner.company)
    InvoiceFactory(company=owner.company, customer=customer)
    assert api.delete(f"/api/customers/{customer.pk}/").status_code == 400
    assert logs_for(customer) == []


def test_rejected_input_leaves_no_log(api):
    api.post("/api/customers/", {"name": ""}, format="json")
    assert not AuditLog.objects.exists()


def test_money_is_logged_as_exact_strings(api, owner):
    supplier = SupplierFactory(company=owner.company)
    body = api.post(
        "/api/purchases/",
        {"supplier": str(supplier.pk), "purchase_date": "2026-03-05", "amount_excl_vat": "1000"},
        format="json",
    ).json()
    changes = only_log(entity_id=body["id"]).changes
    assert changes["amount_excl_vat"] == [None, "1000.00"]
    assert changes["vat_amount"] == [None, "180.00"]


# --- invoices ------------------------------------------------------------


@pytest.fixture
def draft(api, owner) -> dict:
    customer = CustomerFactory(company=owner.company)
    return api.post(
        "/api/invoices/",
        {
            "invoice_number": "INV-1",
            "customer": str(customer.pk),
            "issue_date": "2026-03-10",
            "items": [
                {
                    "description": "Chairs",
                    "quantity": "2",
                    "unit_price": "1000",
                    "tax_treatment": "standard",
                }
            ],
        },
        format="json",
    ).json()


def test_invoice_log_includes_its_lines(api, draft):
    api.patch(
        f"/api/invoices/{draft['id']}/",
        {
            "items": [
                {
                    "description": "Chairs",
                    "quantity": "5",
                    "unit_price": "1000",
                    "tax_treatment": "standard",
                }
            ]
        },
        format="json",
    )
    log = only_log(entity_id=draft["id"], action="update")
    old_items, new_items = log.changes["items"]
    assert old_items[0]["quantity"] == "2.000"
    assert new_items[0]["quantity"] == "5.000"
    assert log.changes["total_amount"] == ["2360.00", "5900.00"]


def test_issue_and_cancel_are_logged_as_their_own_actions(api, draft):
    api.post(f"/api/invoices/{draft['id']}/issue/")
    api.post(f"/api/invoices/{draft['id']}/cancel/")

    actions = [log.action for log in logs_for(Invoice(pk=draft["id"]))]
    assert actions == ["create", "issue", "cancel"]
    issue = only_log(entity_id=draft["id"], action="issue")
    assert issue.changes["status"] == ["draft", "issued"]


def test_deleting_a_draft_is_logged(api, draft):
    api.delete(f"/api/invoices/{draft['id']}/")
    log = only_log(entity_id=draft["id"], action="delete")
    assert log.changes["invoice_number"] == ["INV-1", None]
    assert log.changes["items"][0][0]["description"] == "Chairs"


# --- company settings are audited too ------------------------------------


def test_company_member_and_tax_profile_changes_are_logged(client_for, vat_18):
    user = UserFactory()
    client = client_for(user)
    company = client.post(
        "/api/companies/",
        {
            "legal_name": "Inzozi Ltd",
            "tin": "123456789",
            "business_type": "limited_company",
            "tax_profile": {
                "tax_regime": "real",
                "vat_registered": True,
                "filing_frequency": "monthly",
                "effective_from": "2026-01-01",
            },
        },
        format="json",
    ).json()
    invitee = UserFactory()
    client.post(
        f"/api/companies/{company['id']}/members/", {"email": invitee.email, "role": "viewer"}
    )
    client.post(
        f"/api/companies/{company['id']}/tax-profiles/",
        {
            "tax_regime": "real",
            "vat_registered": False,
            "filing_frequency": "monthly",
            "effective_from": "2026-07-01",
        },
    )

    types = set(
        AuditLog.objects.filter(company_id=company["id"]).values_list("entity_type", flat=True)
    )
    assert types == {"companies.company", "companies.companymember", "companies.taxprofile"}


# --- the log itself is permanent -----------------------------------------


def test_log_rows_cannot_be_edited_or_deleted(api):
    api.post("/api/customers/", {"name": "X"}, format="json")
    log = AuditLog.objects.get()
    log.action = "delete"
    with pytest.raises(RuntimeError):
        log.save()
    with pytest.raises(RuntimeError):
        log.delete()


# --- reading the log through the API -------------------------------------


def test_owner_reads_own_company_history_only(api, owner):
    api.post("/api/customers/", {"name": "Mine"}, format="json")
    other = CompanyFactory()
    other_owner = member_of(other)
    from rest_framework.test import APIClient

    other_client = APIClient()
    other_client.force_authenticate(other_owner.user)
    other_client.credentials(HTTP_X_COMPANY_ID=str(other.pk))
    other_client.post("/api/customers/", {"name": "Theirs"}, format="json")

    labels = [row["entity_label"] for row in api.get("/api/audit-log/").json()["results"]]
    assert labels == ["Mine"]


def test_filter_history_by_record(api, owner):
    a = api.post("/api/customers/", {"name": "A"}, format="json").json()
    api.post("/api/customers/", {"name": "B"}, format="json")
    rows = api.get(f"/api/audit-log/?entity_id={a['id']}").json()["results"]
    assert [r["entity_label"] for r in rows] == ["A"]
    assert api.get("/api/audit-log/?entity_id=not-a-uuid").json()["results"] == []


@pytest.mark.parametrize(("role", "expected"), [(Role.ACCOUNTANT, 200), (Role.VIEWER, 403)])
def test_who_can_read_the_log(client_for, owner, role, expected):
    m = member_of(owner.company, role)
    assert client_for(m.user, owner.company).get("/api/audit-log/").status_code == expected


def test_log_is_read_only_through_the_api(api):
    assert api.post("/api/audit-log/", {}, format="json").status_code == 405
