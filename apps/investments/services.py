from __future__ import annotations

from decimal import Decimal

from django.db.models import Count, DecimalField, Sum, Value
from django.db.models.functions import Coalesce, TruncMonth

from .models import Investment, InvestmentProfit

ZERO = Decimal("0")


def investment_rows():
    return Investment.objects.annotate(
        total_profit=Coalesce(
            Sum("profits__amount"),
            Value(ZERO),
            output_field=DecimalField(max_digits=14, decimal_places=3),
        )
    ).order_by("-started_on", "-id")


def investment_summary() -> dict:
    invested_total = Investment.objects.aggregate(t=Sum("amount"))["t"] or ZERO
    accumulated_profit_total = InvestmentProfit.objects.aggregate(t=Sum("amount"))["t"] or ZERO
    return {
        "investment_count": Investment.objects.count(),
        "invested_total": invested_total,
        "accumulated_profit_total": accumulated_profit_total,
        "tracked_value_total": invested_total + accumulated_profit_total,
        "recent_profits": list(
            InvestmentProfit.objects.select_related("investment")[:5]
        ),
    }


def profit_totals_by_month(*, investment: Investment | None = None, limit: int | None = 24):
    qs = InvestmentProfit.objects.all()
    if investment is not None:
        qs = qs.filter(investment=investment)
    rows = list(
        qs.annotate(bucket=TruncMonth("period_start"))
        .values("bucket")
        .annotate(total=Sum("amount"), entries=Count("id"))
        .order_by("-bucket")
    )
    if limit is not None:
        rows = rows[:limit]
    for row in rows:
        row["label"] = row["bucket"].strftime("%B %Y")
    return rows


def profit_export_rows(*, investment: Investment | None = None):
    qs = InvestmentProfit.objects.select_related("investment").order_by(
        "investment__name", "-period_start", "-id"
    )
    if investment is not None:
        qs = qs.filter(investment=investment)
    return list(qs)
