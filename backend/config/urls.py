from django.contrib import admin
from django.urls import include, path

from config.views import health

urlpatterns = [
    # Django admin is for internal staff (e.g. maintaining tax rules), never
    # the business user's dashboard.
    path("admin/", admin.site.urls),
    path("api/health/", health, name="health"),
    path("api/auth/", include("accounts.urls")),
    path("api/", include("companies.urls")),
    path("api/", include("accounting.urls")),
    path("api/", include("audit.urls")),
    path("api/", include("tax_engine.urls")),
]
