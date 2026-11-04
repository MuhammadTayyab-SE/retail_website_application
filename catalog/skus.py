"""One assignment path while legacy product/variant columns remain in use."""

from contextlib import contextmanager
from types import SimpleNamespace

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DataError, connection, transaction
from django.db.models import Q

from access.audit import current_request

SKU_LOCK = 734003020


def validate_sku(instance):
    from catalog.models import Product, SkuIdentifier
    from checkout.models import OrderItem

    if getattr(instance, "_skip_sku_validation", False):
        return
    variant = not isinstance(instance, Product)
    previous = (
        type(instance)
        .objects.filter(pk=instance.pk)
        .values("sku", *(["product_id"] if variant else []))
        .first()
    )
    if variant and previous and previous["product_id"] != instance.product_id:
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
    generated = getattr(instance, "_generated_sku", False)
    # Initial trusted imports may lack an HTTP actor; corrections always require one.
    if (
        (request or old)
        and not generated
        and (not actor or not actor.is_active or not actor.has_perm("catalog.override_sku"))
    ):
        raise ValidationError(
            {"sku": "You need the SKU override permission to set or correct a SKU."}
        )
    product_id = instance.product_id if variant else instance.pk
    ordered = (
        OrderItem.objects.filter(
            Q(variant_id=instance.pk) | Q(product_id=product_id, variant__isnull=True)
            if variant
            else Q(product_id=product_id)
        )
        if previous
        else OrderItem.objects.none()
    )
    issued = (
        SkuIdentifier.objects.filter(
            Q(variant_key=instance.pk) if variant else Q(product_key=product_id)
        )
        if previous
        else SkuIdentifier.objects.none()
    )
    if variant and previous and Product.objects.filter(pk=product_id, sku__iexact=old).exists():
        ordered = OrderItem.objects.filter(product_id=product_id)
    if ordered.exists() or issued.filter(ordered_at__isnull=False).exists():
        raise ValidationError({"sku": "The SKU is locked because this item has an accepted order."})
    if not code:
        return
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT * FROM catalog_sku_available(%s, %s, %s)",
            [code, product_id, (instance.pk or 0) if variant else None],
        )
        available = cursor.fetchone()[0]
    if not available:
        raise ValidationError({"sku": "This SKU was already issued and cannot be reused."})


@contextmanager
def sku_write(instance, update_fields=None):
    from catalog.models import Product

    writes_sku = update_fields is None or "sku" in update_fields
    instance._skip_sku_validation = not writes_sku
    try:
        with transaction.atomic():
            if not writes_sku:
                yield
                return
            product_id = instance.pk if isinstance(instance, Product) else instance.product_id
            if product_id:
                Product.objects.select_for_update().filter(pk=product_id).exists()
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_xact_lock(%s)", [SKU_LOCK])
            request = current_request.get()
            actor = request.user if request and request.user.is_authenticated else None
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT current_setting('retail.sku_actor', true), "
                    "current_setting('retail.sku_actor_name', true), "
                    "current_setting('retail.sku_source', true)"
                )
                old_settings = cursor.fetchone()
                for key, value in zip(
                    ("sku_actor", "sku_actor_name", "sku_source"),
                    (
                        str(actor.pk) if actor else "",
                        actor.get_username() if actor else "",
                        "generated" if getattr(instance, "_generated_sku", False) else "manual",
                    ),
                ):
                    cursor.execute("SELECT set_config(%s, %s, true)", [f"retail.{key}", value])
            yield
            with connection.cursor() as cursor:
                for key, value in zip(("sku_actor", "sku_actor_name", "sku_source"), old_settings):
                    cursor.execute(
                        "SELECT set_config(%s, %s, true)", [f"retail.{key}", value or ""]
                    )
    finally:
        instance._skip_sku_validation = False


@transaction.atomic
def assign_sku(instance, *, actor, code=None):
    """Assign a generated code, or an authorized manual correction, to a saved item."""
    from catalog.models import Product, ProductVariant

    if not isinstance(instance, (Product, ProductVariant)) or instance._state.adding:
        raise ValueError("Save the product or variant before assigning its SKU.")
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
        product_id = instance.pk if isinstance(instance, Product) else instance.product_id
        Product.objects.select_for_update().get(pk=product_id)
        instance._generated_sku = code is None
        if code is None:
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
        if not isinstance(code, str):
            raise ValidationError({"sku": "Enter a printable SKU."})
        instance.sku = code
        instance.save(update_fields=["sku"])
        return instance.sku
    finally:
        instance._generated_sku = False
        current_request.reset(token)
