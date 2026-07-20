from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Sum
from django.shortcuts import redirect, render

from apps.investments.models import Investment, InvestmentProfit

from .forms import CompanyForm, ManualMovementForm
from .models import Company


def _is_admin(user):
    from django.conf import settings

    return user.is_authenticated and (
        user.is_superuser or user.groups.filter(name=settings.ROLE_ADMIN).exists()
    )


@login_required
def company_detail(request):
    company = Company.load()
    movements = company.movements.select_related("created_by")[:100]
    invested_total = Investment.objects.aggregate(total=Sum("amount"))["total"] or 0
    accumulated_profit_total = InvestmentProfit.objects.aggregate(total=Sum("amount"))["total"] or 0
    return render(
        request,
        "company/detail.html",
        {
            "company": company,
            "movements": movements,
            "invested_total": invested_total,
            "accumulated_profit_total": accumulated_profit_total,
        },
    )


@login_required
@user_passes_test(_is_admin)
def company_edit(request):
    company = Company.load()
    if request.method == "POST":
        form = CompanyForm(request.POST, instance=company)
        if form.is_valid():
            form.save()
            messages.success(request, "Company details saved.")
            return redirect("company:detail")
    else:
        form = CompanyForm(instance=company)
    return render(request, "company/form.html", {"form": form, "company": company})


@login_required
@user_passes_test(_is_admin)
def movement_create(request):
    company = Company.load()
    if request.method == "POST":
        form = ManualMovementForm(request.POST)
        if form.is_valid():
            movement = form.save(commit=False)
            movement.company = company
            movement.created_by = request.user
            movement.save()
            messages.success(request, "Movement recorded.")
            return redirect("company:detail")
    else:
        form = ManualMovementForm()
    return render(request, "company/movement_form.html", {"form": form})
