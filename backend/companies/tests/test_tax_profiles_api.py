import datetime

import pytest

from companies.models import Role
from companies.tests.factories import CompanyFactory, TaxProfileFactory, member_of

pytestmark = pytest.mark.django_db


def url(company) -> str:
    return f"/api/companies/{company.pk}/tax-profiles/"


NEW_PROFILE = {
    "tax_regime": "real",
    "vat_registered": True,
    "filing_frequency": "quarterly",
    "effective_from": "2026-07-01",
}


def test_profile_in_force_depends_on_date():
    company = CompanyFactory()
    TaxProfileFactory(
        company=company, vat_registered=False, effective_from=datetime.date(2025, 1, 1)
    )
    TaxProfileFactory(
        company=company, vat_registered=True, effective_from=datetime.date(2026, 1, 1)
    )

    assert company.tax_profile_on(datetime.date(2024, 12, 31)) is None
    assert company.tax_profile_on(datetime.date(2025, 6, 1)).vat_registered is False
    assert company.tax_profile_on(datetime.date(2026, 3, 1)).vat_registered is True


@pytest.mark.parametrize(
    ("role", "expected"),
    [(Role.OWNER, 201), (Role.ACCOUNTANT, 201), (Role.VIEWER, 403)],
)
def test_who_can_add_a_tax_profile(client_for, role, expected):
    m = member_of(CompanyFactory(), role)
    assert client_for(m.user).post(url(m.company), NEW_PROFILE).status_code == expected


def test_history_is_listed_newest_first(client_for):
    m = member_of(CompanyFactory())
    TaxProfileFactory(company=m.company, effective_from=datetime.date(2025, 1, 1))
    TaxProfileFactory(company=m.company, effective_from=datetime.date(2026, 1, 1))
    dates = [p["effective_from"] for p in client_for(m.user).get(url(m.company)).json()["results"]]
    assert dates == ["2026-01-01", "2025-01-01"]


def test_two_profiles_cannot_start_on_same_day(client_for):
    m = member_of(CompanyFactory())
    TaxProfileFactory(company=m.company, effective_from=datetime.date(2026, 7, 1))
    response = client_for(m.user).post(url(m.company), NEW_PROFILE)
    assert response.status_code == 400


def test_outsider_cannot_see_or_add_tax_profiles(client_for):
    outsider = member_of(CompanyFactory())
    other = CompanyFactory()
    client = client_for(outsider.user)
    assert client.get(url(other)).status_code == 404
    assert client.post(url(other), NEW_PROFILE).status_code == 404
