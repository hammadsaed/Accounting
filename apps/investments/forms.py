from django import forms
from django.utils import timezone

from .models import Investment, InvestmentProfit, ProfitPeriod


class InvestmentForm(forms.ModelForm):
    class Meta:
        model = Investment
        fields = ("started_on", "name", "amount", "notes")
        widgets = {
            "started_on": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, form_id: str | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.is_bound and self.instance.pk is None and not self.initial.get("started_on"):
            self.initial["started_on"] = timezone.localdate()
        cls = "block w-full rounded-md border-slate-300 text-sm shadow-sm focus:border-brand-500 focus:ring-brand-500"
        for name, field in self.fields.items():
            attrs = field.widget.attrs
            attrs["class"] = (attrs.get("class", "") + " " + cls).strip()
            if form_id:
                attrs["form"] = form_id
            if name == "amount":
                attrs["step"] = "0.01"
                attrs["placeholder"] = "0.00"
            elif name == "name":
                attrs["placeholder"] = "Investment name"
            elif name == "notes":
                attrs["placeholder"] = "Optional notes"


class InvestmentProfitForm(forms.ModelForm):
    class Meta:
        model = InvestmentProfit
        fields = ("period_kind", "period_start", "amount", "notes")
        widgets = {
            "period_start": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, form_id: str | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.is_bound and self.instance.pk is None and not self.initial.get("period_start"):
            today = timezone.localdate()
            self.initial["period_start"] = today.replace(day=1)
            self.initial.setdefault("period_kind", ProfitPeriod.MONTHLY)
        cls = "block w-full rounded-md border-slate-300 text-sm shadow-sm focus:border-brand-500 focus:ring-brand-500"
        for name, field in self.fields.items():
            attrs = field.widget.attrs
            attrs["class"] = (attrs.get("class", "") + " " + cls).strip()
            if form_id:
                attrs["form"] = form_id
            if name == "amount":
                attrs["step"] = "0.01"
                attrs["placeholder"] = "0.00"
            elif name == "notes":
                attrs["placeholder"] = "Optional notes"
