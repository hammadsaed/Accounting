from django.apps import AppConfig


class InvestmentsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.investments"
    label = "investments"
    verbose_name = "Investments"

    def ready(self) -> None:
        from . import signals  # noqa: F401
