from django.contrib import admin

from .models import Investment, InvestmentProfit


class InvestmentProfitInline(admin.TabularInline):
    model = InvestmentProfit
    extra = 0


@admin.register(Investment)
class InvestmentAdmin(admin.ModelAdmin):
    list_display = ("name", "amount", "started_on", "created_by")
    search_fields = ("name", "notes")
    inlines = [InvestmentProfitInline]


@admin.register(InvestmentProfit)
class InvestmentProfitAdmin(admin.ModelAdmin):
    list_display = ("investment", "period_kind", "period_start", "amount", "created_by")
    list_filter = ("period_kind", "period_start")
    search_fields = ("investment__name", "notes")
