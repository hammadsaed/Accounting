"""Generic audit signal handlers.

We intentionally hard-code the list of audited model labels here so the
audit surface is explicit and reviewable. Adding a new audited model is
a one-line change.
"""
from __future__ import annotations

from django.apps import apps as django_apps
from django.contrib.contenttypes.models import ContentType
from django.db.models.signals import post_delete, post_init, post_save

from .middleware import get_current_user
from .models import AuditAction, AuditLog

#: Model labels (``app.model``) that should have their writes audited.
AUDITED_MODELS = (
    "accounts.Person",
    "company.Company",
    "company.BalanceMovement",
    "periods.Month",
    "periods.SplitRule",
    "periods.SplitShare",
    "earnings.Earning",
    "expenses.Expense",
    "transfers.Transfer",
    "transfers.Payment",
    "investments.Investment",
    "investments.InvestmentProfit",
)


def _snapshot(instance) -> dict:
    """Capture concrete field values for an instance.

    Used to compute a ``before`` snapshot in ``post_init`` and compared in
    ``post_save`` to record only fields that actually changed on update.
    """
    out = {}
    for field in instance._meta.concrete_fields:
        try:
            value = getattr(instance, field.attname, None)
        except Exception:  # pragma: no cover - defensive
            value = None
        out[field.attname] = value
    return out


def _diff(before: dict, after: dict) -> dict:
    return {
        k: {"from": _stringify(before.get(k)), "to": _stringify(after.get(k))}
        for k in after
        if before.get(k) != after.get(k)
    }


def _stringify(value):
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _record(action: str, instance, changed_fields: dict | None = None) -> None:
    AuditLog.objects.create(
        actor=get_current_user(),
        action=action,
        content_type=ContentType.objects.get_for_model(type(instance)),
        object_id=instance.pk,
        object_repr=str(instance)[:255],
        changed_fields=changed_fields or {},
    )


def _on_post_init(sender, instance, **kwargs):
    instance.__audit_snapshot__ = _snapshot(instance) if instance.pk else None


def _on_post_save(sender, instance, created, **kwargs):
    if created:
        _record(AuditAction.CREATE, instance)
    else:
        before = getattr(instance, "__audit_snapshot__", None) or {}
        after = _snapshot(instance)
        diff = _diff(before, after)
        if diff:
            _record(AuditAction.UPDATE, instance, diff)
    instance.__audit_snapshot__ = _snapshot(instance)


def _on_post_delete(sender, instance, **kwargs):
    _record(AuditAction.DELETE, instance)


def connect_audited_models() -> None:
    """Wire the handlers to every audited model. Called from ``AppConfig.ready``."""
    for label in AUDITED_MODELS:
        try:
            model = django_apps.get_model(label)
        except LookupError:  # pragma: no cover - defensive
            continue
        post_init.connect(_on_post_init, sender=model, dispatch_uid=f"audit:init:{label}")
        post_save.connect(_on_post_save, sender=model, dispatch_uid=f"audit:save:{label}")
        post_delete.connect(_on_post_delete, sender=model, dispatch_uid=f"audit:delete:{label}")
