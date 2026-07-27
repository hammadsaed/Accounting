from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from apps.investments.models import Investment

from .forms import DefaultInvestmentForm
from .models import BalanceMovement, Company, MovementKind
from .services import AUTO_SOURCE_APP, AUTO_SOURCE_MODEL


class DefaultInvestmentTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username="admin", email="admin@example.com", password="pass12345"
        )
        self.client = Client()
        self.client.force_login(self.user)
        self.company = Company.load()

    @patch("apps.company.services.timezone.localdate", return_value=date(2026, 7, 31))
    def test_default_investment_waits_for_monthly_anniversary_before_posting(self, _mock_today):
        self.company.opening_balance = Decimal("1000.000")
        self.company.default_investment_enabled = True
        self.company.default_investment_rate_mode = "annual"
        self.company.default_investment_rate_percent = Decimal("365.0000")
        self.company.default_investment_started_on = date(2026, 7, 1)
        self.company.save()

        self.assertFalse(
            BalanceMovement.objects.filter(source_app=AUTO_SOURCE_APP, source_model=AUTO_SOURCE_MODEL).exists()
        )
        self.company.refresh_from_db()
        self.assertEqual(self.company.current_balance, Decimal("1000.000"))

    @patch("apps.company.services.timezone.localdate", return_value=date(2026, 8, 1))
    def test_default_investment_posts_monthly_profit_into_company_balance(self, _mock_today):
        self.company.opening_balance = Decimal("1000.000")
        self.company.default_investment_enabled = True
        self.company.default_investment_rate_mode = "annual"
        self.company.default_investment_rate_percent = Decimal("365.0000")
        self.company.default_investment_started_on = date(2026, 7, 1)
        self.company.save()

        auto = BalanceMovement.objects.get(source_app=AUTO_SOURCE_APP, source_model=AUTO_SOURCE_MODEL)
        self.assertEqual(auto.kind, MovementKind.DEFAULT_PROFIT)
        self.assertEqual(auto.happened_on, date(2026, 8, 1))
        self.assertEqual(auto.amount, Decimal("310.000"))
        self.company.refresh_from_db()
        self.assertEqual(self.company.current_balance, Decimal("1310.000"))

    @patch("apps.company.services.timezone.localdate", return_value=date(2026, 8, 1))
    def test_real_investment_reduces_idle_cash_before_monthly_profit(self, _mock_today):
        self.company.opening_balance = Decimal("1000.000")
        self.company.default_investment_enabled = True
        self.company.default_investment_rate_mode = "annual"
        self.company.default_investment_rate_percent = Decimal("365.0000")
        self.company.default_investment_started_on = date(2026, 7, 1)
        self.company.save()

        Investment.objects.create(
            name="Fund X",
            amount=Decimal("200.000"),
            started_on=date(2026, 7, 2),
            created_by=self.user,
        )

        auto = list(
            BalanceMovement.objects.filter(source_app=AUTO_SOURCE_APP, source_model=AUTO_SOURCE_MODEL)
            .order_by("happened_on", "id")
            .values_list("happened_on", "amount")
        )
        self.assertEqual(auto, [(date(2026, 8, 1), Decimal("250.000"))])
        self.company.refresh_from_db()
        self.assertEqual(self.company.current_balance, Decimal("1050.000"))

    @patch("apps.company.services.timezone.localdate", return_value=date(2026, 7, 5))
    def test_company_page_allows_saving_default_investment_settings(self, _mock_today):
        r = self.client.post(
            "/company/default-investment/",
            {
                "default_investment_enabled": "on",
                "default_investment_rate_mode": "monthly",
                "default_investment_rate_percent": "12.5000",
                "default_investment_started_on": "2026-07-01",
            },
        )
        self.assertEqual(r.status_code, 302)

        self.company.refresh_from_db()
        self.assertTrue(self.company.default_investment_enabled)
        self.assertEqual(self.company.default_investment_rate_mode, "monthly")
        self.assertEqual(self.company.default_investment_rate_percent, Decimal("12.5000"))

        r = self.client.get("/company/")
        self.assertContains(r, "Default investment")
        self.assertContains(r, "Auto profit earned")
        self.assertContains(r, "Profit months posted")
        self.assertContains(r, "Save default investment")

    def test_default_investment_checkbox_uses_checkbox_styling(self):
        form = DefaultInvestmentForm(instance=self.company)
        checkbox = str(form["default_investment_enabled"])
        self.assertIn("h-4 w-4", checkbox)
        self.assertNotIn("block w-full", checkbox)

    def test_company_page_marks_company_tab_active(self):
        r = self.client.get("/company/")
        self.assertEqual(r.status_code, 200)

        html = r.content.decode()
        self.assertEqual(html.count('aria-current="page"'), 1)
        self.assertRegex(
            html,
            r'<a href="/company/" aria-current="page" class="[^"]*bg-brand-50[^"]*">Company</a>',
        )