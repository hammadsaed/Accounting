from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class ProfitPeriod(models.TextChoices):
    MONTHLY = "monthly", "Monthly"
    WEEKLY = "weekly", "Weekly"


class Investment(models.Model):
    name = models.CharField(max_length=120)
    amount = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal("0"))
    started_on = models.DateField()
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-started_on", "-id")

    def __str__(self) -> str:
        return f"{self.name} · {self.amount}"

    def clean(self):
        if self.amount is not None and self.amount <= 0:
            raise ValidationError({"amount": "Amount must be positive."})


class InvestmentProfit(models.Model):
    investment = models.ForeignKey(Investment, on_delete=models.CASCADE, related_name="profits")
    period_kind = models.CharField(max_length=10, choices=ProfitPeriod.choices, default=ProfitPeriod.MONTHLY)
    period_start = models.DateField()
    amount = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal("0"))
    notes = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-period_start", "-id")
        constraints = [
            models.UniqueConstraint(fields=("investment", "period_kind", "period_start"), name="investments_profit_unique_period"),
        ]

    def clean(self):
        if self.amount is None or self.amount == 0:
            raise ValidationError({"amount": "Amount must be non-zero."})
        if not self.period_start:
            raise ValidationError({"period_start": "Pick a period start."})
        if self.period_kind == ProfitPeriod.MONTHLY:
            self.period_start = self.period_start.replace(day=1)
        elif self.period_kind == ProfitPeriod.WEEKLY:
            self.period_start = self.period_start - timedelta(days=self.period_start.weekday())

    @property
    def period_label(self) -> str:
        if self.period_kind == ProfitPeriod.MONTHLY:
            return self.period_start.strftime("%B %Y")
        end = self.period_start + timedelta(days=6)
        return f"Week of {self.period_start:%b %-d, %Y} – {end:%b %-d, %Y}"

    def __str__(self) -> str:
        return f"{self.get_period_kind_display()} {self.period_start}: {self.amount}"
