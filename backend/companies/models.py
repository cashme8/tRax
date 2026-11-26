from datetime import date

from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone

from common.models import TimeStampedModel

# Rwandan TINs are 9 digits. TODO: confirm the exact format/checksum rules with RRA.
tin_validator = RegexValidator(r"^\d{9}$", "A TIN must be exactly 9 digits.")


class Company(TimeStampedModel):
    class BusinessType(models.TextChoices):
        SOLE_PROPRIETOR = "sole_proprietor", "Sole proprietor"
        LIMITED_COMPANY = "limited_company", "Limited company"
        PARTNERSHIP = "partnership", "Partnership"
        COOPERATIVE = "cooperative", "Cooperative"
        NGO = "ngo", "NGO / non-profit"
        OTHER = "other", "Other"

    legal_name = models.CharField(max_length=255)
    tin = models.CharField("TIN", max_length=9, unique=True, validators=[tin_validator])
    business_type = models.CharField(max_length=30, choices=BusinessType.choices)
    industry = models.CharField(max_length=120, blank=True)

    class Meta:
        verbose_name_plural = "companies"
        ordering = ["legal_name"]

    def __str__(self) -> str:
        return f"{self.legal_name} ({self.tin})"

    def tax_profile_on(self, on_date: date | None = None) -> "TaxProfile | None":
        """The tax profile in force on a date (default: today)."""
        on_date = on_date or timezone.localdate()
        return (
            self.tax_profiles.filter(effective_from__lte=on_date)
            .order_by("-effective_from")
            .first()
        )


class CompanyOwnedModel(TimeStampedModel):
    """
    Base for every business record (invoices, expenses...). The `company` link
    is what CompanyScopedViewSet filters on, so every record is tenant-scoped.
    PROTECT: a company with records can never be deleted by accident.
    """

    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="+")

    class Meta:
        abstract = True


class Role(models.TextChoices):
    OWNER = "owner", "Owner"
    ACCOUNTANT = "accountant", "Accountant"
    VIEWER = "viewer", "Viewer"


class CompanyMember(TimeStampedModel):
    """Links a user to a company with a role. One accountant can serve many companies."""

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="members")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memberships"
    )
    role = models.CharField(max_length=20, choices=Role.choices)
    # Deactivate rather than delete, so history (who did what) still points somewhere.
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["company", "user"], name="unique_member_per_company")
        ]
        ordering = ["company", "user__email"]

    def __str__(self) -> str:
        return f"{self.user} — {self.role} at {self.company.legal_name}"


class TaxProfile(TimeStampedModel):
    """
    How a company is taxed, from a given date. Kept as history (a new row per change)
    so past periods are still calculated with the profile that applied back then.
    """

    class Regime(models.TextChoices):
        # TODO: confirm regime names and turnover thresholds with RRA.
        REAL = "real", "Real regime"
        LUMP_SUM = "lump_sum", "Lump-sum regime"
        FLAT = "flat", "Flat tax regime"

    class FilingFrequency(models.TextChoices):
        MONTHLY = "monthly", "Monthly"
        QUARTERLY = "quarterly", "Quarterly"

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="tax_profiles")
    tax_regime = models.CharField(max_length=20, choices=Regime.choices)
    vat_registered = models.BooleanField(default=False)
    filing_frequency = models.CharField(max_length=20, choices=FilingFrequency.choices)
    effective_from = models.DateField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["company", "effective_from"], name="one_tax_profile_per_start_date"
            )
        ]
        ordering = ["company", "-effective_from"]  # newest first

    def __str__(self) -> str:
        return f"{self.company.legal_name}: {self.tax_regime} from {self.effective_from}"
