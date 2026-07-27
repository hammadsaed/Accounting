from __future__ import annotations

from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Sum
from django.utils import timezone

from .models import BalanceMovement, Company, MovementKind

AUTO_SOURCE_APP = "company"
AUTO_SOURCE_MODEL = "default_investment_profit"
ZERO = Decimal("0")
HUNDRED = Decimal("100")
MONEY_STEP = Decimal("0.001")


def _auto_movements(company: Company):
    return company.movements.filter(source_app=AUTO_SOURCE_APP, source_model=AUTO_SOURCE_MODEL)


def _non_default_movements(company: Company):
    return company.movements.exclude(source_app=AUTO_SOURCE_APP, source_model=AUTO_SOURCE_MODEL)


def _monthly_anniversary(anchor: date, months_elapsed: int) -> date:
    month_index = anchor.month - 1 + months_elapsed
    year = anchor.year + (month_index // 12)
    month = (month_index % 12) + 1
    day = min(anchor.day, monthrange(year, month)[1])
    return date(year, month, day)


def _daily_rate(company: Company, cycle_days: int) -> Decimal:
    rate = (company.default_investment_rate_percent or ZERO) / HUNDRED
    if company.default_investment_rate_mode == "monthly":
        return rate / Decimal(cycle_days)
    return rate / Decimal("365")


def default_investment_summary(company: Company) -> dict:
    auto = _auto_movements(company)
    total_profit = auto.aggregate(total=Sum("amount"))["total"] or ZERO
    current_idle_cash = company.current_balance if company.current_balance > ZERO else ZERO
    return {
        "enabled": company.default_investment_enabled,
        "rate_mode": company.get_default_investment_rate_mode_display(),
        "rate_percent": company.default_investment_rate_percent or ZERO,
        "start_date": company.default_investment_started_on,
        "posted_months": auto.count(),
        "total_profit": total_profit,
        "current_idle_cash": current_idle_cash,
    }


def rebuild_default_investment(company: Company | None = None) -> int:
    company = company or Company.load()
    _auto_movements(company).delete()

    if not company.default_investment_enabled:
        return 0
    if not company.default_investment_started_on:
        return 0
    if not company.default_investment_rate_percent or company.default_investment_rate_percent <= 0:
        return 0

    start = company.default_investment_started_on
    today = timezone.localdate()
    if start > today:
        return 0

    cash = company.opening_balance
    daily_changes: dict = {}
    for happened_on, amount in _non_default_movements(company).order_by("happened_on", "id").values_list("happened_on", "amount"):
        if happened_on < start:
            cash += amount
        else:
            daily_changes[happened_on] = daily_changes.get(happened_on, ZERO) + amount

    rows: list[BalanceMovement] = []
    period_start = start
    months_elapsed = 1
    while True:
        post_date = _monthly_anniversary(start, months_elapsed)
        if post_date > today:
            break

        cycle_days = (post_date - period_start).days
        cycle_profit = ZERO
        day = period_start
        while day < post_date:
            cash += daily_changes.get(day, ZERO)
            if cash > ZERO:
                cycle_profit += (cash * _daily_rate(company, cycle_days)).quantize(
                    MONEY_STEP,
                    rounding=ROUND_HALF_UP,
                )
            day += timedelta(days=1)

        if cycle_profit:
            rows.append(
                BalanceMovement(
                    company=company,
                    kind=MovementKind.DEFAULT_PROFIT,
                    amount=cycle_profit,
                    happened_on=post_date,
                    description="Default investment profit",
                    source_app=AUTO_SOURCE_APP,
                    source_model=AUTO_SOURCE_MODEL,
                )
            )
            cash += cycle_profit

        period_start = post_date
        months_elapsed += 1

    BalanceMovement.objects.bulk_create(rows)
    return len(rows)