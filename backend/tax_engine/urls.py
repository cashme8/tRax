from django.urls import path

from tax_engine.views import VatSummaryView

urlpatterns = [
    path("tax/vat-summary/", VatSummaryView.as_view(), name="vat-summary"),
]
