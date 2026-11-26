import pytest

from accounting.tests.factories import CustomerFactory
from companies.models import Role
from companies.tests.factories import CompanyFactory, member_of

pytestmark = pytest.mark.django_db

URL = "/api/tax/vat-summary/"


def test_summary_for_a_period(api, owner):
    customer = CustomerFactory(company=owner.company)
    invoice = api.post(
        "/api/invoices/",
        {
            "invoice_number": "INV-1",
            "customer": str(customer.pk),
            "issue_date": "2026-03-10",
            "items": [
                {
                    "description": "x",
                    "quantity": "1",
                    "unit_price": "1000",
                    "tax_treatment": "standard",
                }
            ],
        },
        format="json",
    ).json()
    api.post(f"/api/invoices/{invoice['id']}/issue/")

    response = api.get(URL, {"start": "2026-03-01", "end": "2026-03-31"})

    assert response.status_code == 200
    body = response.json()
    assert body["output_vat"] == "180.00"
    assert body["net_payable"] == "180.00"
    assert body["output_by_treatment"]["standard"]["count"] == 1


@pytest.mark.parametrize(
    "params",
    [
        {},
        {"start": "2026-03-01"},
        {"start": "bad", "end": "2026-03-31"},
        {"start": "2026-04-01", "end": "2026-03-01"},
    ],
)
def test_bad_periods_are_400(api, params):
    assert api.get(URL, params).status_code == 400


def test_viewers_can_see_the_summary(client_for, owner):
    viewer = member_of(owner.company, Role.VIEWER)
    response = client_for(viewer.user, owner.company).get(
        URL, {"start": "2026-03-01", "end": "2026-03-31"}
    )
    assert response.status_code == 200


def test_outsiders_get_404(client_for, owner):
    outsider = member_of(CompanyFactory())
    response = client_for(outsider.user, owner.company).get(
        URL, {"start": "2026-03-01", "end": "2026-03-31"}
    )
    assert response.status_code == 404
