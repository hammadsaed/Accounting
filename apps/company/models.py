"""Company singleton and ledger of cash movements.

The company's *cash balance* is the opening balance plus the signed sum of
real cash movements. Automatically generated ``default_profit`` rows stay in
the ledger for tracking/reporting, but they do not count as cash on hand.
"""
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Sum


class Company(models.Model):
    """Single-row table representing the company itself."""

    name = models.CharField(max_length=120, default="Company")
    opening_balance = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal("0"))
    opening_balance_date = models.DateField(null=True, blank=True)
    bank_name = models.CharField(max_length=120, blank=True)
    bank_account_title = models.CharField(max_length=120, blank=True)
    bank_account_number = models.CharField(max_length=64, blank=True)
    bank_iban = models.CharField("Bank IBAN", max_length=64, blank=True)
    default_investment_enabled = models.BooleanField(default=False)
    default_investment_rate_mode = models.CharField(
        max_length=10,
        choices=(("annual", "Annual %"), ("monthly", "Monthly %")),
        default="annual",
    )
    default_investment_rate_percent = models.DecimalField(
        max_digits=7,
        decimal_places=4,
        null=True,
        blank=True,
    )
    default_investment_started_on = models.DateField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Company"
        verbose_name_plural = "Company"

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        # Pin to a single row.
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls) -> "Company":
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    @property
    def current_balance(self) -> Decimal:
        movements_total = self.movements.exclude(kind=MovementKind.DEFAULT_PROFIT).aggregate(
            total=Sum("amount")
        )["total"] or Decimal("0")
        return self.opening_balance + movements_total


class MovementKind(models.TextChoices):
    DEPOSIT = "deposit", "Deposit"
    WITHDRAWAL = "withdrawal", "Withdrawal"
    ADJUSTMENT = "adjustment", "Adjustment"
    EXPENSE = "expense", "Expense"
    RECEIPT = "receipt", "Receipt from settlement"
    PAYOUT = "payout", "Payout to person"
    INVESTMENT = "investment", "Investment"
    DEFAULT_PROFIT = "default_profit", "Default investment profit"


class BalanceMovement(models.Model):
    """Signed cash movement against the company account.

    Most positive ``amount`` values increase the cash balance; a negative one
    decreases it. ``DEFAULT_PROFIT`` rows are tracked in the ledger but do not
    count toward ``Company.current_balance``. ``source_*`` fields optionally
    point at the originating object (e.g. an ``Expense``) so the movement page
    can link back to it.
    """

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="movements")
    kind = models.CharField(max_length=20, choices=MovementKind.choices)
    amount = models.DecimalField(max_digits=14, decimal_places=3)
    happened_on = models.DateField()
    description = models.CharField(max_length=255, blank=True)

    # Optional pointer back to the row that produced this movement.
    source_app = models.CharField(max_length=40, blank=True)
    source_model = models.CharField(max_length=40, blank=True)
    source_id = models.PositiveIntegerField(null=True, blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-happened_on", "-id")
        indexes = [
            models.Index(fields=("happened_on",)),
            models.Index(fields=("kind",)),
            models.Index(fields=("source_app", "source_model", "source_id")),
        ]

    def __str__(self) -> str:
        return f"{self.get_kind_display()} {self.amount} on {self.happened_on}"
