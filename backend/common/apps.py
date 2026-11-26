from django.apps import AppConfig


class CommonConfig(AppConfig):
    """Shared building blocks (base models, later the company-scoped viewset). No tables."""

    name = "common"
