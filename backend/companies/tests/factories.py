import datetime

import factory

from accounts.tests.factories import UserFactory
from companies.models import Company, CompanyMember, Role, TaxProfile


class CompanyFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Company

    legal_name = factory.Sequence(lambda n: f"Company {n} Ltd")
    tin = factory.Sequence(lambda n: f"{100000000 + n}")
    business_type = Company.BusinessType.LIMITED_COMPANY
    industry = "Retail"


class CompanyMemberFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = CompanyMember

    company = factory.SubFactory(CompanyFactory)
    user = factory.SubFactory(UserFactory)
    role = Role.OWNER


class TaxProfileFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = TaxProfile

    company = factory.SubFactory(CompanyFactory)
    tax_regime = TaxProfile.Regime.REAL
    vat_registered = True
    filing_frequency = TaxProfile.FilingFrequency.MONTHLY
    effective_from = datetime.date(2026, 1, 1)


def member_of(company, role=Role.OWNER, **kwargs) -> CompanyMember:
    """A new user who belongs to `company` with `role`. Returns the membership."""
    return CompanyMemberFactory(company=company, role=role, **kwargs)
