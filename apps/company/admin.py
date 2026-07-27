from django.contrib import admin

from .models import BalanceMovement, Company


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("name", "opening_balance", "opening_balance_date", "current_balance")
    fieldsets = (
        (None, {"fields": ("name",)}),
        ("Opening balance", {"fields": ("opening_balance", "opening_balance_date")}),
        ("Bank", {"fields": ("bank_name", "bank_account_title", "bank_account_number", "bank_iban")}),
        (
            "Default investment",
            {
                "fields": (
                    "default_investment_enabled",
                    "default_investment_rate_mode",
                    "default_investment_rate_percent",
                    "default_investment_started_on",
                )
            },
        ),
    )

    def has_add_permission(self, request):
        # Singleton: only allow add when the row doesn't yet exist.
        return not Company.objects.exists()


@admin.register(BalanceMovement)
class BalanceMovementAdmin(admin.ModelAdmin):
    list_display = ("happened_on", "kind", "amount", "description", "created_by")
    list_filter = ("kind", "happened_on")
    search_fields = ("description",)
    readonly_fields = ("source_app", "source_model", "source_id", "created_at")
