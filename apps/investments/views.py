import csv
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import InvestmentForm, InvestmentProfitForm
from .models import Investment, InvestmentProfit, ProfitPeriod
from .services import (
    investment_rows,
    investment_summary,
    profit_export_rows,
    profit_totals_by_month,
)

ZERO = Decimal("0")


def _is_admin(user):
    return user.is_authenticated and (user.is_superuser or user.groups.filter(name=settings.ROLE_ADMIN).exists())


def _form_error_text(form) -> str:
    return "; ".join(f"{k}: {', '.join(v)}" for k, v in form.errors.items())


def _profit_percent(amount: Decimal, principal: Decimal) -> Decimal:
    if not principal:
        return ZERO
    return (amount / principal) * Decimal("100")


def _csv_response(filename: str, rows) -> HttpResponse:
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    writer = csv.writer(response)
    writer.writerow(["investment", "period_type", "period_start", "period_label", "amount", "notes"])
    for row in rows:
        writer.writerow([
            row.investment.name,
            row.get_period_kind_display(),
            row.period_start.isoformat(),
            row.period_label,
            f"{row.amount:.3f}",
            row.notes,
        ])
    return response


@login_required
def investment_list(request):
    investments = list(investment_rows())
    for inv in investments:
        inv.current_value = inv.amount + inv.total_profit
    raw = request.GET.get("edit", "")
    edit_pk = int(raw) if raw.isdigit() else 0
    edit_target = next((x for x in investments if x.pk == edit_pk), None)
    return render(request, "investments/list.html", {
        "investments": investments,
        "edit_pk": edit_target.pk if edit_target else None,
        "edit_form": InvestmentForm(instance=edit_target, form_id="form-investment-edit") if edit_target else None,
        "add_form": InvestmentForm(form_id="form-investment-add"),
        "summary": investment_summary(),
        "monthly_profit_totals": profit_totals_by_month(limit=None),
        "can_manage": _is_admin(request.user),
    })


@require_POST
@login_required
@user_passes_test(_is_admin)
def investment_create(request):
    form = InvestmentForm(request.POST)
    if form.is_valid():
        obj = form.save(commit=False); obj.created_by = request.user; obj.save()
        messages.success(request, "Investment recorded and company cash reduced.")
    else:
        messages.error(request, f"Could not add investment ({_form_error_text(form)}).")
    return redirect("investments:list")


@require_POST
@login_required
@user_passes_test(_is_admin)
def investment_update(request, pk: int):
    obj = get_object_or_404(Investment, pk=pk)
    form = InvestmentForm(request.POST, instance=obj)
    if form.is_valid():
        form.save(); messages.success(request, "Investment updated.")
    else:
        messages.error(request, f"Could not update investment ({_form_error_text(form)}).")
    return redirect("investments:list")


@require_POST
@login_required
@user_passes_test(_is_admin)
def investment_delete(request, pk: int):
    obj = get_object_or_404(Investment, pk=pk)
    label = obj.name; obj.delete()
    messages.success(request, f"Deleted investment ({label}).")
    return redirect("investments:list")


@login_required
def investment_detail(request, pk: int):
    investment = get_object_or_404(investment_rows(), pk=pk)
    kind = request.GET.get("kind", "all")
    profits = list(investment.profits.all())
    if kind in {ProfitPeriod.MONTHLY, ProfitPeriod.WEEKLY}:
        profits = [row for row in profits if row.period_kind == kind]
    for row in profits:
        row.profit_percent = _profit_percent(row.amount, investment.amount)
    raw = request.GET.get("edit", "")
    edit_pk = int(raw) if raw.isdigit() else 0
    edit_target = next((row for row in profits if row.pk == edit_pk), None) if edit_pk else None
    return render(request, "investments/detail.html", {
        "investment": investment,
        "profits": profits,
        "kind": kind,
        "tabs": [("all", "All"), (ProfitPeriod.MONTHLY, "Monthly"), (ProfitPeriod.WEEKLY, "Weekly")],
        "edit_pk": edit_target.pk if edit_target else None,
        "edit_form": InvestmentProfitForm(instance=edit_target, form_id="form-profit-edit") if edit_target else None,
        "add_form": InvestmentProfitForm(form_id="form-profit-add"),
        "total_profit": investment.total_profit,
        "current_value": investment.amount + investment.total_profit,
        "monthly_profit_totals": profit_totals_by_month(investment=investment, limit=None),
        "can_manage": _is_admin(request.user),
    })


@login_required
def profit_export(request):
    return _csv_response("investment-profit-history.csv", profit_export_rows())


@login_required
def investment_profit_export(request, pk: int):
    investment = get_object_or_404(Investment, pk=pk)
    return _csv_response(
        f"investment-{investment.pk}-profit-history.csv",
        profit_export_rows(investment=investment),
    )


@require_POST
@login_required
@user_passes_test(_is_admin)
def profit_create(request, pk: int):
    investment = get_object_or_404(Investment, pk=pk)
    form = InvestmentProfitForm(request.POST)
    if form.is_valid():
        obj = form.save(commit=False); obj.investment = investment; obj.created_by = request.user; obj.save()
        messages.success(request, "Profit row recorded.")
    else:
        messages.error(request, f"Could not add profit row ({_form_error_text(form)}).")
    return redirect("investments:detail", pk=investment.pk)


@require_POST
@login_required
@user_passes_test(_is_admin)
def profit_update(request, pk: int):
    obj = get_object_or_404(InvestmentProfit.objects.select_related("investment"), pk=pk)
    form = InvestmentProfitForm(request.POST, instance=obj)
    if form.is_valid():
        form.save(); messages.success(request, "Profit row updated.")
    else:
        messages.error(request, f"Could not update profit row ({_form_error_text(form)}).")
    return redirect("investments:detail", pk=obj.investment_id)


@require_POST
@login_required
@user_passes_test(_is_admin)
def profit_delete(request, pk: int):
    obj = get_object_or_404(InvestmentProfit.objects.select_related("investment"), pk=pk)
    investment_id = obj.investment_id; obj.delete()
    messages.success(request, "Profit row deleted.")
    return redirect("investments:detail", pk=investment_id)
