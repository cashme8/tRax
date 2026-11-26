"""
Structural guarantee: every API endpoint either
  * is built on the company-scoping base (CompanyContextMixin), or
  * is on the short, reviewed allowlist below.

If someone adds an endpoint and forgets tenant scoping, this test fails.
To add to the allowlist you must explain why the endpoint is safe.
"""

from django.urls import URLPattern, URLResolver, get_resolver

from companies.scoping import CompanyContextMixin

# view class name → why it doesn't need company scoping
ALLOWED_UNSCOPED = {
    "health": "Public liveness check; returns no data.",
    "RegisterView": "Creates the caller's own account.",
    "LoginView": "Exchanges the caller's own credentials for tokens.",
    "TokenRefreshView": "Exchanges the caller's own refresh token.",
    "MeView": "Returns only the caller's own user.",
    "CompanyViewSet": (
        "Lists/creates companies. Its queryset is filtered to the caller's active "
        "memberships (tested in companies/tests and tests/test_tenant_isolation.py)."
    ),
    "APIRootView": "DRF's browsable index of URLs; returns no data.",
}


def _api_views(patterns, prefix=""):
    for pattern in patterns:
        route = prefix + str(pattern.pattern)
        if isinstance(pattern, URLResolver):
            yield from _api_views(pattern.url_patterns, route)
        elif isinstance(pattern, URLPattern) and route.startswith("api/"):
            view = pattern.callback
            cls = getattr(view, "cls", None) or getattr(view, "view_class", None)
            yield route, cls, getattr(view, "__name__", "")


def test_every_api_endpoint_is_company_scoped_or_allowlisted():
    unscoped = []
    for route, cls, func_name in _api_views(get_resolver().url_patterns):
        name = cls.__name__ if cls else func_name
        if cls is not None and issubclass(cls, CompanyContextMixin):
            continue
        if name in ALLOWED_UNSCOPED:
            continue
        unscoped.append(f"{route} → {name}")
    assert not unscoped, (
        "These endpoints aren't company-scoped. Build them on CompanyScopedViewSet / "
        "CompanyFromHeaderMixin / CompanyFromUrlMixin, or add them to ALLOWED_UNSCOPED "
        "with a reason:\n  " + "\n  ".join(unscoped)
    )


def test_the_check_actually_sees_the_scoped_endpoints():
    """Guard against the test above passing because it found nothing."""
    scoped = {
        cls.__name__
        for _, cls, _ in _api_views(get_resolver().url_patterns)
        if cls is not None and issubclass(cls, CompanyContextMixin)
    }
    assert {
        "CustomerViewSet",
        "SupplierViewSet",
        "InvoiceViewSet",
        "PaymentViewSet",
        "PurchaseViewSet",
        "ExpenseViewSet",
        "CompanyMemberViewSet",
        "TaxProfileViewSet",
        "AuditLogViewSet",
        "VatSummaryView",
    } <= scoped
