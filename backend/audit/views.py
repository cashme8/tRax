import uuid

from rest_framework import mixins, viewsets

from audit.models import AuditLog
from audit.serializers import AuditLogSerializer
from companies.scoping import EDIT_ROLES, CompanyFromHeaderMixin


class AuditLogViewSet(
    CompanyFromHeaderMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """
    GET /api/audit-log/   the active company's history, newest first (read-only).
    Filters: ?entity_type=accounting.invoice  ?entity_id=<uuid>
    Owners and accountants only.
    """

    serializer_class = AuditLogSerializer
    read_roles = EDIT_ROLES

    def get_queryset(self):
        queryset = AuditLog.objects.filter(company=self.company)
        params = self.request.query_params
        if entity_type := params.get("entity_type"):
            queryset = queryset.filter(entity_type=entity_type)
        if entity_id := params.get("entity_id"):
            try:
                queryset = queryset.filter(entity_id=uuid.UUID(entity_id))
            except ValueError:
                return queryset.none()
        return queryset
