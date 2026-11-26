"""
Multi-tenant scoping: the one place that decides which company a request is
about and whether the user may touch it. Every company-owned endpoint builds
on these classes, so no endpoint can forget the check.

Two ways a request names its company:
  * CompanyScopedViewSet   — business records (invoices, expenses...): the
                             frontend sends the active company in the
                             `X-Company-ID` header.
  * CompanyFromUrlMixin    — company settings (members, tax profiles):
                             the company id is in the URL,
                             e.g. /api/companies/<id>/members/.

If the user isn't an active member, the answer is 404 "not found" — never
403 — so outsiders can't even learn that a company or record exists.
"""

import uuid
from functools import cached_property

from django.db.models import ProtectedError
from rest_framework import exceptions, permissions, serializers, viewsets

from companies.models import Company, CompanyMember, Role

READ_ROLES = (Role.OWNER, Role.ACCOUNTANT, Role.VIEWER)
EDIT_ROLES = (Role.OWNER, Role.ACCOUNTANT)
OWNER_ONLY = (Role.OWNER,)


def get_active_membership(user, company_id) -> CompanyMember:
    """The user's active membership in a company, or 404."""
    try:
        company_uuid = uuid.UUID(str(company_id))
    except ValueError:
        raise exceptions.NotFound("Company not found.") from None
    membership = (
        CompanyMember.objects.select_related("company")
        .filter(company_id=company_uuid, user=user, is_active=True)
        .first()
    )
    if membership is None:
        raise exceptions.NotFound("Company not found.")
    return membership


class HasCompanyRole(permissions.BasePermission):
    """Reads need a role in view.read_roles; writes need one in view.write_roles."""

    message = "Your role in this company does not allow this action."

    def has_permission(self, request, view) -> bool:
        role = view.membership.role  # raises 404 for non-members
        allowed = (
            view.read_roles if request.method in permissions.SAFE_METHODS else view.write_roles
        )
        return role in allowed


class CompanyContextMixin:
    """Gives a view `self.membership` and `self.company`, and enforces roles."""

    permission_classes = [permissions.IsAuthenticated, HasCompanyRole]
    read_roles: tuple[str, ...] = READ_ROLES
    write_roles: tuple[str, ...] = EDIT_ROLES

    def get_company_id(self) -> str:
        raise NotImplementedError

    @cached_property
    def membership(self) -> CompanyMember:
        return get_active_membership(self.request.user, self.get_company_id())

    @property
    def company(self) -> Company:
        return self.membership.company

    def get_serializer_context(self) -> dict:
        # Serializers use this to check that linked records (e.g. an invoice's
        # customer) belong to the same company.
        return {**super().get_serializer_context(), "company": self.company}


class CompanyFromUrlMixin(CompanyContextMixin):
    company_url_kwarg = "company_pk"

    def get_company_id(self) -> str:
        return self.kwargs[self.company_url_kwarg]


class CompanyScopedViewSet(CompanyContextMixin, viewsets.ModelViewSet):
    """
    Base for every company-owned business record. Subclasses set `queryset`
    and `serializer_class`; this class guarantees:
      * list/detail only ever show the active company's rows;
      * new rows are always saved to the active company (the client can't choose);
      * viewers can read, owners/accountants can write.
    """

    COMPANY_HEADER = "X-Company-ID"

    def get_company_id(self) -> str:
        company_id = self.request.headers.get(self.COMPANY_HEADER)
        if not company_id:
            raise exceptions.ValidationError(
                {"detail": f"The {self.COMPANY_HEADER} header is required."}
            )
        return company_id

    def get_queryset(self):
        return super().get_queryset().filter(company=self.company)

    def perform_create(self, serializer) -> None:
        serializer.save(company=self.company)

    def perform_destroy(self, instance) -> None:
        try:
            instance.delete()
        except ProtectedError:
            raise exceptions.ValidationError(
                {"detail": "This record is used by other records and can't be deleted."}
            ) from None


class CompanyScopedPrimaryKeyRelatedField(serializers.PrimaryKeyRelatedField):
    """
    A link to another record (e.g. an invoice's customer) that only accepts
    records of the active company. Another company's id is reported as
    "does not exist", so its existence isn't revealed.
    """

    def get_queryset(self):
        return super().get_queryset().filter(company=self.context["company"])
