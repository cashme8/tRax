from django.apps import AppConfig


class TaxEngineConfig(AppConfig):
    """
    Versioned tax rules and every official tax calculation. Rates live in the
    TaxRule table (data), never in code, so a new finance law is a data change
    and old periods still calculate with the rules that applied back then.
    """

    name = "tax_engine"
