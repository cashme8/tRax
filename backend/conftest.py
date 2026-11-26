"""Shared pytest fixtures for the whole backend. Apps add their own in <app>/tests/."""

import pytest
from rest_framework.test import APIClient


@pytest.fixture
def api_client() -> APIClient:
    """An unauthenticated DRF test client."""
    return APIClient()


@pytest.fixture
def client_for():
    """
    client_for(user) → an APIClient logged in as that user.
    client_for(user, company) → also sends that company in the X-Company-ID header.
    """

    def make(user, company=None) -> APIClient:
        client = APIClient()
        client.force_authenticate(user=user)
        if company is not None:
            client.credentials(HTTP_X_COMPANY_ID=str(company.pk))
        return client

    return make


@pytest.fixture
def vat_18(db):
    """
    Replace whatever VAT rules exist (e.g. the seeded one) with a known
    18% rule from 2001, so tests don't depend on seed data that admins may edit.
    """
    import datetime
    from decimal import Decimal

    from tax_engine.models import TaxRule

    TaxRule.objects.all().delete()
    return TaxRule.objects.create(
        tax_type="vat",
        rate=Decimal("0.1800"),
        effective_from=datetime.date(2001, 1, 1),
        rule_version="test-vat-18",
    )
