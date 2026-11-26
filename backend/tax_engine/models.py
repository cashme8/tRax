from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q

from common.models import TimeStampedModel


class TaxType(models.TextChoices):
    VAT = "vat", "VAT — standard rate"
    # Later: PAYE bands, RSSB, withholding (15% / 3%), corporate income tax...


class TaxTreatment(models.TextChoices):
    """
    How VAT applies to a sale or purchase line.
      standard    — VAT at the standard rate from TaxRule.
      zero_rated  — taxable, but at 0% (e.g. exports); input VAT still claimable.
      exempt      — outside VAT by law; no VAT charged.
      non_taxable — not a supply for VAT at all (e.g. some fees, salaries).
    Zero-rated, exempt and non-taxable lines carry no VAT by definition.
    """

    STANDARD = "standard", "Standard-rated"
    ZERO_RATED = "zero_rated", "Zero-rated"
    EXEMPT = "exempt", "Exempt"
    NON_TAXABLE = "non_taxable", "Non-taxable"


class TaxRule(TimeStampedModel):
    """One rate for one tax type, valid from `effective_from` to `effective_to` (inclusive)."""

    tax_type = models.CharField(max_length=30, choices=TaxType.choices)
    # Stored as a fraction: 0.1800 means 18%.
    rate = models.DecimalField(
        max_digits=7,
        decimal_places=4,
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("1"))],
    )
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True, help_text="Blank = still in force.")
    rule_version = models.CharField(
        max_length=50, help_text="Stable label stored with every calculation, e.g. vat-std-v1."
    )
    description = models.CharField(max_length=255, blank=True)
    is_verified = models.BooleanField(
        default=False, help_text="Checked against the law by a tax advisor."
    )
    source_note = models.TextField(
        blank=True, help_text="Legal source, or what still needs checking."
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["tax_type", "rule_version"], name="unique_rule_version_per_tax_type"
            ),
            models.CheckConstraint(
                condition=Q(effective_to__isnull=True)
                | Q(effective_to__gte=models.F("effective_from")),
                name="tax_rule_dates_in_order",
            ),
        ]
        ordering = ["tax_type", "-effective_from"]

    def __str__(self) -> str:
        end = self.effective_to or "…"
        percent = f"{self.rate * 100:.2f}%"
        return f"{self.tax_type} {percent} ({self.effective_from} → {end}) [{self.rule_version}]"

    def clean(self) -> None:
        """Two rules for the same tax must never be in force on the same day."""
        if self.effective_to and self.effective_to < self.effective_from:
            raise ValidationError({"effective_to": "Must be on or after effective_from."})
        overlapping = TaxRule.objects.filter(tax_type=self.tax_type).exclude(pk=self.pk)
        # Another rule overlaps if it starts on/before our end and ends on/after our start.
        if self.effective_to:
            overlapping = overlapping.filter(effective_from__lte=self.effective_to)
        overlapping = overlapping.filter(
            Q(effective_to__isnull=True) | Q(effective_to__gte=self.effective_from)
        )
        if overlapping.exists():
            raise ValidationError(
                "This date range overlaps another rule for the same tax. "
                "End the old rule the day before this one starts."
            )
