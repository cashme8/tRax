from django.urls import path
from rest_framework.routers import DefaultRouter

from companies.views import CompanyMemberViewSet, CompanyViewSet, TaxProfileViewSet

router = DefaultRouter()
router.register("companies", CompanyViewSet, basename="company")

members = CompanyMemberViewSet.as_view({"get": "list", "post": "create"})
member_detail = CompanyMemberViewSet.as_view({"patch": "partial_update"})
tax_profiles = TaxProfileViewSet.as_view({"get": "list", "post": "create"})

urlpatterns = [
    *router.urls,
    path("companies/<uuid:company_pk>/members/", members, name="company-members"),
    path(
        "companies/<uuid:company_pk>/members/<uuid:pk>/",
        member_detail,
        name="company-member-detail",
    ),
    path("companies/<uuid:company_pk>/tax-profiles/", tax_profiles, name="company-tax-profiles"),
]
