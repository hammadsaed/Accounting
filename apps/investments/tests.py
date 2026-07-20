from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from apps.company.models import BalanceMovement, Company, MovementKind

from .models import Investment, InvestmentProfit, ProfitPeriod


class InvestmentFeatureTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username="admin", email="admin@example.com", password="pass12345"
        )
        self.client = Client()
        self.client.force_login(self.user)
        self.company = Company.load()

    def test_investment_creates_updates_and_deletes_company_movement(self):
        inv = Investment.objects.create(
            name="Fund A",
            amount=Decimal("1000.000"),
            started_on=date(2026, 5, 1),
            created_by=self.user,
        )
        movement = BalanceMovement.objects.get(
            source_app="investments", source_model="investment", source_id=inv.pk
        )
        self.assertEqual(movement.kind, MovementKind.INVESTMENT)
        self.assertEqual(movement.amount, Decimal("-1000.000"))
        self.assertEqual(self.company.current_balance, Decimal("-1000.000"))

        inv.amount = Decimal("1200.000")
        inv.name = "Fund A+"
        inv.started_on = date(2026, 5, 3)
        inv.save()
        movement.refresh_from_db()
        self.assertEqual(movement.amount, Decimal("-1200.000"))
        self.assertEqual(movement.happened_on, date(2026, 5, 3))
        self.assertIn("Fund A+", movement.description)

        inv.delete()
        self.assertFalse(BalanceMovement.objects.filter(pk=movement.pk).exists())

    def test_profit_rows_normalize_months_and_weeks(self):
        inv = Investment.objects.create(
            name="Fund B", amount=Decimal("500.000"), started_on=date(2026, 5, 1)
        )
        monthly = InvestmentProfit(
            investment=inv,
            period_kind=ProfitPeriod.MONTHLY,
            period_start=date(2026, 5, 19),
            amount=Decimal("25.000"),
        )
        monthly.full_clean(); monthly.save()
        self.assertEqual(monthly.period_start, date(2026, 5, 1))

        weekly = InvestmentProfit(
            investment=inv,
            period_kind=ProfitPeriod.WEEKLY,
            period_start=date(2026, 5, 21),
            amount=Decimal("10.000"),
        )
        weekly.full_clean(); weekly.save()
        self.assertEqual(weekly.period_start, date(2026, 5, 18))

    def test_investment_pages_dashboard_and_company_page_render(self):
        inv = Investment.objects.create(
            name="Fund C", amount=Decimal("2000.000"), started_on=date(2026, 6, 1)
        )
        InvestmentProfit.objects.create(
            investment=inv,
            period_kind=ProfitPeriod.MONTHLY,
            period_start=date(2026, 6, 1),
            amount=Decimal("300.000"),
            created_by=self.user,
        )
        InvestmentProfit.objects.create(
            investment=inv,
            period_kind=ProfitPeriod.WEEKLY,
            period_start=date(2026, 6, 8),
            amount=Decimal("50.000"),
            created_by=self.user,
        )

        r = self.client.get("/investments/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Fund C")
        self.assertContains(r, "Investments")
        self.assertContains(r, "Profit totals by month")
        self.assertContains(r, "June 2026")
        self.assertContains(r, "PKR 350.00")

        r = self.client.get(f"/investments/{inv.pk}/?kind=monthly")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Accumulated profit")
        self.assertContains(r, "Monthly")
        self.assertContains(r, "Export CSV")
        self.assertContains(r, "Profit %")
        self.assertContains(r, "15.00%")

        r = self.client.get(f"/investments/{inv.pk}/?kind=weekly")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "2.50%")

        r = self.client.get("/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Investments snapshot")
        self.assertContains(r, "Tracked value")

        r = self.client.get("/company/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Include invested amount")
        self.assertContains(r, "Include accumulated profits")

    def test_profit_history_csv_exports(self):
        inv1 = Investment.objects.create(
            name="Fund D", amount=Decimal("1000.000"), started_on=date(2026, 7, 1)
        )
        inv2 = Investment.objects.create(
            name="Fund E", amount=Decimal("800.000"), started_on=date(2026, 7, 5)
        )
        InvestmentProfit.objects.create(
            investment=inv1,
            period_kind=ProfitPeriod.MONTHLY,
            period_start=date(2026, 7, 1),
            amount=Decimal("100.000"),
        )
        InvestmentProfit.objects.create(
            investment=inv2,
            period_kind=ProfitPeriod.WEEKLY,
            period_start=date(2026, 7, 6),
            amount=Decimal("25.000"),
        )

        r = self.client.get("/investments/export.csv")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Content-Type"], "text/csv")
        self.assertIn("Fund D", r.content.decode())
        self.assertIn("Fund E", r.content.decode())

        r = self.client.get(f"/investments/{inv1.pk}/export.csv")
        self.assertEqual(r.status_code, 200)
        csv_text = r.content.decode()
        self.assertIn("Fund D", csv_text)
        self.assertNotIn("Fund E", csv_text)
