"""Read-only aggregations for the dashboard and monthly report.

Everything in here is computed lazily from the existing app models — no
denormalised storage, so the numbers are always current.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from django.db.models import Sum

from apps.accounts.models import Person
from apps.company.models import Company
from apps.earnings.models import Allocation, ReceiverKind
from apps.investments.services import investment_summary
from apps.periods.models import Month
from apps.transfers.models import Transfer, TransferStatus

ZERO = Decimal("0")


@dataclass
class PersonStanding:
    """One person's position in a single month."""
    person: Person
    received: Decimal
    owns: Decimal
    paid_out: Decimal
    paid_in: Decimal

    @property
    def imbalance(self) -> Decimal:
        """Positive: still holding others' money. Negative: still owed money."""
        return self.received - self.owns - self.paid_out + self.paid_in


@dataclass
class CompanyStanding:
    received: Decimal
    owns: Decimal
    paid_in: Decimal
    paid_out: Decimal

    @property
    def imbalance(self) -> Decimal:
        return self.received - self.owns - self.paid_out + self.paid_in


def _current_month() -> Optional[Month]:
    return Month.objects.order_by("-year", "-month").first()


def _payments_into(month: Month, *, to_company: bool = False, person: Person | None = None) -> Decimal:
    qs = month.transfers.filter(payments__isnull=False)
    if to_company:
        qs = qs.filter(to_kind="company")
    elif person is not None:
        qs = qs.filter(to_kind="person", to_person=person)
    return qs.aggregate(t=Sum("payments__amount"))["t"] or ZERO


def _payments_out_of(month: Month, *, from_company: bool = False, person: Person | None = None) -> Decimal:
    qs = month.transfers.filter(payments__isnull=False)
    if from_company:
        qs = qs.filter(from_kind="company")
    elif person is not None:
        qs = qs.filter(from_kind="person", from_person=person)
    return qs.aggregate(t=Sum("payments__amount"))["t"] or ZERO


def person_standings(month: Month) -> list[PersonStanding]:
    standings = []
    for person in Person.objects.filter(is_active=True).order_by("name"):
        received = (
            month.earnings.filter(receiver_kind=ReceiverKind.PERSON, receiver_person=person)
            .aggregate(t=Sum("amount"))["t"] or ZERO
        )
        owns = (
            Allocation.objects.filter(earning__month=month, person=person)
            .aggregate(t=Sum("amount"))["t"] or ZERO
        )
        standings.append(PersonStanding(
            person=person,
            received=received,
            owns=owns,
            paid_out=_payments_out_of(month, person=person),
            paid_in=_payments_into(month, person=person),
        ))
    return standings


def company_standing(month: Month) -> CompanyStanding:
    received = (
        month.earnings.filter(receiver_kind=ReceiverKind.COMPANY)
        .aggregate(t=Sum("amount"))["t"] or ZERO
    )
    owns = (
        Allocation.objects.filter(earning__month=month, is_company=True)
        .aggregate(t=Sum("amount"))["t"] or ZERO
    )
    return CompanyStanding(
        received=received,
        owns=owns,
        paid_in=_payments_into(month, to_company=True),
        paid_out=_payments_out_of(month, from_company=True),
    )


@dataclass(frozen=True)
class EntityColumn:
    key: str
    label: str
    is_company: bool


def entity_income_by_month(*, limit: int | None = 24) -> dict:
    """Pivot of allocations: months (newest first) × entities (Company + people).

    Each cell is the entity's share of that month's earnings according to the
    split rule snapshot stored on the allocation rows. Independent of who
    actually received the cash, so the totals always reconcile to the gross
    earnings of the month even before transfers are settled.
    """
    rows = (
        Allocation.objects.filter(earning__month__isnull=False)
        .values("earning__month_id", "person_id", "is_company")
        .annotate(total=Sum("amount"))
    )

    cells: dict[tuple[int, str], Decimal] = {}
    month_ids: set[int] = set()
    person_ids: set[int] = set()
    has_company = False
    for r in rows:
        mid = r["earning__month_id"]
        month_ids.add(mid)
        if r["is_company"]:
            has_company = True
            key = "company"
        else:
            person_ids.add(r["person_id"])
            key = f"person:{r['person_id']}"
        cells[(mid, key)] = (r["total"] or ZERO)

    months = list(Month.objects.filter(id__in=month_ids).order_by("-year", "-month"))
    if limit:
        months = months[:limit]
    persons = {p.id: p for p in Person.objects.filter(id__in=person_ids)}

    columns: list[EntityColumn] = []
    if has_company:
        columns.append(EntityColumn(key="company", label="Company", is_company=True))
    for pid in sorted(person_ids, key=lambda i: persons[i].name.lower()):
        columns.append(EntityColumn(key=f"person:{pid}", label=persons[pid].name, is_company=False))

    rows_out = []
    party_totals = {col.key: ZERO for col in columns}
    grand_total = ZERO
    for m in months:
        month_total = ZERO
        cell_values = []
        for col in columns:
            v = cells.get((m.id, col.key), ZERO)
            cell_values.append(v)
            month_total += v
            party_totals[col.key] += v
        grand_total += month_total
        rows_out.append({"month": m, "cells": cell_values, "total": month_total})

    return {
        "columns": columns,
        "rows": rows_out,
        "party_totals": [party_totals[c.key] for c in columns],
        "grand_total": grand_total,
    }


def dashboard_context() -> dict:
    company = Company.load()
    month = _current_month()

    pending = Transfer.objects.filter(
        status__in=[TransferStatus.PENDING, TransferStatus.PARTIAL]
    )
    pending_total = sum((t.amount_remaining for t in pending), ZERO)

    ctx = {
        "company": company,
        "company_balance": company.current_balance,
        "month": month,
        "pending_count": pending.count(),
        "pending_total": pending_total,
        "pending_transfers": pending.select_related("month", "from_person", "to_person")[:10],
        "entity_income": entity_income_by_month(),
        "investment_summary": investment_summary(),
    }

    if month is None:
        return ctx

    earnings_total = month.earnings.aggregate(t=Sum("amount"))["t"] or ZERO
    expenses_total = month.expenses.aggregate(t=Sum("amount"))["t"] or ZERO
    company_share = (
        Allocation.objects.filter(earning__month=month, is_company=True)
        .aggregate(t=Sum("amount"))["t"] or ZERO
    )

    ctx.update(
        earnings_total=earnings_total,
        expenses_total=expenses_total,
        company_share=company_share,
        company_net=company_share - expenses_total,
        person_standings=person_standings(month),
        company_standing=company_standing(month),
        recent_earnings=month.earnings.select_related("earner", "receiver_person")[:5],
        recent_expenses=month.expenses.select_related("category")[:5],
    )
    return ctx


def monthly_report(month: Month) -> dict:
    """Detailed per-month breakdown matching the template in the spec."""
    earnings = list(month.earnings.select_related("earner", "receiver_person"))
    rule = getattr(month, "split_rule", None)
    expenses = list(month.expenses.select_related("category"))
    transfers = list(month.transfers.select_related("from_person", "to_person"))

    earnings_by_earner: dict[str, Decimal] = {}
    for e in earnings:
        earnings_by_earner[e.earner.name] = earnings_by_earner.get(e.earner.name, ZERO) + e.amount

    expenses_by_category: dict[str, Decimal] = {}
    for x in expenses:
        name = x.category.name if x.category_id else "Uncategorized"
        expenses_by_category[name] = expenses_by_category.get(name, ZERO) + x.amount

    earnings_total = sum(earnings_by_earner.values(), ZERO)
    expenses_total = sum(expenses_by_category.values(), ZERO)

    standings = person_standings(month)
    company = company_standing(month)
    company_net = company.owns - expenses_total

    return {
        "month": month,
        "rule": rule,
        "earnings": earnings,
        "earnings_by_earner": earnings_by_earner,
        "earnings_total": earnings_total,
        "expenses": expenses,
        "expenses_by_category": expenses_by_category,
        "expenses_total": expenses_total,
        "transfers": transfers,
        "person_standings": standings,
        "company_standing": company,
        "company_net": company_net,
    }
