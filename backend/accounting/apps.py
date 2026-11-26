from django.apps import AppConfig


class AccountingConfig(AppConfig):
    """
    Customers, suppliers, invoices, purchases, expenses, payments.
    TODO(later milestone): double-entry ledger (chart of accounts, journals, trial balance).
    """

    name = "accounting"
