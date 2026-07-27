from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import BalanceMovement, Company
from .services import AUTO_SOURCE_APP, AUTO_SOURCE_MODEL, rebuild_default_investment


def _is_auto_movement(instance: BalanceMovement) -> bool:
    return instance.source_app == AUTO_SOURCE_APP and instance.source_model == AUTO_SOURCE_MODEL


@receiver(post_save, sender=Company)
def rebuild_on_company_save(sender, instance: Company, raw=False, **kwargs):
    if raw:
        return
    rebuild_default_investment(instance)


@receiver(post_save, sender=BalanceMovement)
def rebuild_on_movement_save(sender, instance: BalanceMovement, raw=False, **kwargs):
    if raw or _is_auto_movement(instance):
        return
    rebuild_default_investment(instance.company)


@receiver(post_delete, sender=BalanceMovement)
def rebuild_on_movement_delete(sender, instance: BalanceMovement, **kwargs):
    if _is_auto_movement(instance):
        return
    rebuild_default_investment(instance.company)