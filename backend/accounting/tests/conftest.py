import datetime

import pytest

from companies.models import Role
from companies.tests.factories import CompanyFactory, TaxProfileFactory, member_of


@pytest.fixture
def owner(vat_18):
    """Owner of a VAT-registered company (tax profile from 2020), with an 18% VAT rule."""
    company = CompanyFactory()
    TaxProfileFactory(
        company=company, vat_registered=True, effective_from=datetime.date(2020, 1, 1)
    )
    return member_of(company, Role.OWNER)


@pytest.fixture
def api(owner, client_for):
    """API client for `owner`, sending their company in X-Company-ID."""
    return client_for(owner.user, owner.company)
