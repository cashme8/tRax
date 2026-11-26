from django.db.models import OuterRef, Subquery
from rest_framework import mixins, permissions, viewsets

from companies.models import Company, CompanyMember, TaxProfile
from companies.scoping import EDIT_ROLES, OWNER_ONLY, CompanyFromUrlMixin
from companies.serializers import (
    CompanyMemberSerializer,
    CompanySerializer,
    TaxProfileSerializer,
)


class CanEditCompany(permissions.BasePermission):
    message = "Only owners and accountants can edit the company."

    def has_object_permission(self, request, view, obj: Company) -> bool:
        return request.method in permissions.SAFE_METHODS or obj.my_role in EDIT_ROLES


class CompanyViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """
    GET    /api/companies/        companies you're an active member of (with your role)
    POST   /api/companies/        create one; you become its owner
    GET    /api/companies/<id>/   one of your companies (others → 404)
    PATCH  /api/companies/<id>/   owners and accountants only
    No DELETE: companies hold financial history. TODO(later): archive instead.
    """

    serializer_class = CompanySerializer
    permission_classes = [permissions.IsAuthenticated, CanEditCompany]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        mine = CompanyMember.objects.filter(
            company=OuterRef("pk"), user=self.request.user, is_active=True
        )
        return Company.objects.filter(
            members__user=self.request.user, members__is_active=True
        ).annotate(my_role=Subquery(mine.values("role")[:1]))


class CompanyMemberViewSet(
    CompanyFromUrlMixin,
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """
    GET    /api/companies/<id>/members/        any member can see the team
    POST   /api/companies/<id>/members/        owner adds an existing user: {email, role}
    PATCH  /api/companies/<id>/members/<mid>/  owner changes role or is_active
    No DELETE: deactivate (is_active=false) so the audit history stays intact.
    """

    serializer_class = CompanyMemberSerializer
    write_roles = OWNER_ONLY
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        return CompanyMember.objects.filter(company=self.company).select_related("user")


class TaxProfileViewSet(
    CompanyFromUrlMixin,
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    """
    GET    /api/companies/<id>/tax-profiles/   full history, newest first
    POST   /api/companies/<id>/tax-profiles/   record a change from a date (owner/accountant)
    Profiles are never edited or deleted, so past periods keep their original profile.
    """

    serializer_class = TaxProfileSerializer

    def get_queryset(self):
        return TaxProfile.objects.filter(company=self.company)

    def perform_create(self, serializer) -> None:
        serializer.save(company=self.company)
