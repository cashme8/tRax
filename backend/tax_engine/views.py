import datetime

from rest_framework import exceptions, generics
from rest_framework.response import Response

from companies.scoping import CompanyFromHeaderMixin
from tax_engine.services import calculate_vat


def _parse_date(value: str | None, name: str) -> datetime.date:
    if not value:
        raise exceptions.ValidationError({name: "Required (YYYY-MM-DD)."})
    try:
        return datetime.date.fromisoformat(value)
    except ValueError:
        raise exceptions.ValidationError({name: "Use the format YYYY-MM-DD."}) from None


class VatSummaryView(CompanyFromHeaderMixin, generics.GenericAPIView):
    """
    GET /api/tax/vat-summary/?start=2026-03-01&end=2026-03-31
    The active company's VAT position for the period, computed by the server.
    Read-only, so every role (including viewers) can see it.
    """

    def get(self, request):
        start = _parse_date(request.query_params.get("start"), "start")
        end = _parse_date(request.query_params.get("end"), "end")
        if start > end:
            raise exceptions.ValidationError({"end": "Must be on or after start."})
        return Response(calculate_vat(self.company, start, end).as_dict())
