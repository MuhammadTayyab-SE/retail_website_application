"""Variant SKU allocation and correction using the existing permanent registry."""

from contextlib import contextmanager
from types import SimpleNamespace

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DataError, connection, transaction
from django.db.models import Q

from access.audit import current_request

SKU_LOCK = 734003020


def generated_sku():
    with connection.cursor() as cursor:
        try:
            cursor.execute("SELECT catalog_next_sku()")
        except DataError as error:
            if getattr(error.__cause__, "sqlstate", "") == "2200H":
                raise ValidationError(
                    {"sku": "The SKU sequence is exhausted; contact the administrator."}
                ) from error
            raise
        code = cursor.fetchone()[0]
        cursor.execute("SELECT set_config('retail.sku_source', 'generated', true)")
        return code


def validate_sku(instance):
    from catalog.models import SkuIdentifier
    from checkout.models import OrderItem

    if getattr(instance, "_skip_sku_validation", False):
        return
    previous = type(instance).objects.filter(pk=instance.pk).values("sku", "product_id").first()
    if previous and previous["product_id"] != instance.product_id:
        raise ValidationError(
            {"product": "An issued SKU cannot be transferred to another product."}
        )
    old = previous["sku"].strip().upper() if previous else ""
    code = instance.sku.strip().upper()
    if old == code:
        return
    if old and not code:
        raise ValidationError({"sku": "An issued SKU cannot be cleared."})
    request = current_request.get()
    actor = request.user if request else None
    if (
        (request or old)
        and not getattr(instance, "_generated_sku", False)
        and (not actor or not actor.is_active or not actor.has_perm("catalog.override_sku"))
    ):
        raise ValidationError(
            {"sku": "You need the SKU override permission to set or correct a SKU."}
        )
    if previous and (
        OrderItem.objects.filter(
            Q(variant_id=instance.pk) | Q(product_id=instance.product_id, variant__isnull=True)
        ).exists()
        or SkuIdentifier.objects.filter(variant_key=instance.pk, ordered_at__isnull=False).exists()
    ):
        raise ValidationError({"sku": "The SKU is locked because this item has an accepted order."})
    if code:
        with connection.cursor() as cursor:
            cursor.execute("SELECT catalog_sku_available(%s)", [code])
            if not cursor.fetchone()[0]:
                raise ValidationError({"sku": "This SKU was already issued and cannot be reused."})


@contextmanager
def sku_write(instance, update_fields=None):
    from catalog.models import Product

    writes_sku = update_fields is None or "sku" in update_fields
    instance._skip_sku_validation = not writes_sku
    try:
        with transaction.atomic():
            Product.objects.select_for_update().get(pk=instance.product_id)
            if not writes_sku:
                yield
                return
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_xact_lock(%s)", [SKU_LOCK])
            request = current_request.get()
            actor = request.user if request and request.user.is_authenticated else None
            if (
                request
                and instance._state.adding
                and (
                    not actor
                    or not actor.is_active
                    or not actor.is_staff
                    or not (
                        actor.has_perm("catalog.change_product")
                        or (
                            getattr(instance, "_creating_product", False)
                            and actor.has_perm("catalog.add_product")
                        )
                    )
                )
            ):
                raise PermissionDenied("Product creation or editing permission is required.")
            keys = ("sku_actor", "sku_actor_name", "sku_source")
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT current_setting('retail.sku_actor', true), "
                    "current_setting('retail.sku_actor_name', true), "
                    "current_setting('retail.sku_source', true)"
                )
                old_settings = cursor.fetchone()
                for key, value in zip(
                    keys,
                    (
                        str(actor.pk) if actor else "",
                        actor.get_username() if actor else "",
                        "generated" if getattr(instance, "_generated_sku", False) else "manual",
                    ),
                ):
                    cursor.execute("SELECT set_config(%s, %s, true)", [f"retail.{key}", value])
            yield
            with connection.cursor() as cursor:
                for key, value in zip(keys, old_settings):
                    cursor.execute(
                        "SELECT set_config(%s, %s, true)", [f"retail.{key}", value or ""]
                    )
    finally:
        instance._skip_sku_validation = False


@transaction.atomic
def assign_sku(instance, *, actor, code=None):
    from catalog.models import Product, ProductVariant

    if not isinstance(instance, ProductVariant):
        raise ValueError("SKUs belong to product variants.")
    if (
        not actor
        or not actor.is_active
        or not actor.is_staff
        or not actor.has_perm("catalog.change_product")
    ):
        raise PermissionDenied("Product editing permission is required to assign a SKU.")
    if code is not None and not actor.has_perm("catalog.override_sku"):
        raise PermissionDenied("The SKU override permission is required for a manual code.")
    token = current_request.set(SimpleNamespace(user=actor))
    try:
        Product.objects.select_for_update().get(pk=instance.product_id)
        instance._generated_sku = code is None
        instance.sku = generated_sku() if code is None else code
        if not isinstance(instance.sku, str):
            raise ValidationError({"sku": "Enter a printable SKU."})
        instance.save() if instance._state.adding else instance.save(update_fields=["sku"])
        return instance.sku
    finally:
        instance._generated_sku = False
        current_request.reset(token)
