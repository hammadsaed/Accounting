from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.company.models import BalanceMovement, Company, MovementKind

from .models import Investment

SOURCE_APP = "investments"
SOURCE_MODEL = "investment"


def _movement_for(investment: Investment):
    return BalanceMovement.objects.filter(source_app=SOURCE_APP, source_model=SOURCE_MODEL, source_id=investment.pk).first()


@receiver(post_save, sender=Investment)
def upsert_movement(sender, instance: Investment, created, **kwargs):
    company = Company.load()
    fields = dict(
        company=company,
        kind=MovementKind.INVESTMENT,
        amount=-instance.amount,
        happened_on=instance.started_on,
        description=f"Investment: {instance.name}"[:255],
        source_app=SOURCE_APP,
        source_model=SOURCE_MODEL,
        source_id=instance.pk,
        created_by=instance.created_by,
    )
    movement = _movement_for(instance)
    if movement is None:
        BalanceMovement.objects.create(**fields)
        return
    for k, v in fields.items():
        setattr(movement, k, v)
    movement.save()


@receiver(post_delete, sender=Investment)
def delete_movement(sender, instance: Investment, **kwargs):
    BalanceMovement.objects.filter(source_app=SOURCE_APP, source_model=SOURCE_MODEL, source_id=instance.pk).delete()
