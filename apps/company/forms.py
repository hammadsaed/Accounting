from django import forms
from django.utils import timezone

from .models import BalanceMovement, Company, MovementKind


class CompanyForm(forms.ModelForm):
    class Meta:
        model = Company
        fields = (
            "name",
            "opening_balance",
            "opening_balance_date",
            "bank_name",
            "bank_account_title",
            "bank_account_number",
            "bank_iban",
        )
        widgets = {
            "opening_balance_date": forms.DateInput(attrs={"type": "date"}),
        }


class ManualMovementForm(forms.ModelForm):
    """Form for the three movement kinds that admins enter by hand."""

    kind = forms.ChoiceField(
        choices=[
            (MovementKind.DEPOSIT, "Deposit"),
            (MovementKind.WITHDRAWAL, "Withdrawal"),
            (MovementKind.ADJUSTMENT, "Adjustment"),
        ]
    )

    class Meta:
        model = BalanceMovement
        fields = ("kind", "amount", "happened_on", "description")
        widgets = {
            "happened_on": forms.DateInput(attrs={"type": "date"}),
        }

    def clean(self):
        cleaned = super().clean()
        kind = cleaned.get("kind")
        amount = cleaned.get("amount")
        if amount is None or kind is None:
            return cleaned
        # Withdrawals are stored as negative amounts; deposits as positive.
        # Adjustments accept either sign as the user enters them.
        if kind == MovementKind.WITHDRAWAL and amount > 0:
            cleaned["amount"] = -amount
        if kind == MovementKind.DEPOSIT and amount < 0:
            cleaned["amount"] = -amount
        return cleaned


class DefaultInvestmentForm(forms.ModelForm):
    class Meta:
        model = Company
        fields = (
            "default_investment_enabled",
            "default_investment_rate_mode",
            "default_investment_rate_percent",
            "default_investment_started_on",
        )
        widgets = {
            "default_investment_started_on": forms.DateInput(attrs={"type": "date"}),
        }
        labels = {
            "default_investment_enabled": "Enable default investment",
            "default_investment_rate_mode": "Rate type",
            "default_investment_rate_percent": "Profit rate %",
            "default_investment_started_on": "Start date",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.is_bound and not self.instance.default_investment_started_on:
            self.initial.setdefault("default_investment_started_on", timezone.localdate())
        input_cls = "block w-full rounded-md border-slate-300 text-sm shadow-sm focus:border-brand-500 focus:ring-brand-500"
        checkbox_cls = "h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500"
        for name, field in self.fields.items():
            attrs = field.widget.attrs
            cls = checkbox_cls if isinstance(field.widget, forms.CheckboxInput) else input_cls
            attrs["class"] = (attrs.get("class", "") + " " + cls).strip()
            if name == "default_investment_rate_percent":
                attrs["step"] = "0.0001"
                attrs["placeholder"] = "0.0000"

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("default_investment_enabled"):
            return cleaned
        rate = cleaned.get("default_investment_rate_percent")
        started_on = cleaned.get("default_investment_started_on")
        if rate is None or rate <= 0:
            self.add_error("default_investment_rate_percent", "Enter a positive rate.")
        if not started_on:
            self.add_error("default_investment_started_on", "Choose when the default investment should start.")
        return cleaned
