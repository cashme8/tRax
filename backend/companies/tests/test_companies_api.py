"""Companies: creating, listing, editing — and that nobody sees someone else's company."""

import pytest

from accounts.tests.factories import UserFactory
from companies.models import CompanyMember, Role, TaxProfile
from companies.tests.factories import CompanyFactory, TaxProfileFactory, member_of

pytestmark = pytest.mark.django_db

URL = "/api/companies/"


def detail(company) -> str:
    return f"{URL}{company.pk}/"


def new_company_payload(**overrides) -> dict:
    payload = {
        "legal_name": "Inzozi Traders Ltd",
        "tin": "123456789",
        "business_type": "limited_company",
        "industry": "Retail",
        "tax_profile": {
            "tax_regime": "real",
            "vat_registered": True,
            "filing_frequency": "monthly",
            "effective_from": "2026-01-01",
        },
    }
    payload.update(overrides)
    return payload


# --- create -------------------------------------------------------------


def test_creator_becomes_owner_and_tax_profile_is_saved(client_for):
    user = UserFactory()
    response = client_for(user).post(URL, new_company_payload(), format="json")

    assert response.status_code == 201, response.json()
    body = response.json()
    assert body["my_role"] == "owner"
    assert body["current_tax_profile"]["vat_registered"] is True
    membership = CompanyMember.objects.get(company_id=body["id"])
    assert membership.user == user and membership.role == Role.OWNER
    assert TaxProfile.objects.filter(company_id=body["id"]).count() == 1


def test_create_requires_tax_profile(client_for):
    payload = new_company_payload()
    del payload["tax_profile"]
    response = client_for(UserFactory()).post(URL, payload, format="json")
    assert response.status_code == 400
    assert "tax_profile" in response.json()


@pytest.mark.parametrize("bad_tin", ["12345", "1234567890", "12345678a"])
def test_tin_must_be_nine_digits(client_for, bad_tin):
    response = client_for(UserFactory()).post(URL, new_company_payload(tin=bad_tin), format="json")
    assert response.status_code == 400
    assert "tin" in response.json()


def test_tin_must_be_unique(client_for):
    CompanyFactory(tin="123456789")
    response = client_for(UserFactory()).post(URL, new_company_payload(), format="json")
    assert response.status_code == 400
    assert "tin" in response.json()


def test_create_requires_login(api_client):
    assert api_client.post(URL, new_company_payload(), format="json").status_code == 401


# --- isolation ----------------------------------------------------------


def test_user_a_lists_only_company_a(client_for):
    a = member_of(CompanyFactory(legal_name="A Ltd"))
    member_of(CompanyFactory(legal_name="B Ltd"))

    response = client_for(a.user).get(URL)

    assert response.status_code == 200
    names = [c["legal_name"] for c in response.json()["results"]]
    assert names == ["A Ltd"]


def test_user_a_cannot_open_company_b(client_for):
    a = member_of(CompanyFactory())
    company_b = CompanyFactory()
    assert client_for(a.user).get(detail(company_b)).status_code == 404


def test_user_a_cannot_edit_company_b(client_for):
    a = member_of(CompanyFactory())
    company_b = CompanyFactory(legal_name="B Ltd")
    response = client_for(a.user).patch(detail(company_b), {"legal_name": "Hacked"}, format="json")
    assert response.status_code == 404
    company_b.refresh_from_db()
    assert company_b.legal_name == "B Ltd"


def test_deactivated_member_loses_access(client_for):
    m = member_of(CompanyFactory(), is_active=False)
    client = client_for(m.user)
    assert client.get(URL).json()["results"] == []
    assert client.get(detail(m.company)).status_code == 404


def test_each_member_sees_their_own_role(client_for):
    company = CompanyFactory()
    viewer = member_of(company, Role.VIEWER)
    response = client_for(viewer.user).get(detail(company))
    assert response.json()["my_role"] == "viewer"


# --- editing by role ----------------------------------------------------


@pytest.mark.parametrize(
    ("role", "expected"),
    [(Role.OWNER, 200), (Role.ACCOUNTANT, 200), (Role.VIEWER, 403)],
)
def test_who_can_edit_company(client_for, role, expected):
    m = member_of(CompanyFactory(), role)
    response = client_for(m.user).patch(detail(m.company), {"industry": "Hotels"}, format="json")
    assert response.status_code == expected


def test_tax_profile_cannot_be_overwritten_through_company(client_for):
    m = member_of(CompanyFactory())
    TaxProfileFactory(company=m.company)
    response = client_for(m.user).patch(
        detail(m.company),
        {"tax_profile": new_company_payload()["tax_profile"]},
        format="json",
    )
    assert response.status_code == 400


def test_companies_cannot_be_deleted(client_for):
    m = member_of(CompanyFactory())
    assert client_for(m.user).delete(detail(m.company)).status_code == 405
