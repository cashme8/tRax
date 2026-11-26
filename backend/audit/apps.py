from django.apps import AppConfig


class AuditConfig(AppConfig):
    """Permanent record of who changed what and when (RRA audits reach back years)."""

    name = "audit"
