"""
Direct tests of CompanyScopedViewSet, the base class every business-record
endpoint (invoices, expenses...) will use from Step 4. We plug it onto
CompanyMember here only because that's a company-owned table that exists today.
"""

import uuid

import pytest
from django.urls import include, path
from rest_framework import routers, serializers

from companies.models import CompanyMember, Role
from companies.scoping import CompanyScopedViewSet
from companies.tests.factories import CompanyFactory, member_of

pytestmark = [pytest.mark.django_db, pytest.mark.urls(__name__)]


class _RowSerializer(serializers.ModelSerializer):
    class Meta:
        model = CompanyMember
        fields = ["id", "role"]


class _RowViewSet(CompanyScopedViewSet):
    queryset = CompanyMember.objects.all()
    serializer_class = _RowSerializer


_router = routers.SimpleRouter()
_router.register("rows", _RowViewSet, basename="row")
urlpatterns = [path("", include(_router.urls))]  # used via pytest.mark.urls


def test_missing_company_header_is_a_400(client_for):
    m = member_of(CompanyFactory())
    response = client_for(m.user).get("/rows/")  # no company passed
    assert response.status_code == 400
    assert "X-Company-ID" in response.json()["detail"]


@pytest.mark.parametrize("bad_id", ["not-a-uuid", str(uuid.uuid4())])
def test_unknown_company_is_a_404(client_for, bad_id):
    m = member_of(CompanyFactory())
    client = client_for(m.user)
    client.credentials(HTTP_X_COMPANY_ID=bad_id)
    assert client.get("/rows/").status_code == 404


def test_header_for_a_company_you_dont_belong_to_is_a_404(client_for):
    a = member_of(CompanyFactory())
    company_b = CompanyFactory()
    member_of(company_b)
    assert client_for(a.user, company_b).get("/rows/").status_code == 404


def test_list_only_returns_rows_of_the_active_company(client_for):
    a = member_of(CompanyFactory())
    member_of(a.company, Role.VIEWER)
    member_of(CompanyFactory())  # another company's row

    ids = {r["id"] for r in client_for(a.user, a.company).get("/rows/").json()["results"]}

    assert ids == {str(m.pk) for m in CompanyMember.objects.filter(company=a.company)}


def test_cannot_fetch_another_companys_row_by_id(client_for):
    a = member_of(CompanyFactory())
    foreign_row = member_of(CompanyFactory())
    response = client_for(a.user, a.company).get(f"/rows/{foreign_row.pk}/")
    assert response.status_code == 404


@pytest.mark.parametrize(
    ("role", "read", "write"),
    [(Role.OWNER, 200, 200), (Role.ACCOUNTANT, 200, 200), (Role.VIEWER, 200, 403)],
)
def test_roles_for_reading_and_writing(client_for, role, read, write):
    m = member_of(CompanyFactory(), role)
    client = client_for(m.user, m.company)
    assert client.get(f"/rows/{m.pk}/").status_code == read
    assert client.patch(f"/rows/{m.pk}/", {"role": role}).status_code == write


def test_unauthenticated_is_a_401(api_client):
    company = CompanyFactory()
    api_client.credentials(HTTP_X_COMPANY_ID=str(company.pk))
    assert api_client.get("/rows/").status_code == 401
