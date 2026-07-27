from django.apps import AppConfig


class CompanyConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.company"
    label = "company"
    verbose_name = "Company"

    def ready(self) -> None:
        from . import signals  # noqa: F401
