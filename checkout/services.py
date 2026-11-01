import re
import hashlib
import json
from collections import Counter
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.db.models import F
from django.urls import reverse
from django.utils import timezone

from catalog.models import Product, ProductVariant
from checkout.models import DeliveryPolicy, Order, OrderItem


class CheckoutError(ValueError):
    pass


def cart_quantities(items):
    if not isinstance(items, list) or not 1 <= len(items) <= 100:
        raise CheckoutError("Your cart is empty or too large. Please review it before checkout.")
    quantities = Counter()
    for item in items:
        if not isinstance(item, dict):
            raise CheckoutError("The cart contains an invalid item.")
        match = re.fullmatch(
            r"live-([1-9][0-9]{0,17})(?::([1-9][0-9]{0,17}))?", str(item.get("id", ""))
        )
        quantity = item.get("quantity")
        if not match or type(quantity) is not int or not 1 <= quantity <= 2147483647:
            raise CheckoutError("The cart contains an invalid product or quantity.")
        key = (int(match[1]), int(match[2]) if match[2] else None)
        quantities[key] += quantity
        if quantities[key] > 2147483647:
            raise CheckoutError("The requested quantity is too large.")
    return quantities


def priced_items(items, *, lock=False):
    quantities = cart_quantities(items)
    product_ids = sorted({key[0] for key in quantities})
    if lock:
        list(Product.objects.select_for_update().filter(pk__in=product_ids).order_by("pk"))
    products = {
        p.pk: p
        for p in Product.objects.visible().filter(pk__in=product_ids).prefetch_related("photos")
    }
    variant_ids = sorted({key[1] for key in quantities if key[1]})
    variants_query = ProductVariant.objects.filter(pk__in=variant_ids, is_active=True).order_by(
        "pk"
    )
    if lock:
        variants_query = variants_query.select_for_update()
    variants = {v.pk: v for v in variants_query}
    stock_quantities = Counter()
    lines = []
    for (product_id, variant_id), quantity in quantities.items():
        product = products.get(product_id)
        if not product:
            raise CheckoutError("A cart product is no longer available. Please review your cart.")
        variant = variants.get(variant_id) if variant_id else None
        if variant_id and (not variant or variant.product_id != product_id):
            raise CheckoutError(f"An option for {product.name} is no longer available.")
        stock_quantities[product_id] += quantity
        if stock_quantities[product_id] > product.quantity:
            raise CheckoutError(f"Only {product.quantity} units of {product.name} are available.")
        if variant:
            variant.product = product
        price = variant.sale_price if variant else product.sale_price
        regular = variant.price if variant and variant.price is not None else product.price
        photos = list(product.photos.all())
        photo = next((p for p in photos if p.variant_id == variant_id), None)
        photo = photo or next((p for p in photos if p.variant_id is None), None)
        lines.append(
            {
                "product": product,
                "variant": variant,
                "quantity": quantity,
                "name": f"{product.name} ({variant.sku})" if variant else product.name,
                "sku": variant.sku if variant else product.sku,
                "description": (
                    variant.description if variant and variant.description else product.description
                ),
                "regular_price": regular,
                "unit_price": price,
                "line_total": price * quantity,
                "image": reverse("public-product-photo", args=[photo.pk]) if photo else "",
            }
        )
    for line in lines:
        line["stock"] = (
            line["product"].quantity - stock_quantities[line["product"].pk] + line["quantity"]
        )
    return lines


def policy_totals(lines, policy, city="", delivery_method="delivery", *, enforce_rules=True):
    if not policy or not policy.enabled:
        raise CheckoutError("Checkout is not available until delivery rules are configured.")
    if delivery_method not in ("delivery", "pickup"):
        raise CheckoutError("This delivery option is not available.")
    pickup = delivery_method == "pickup"
    if pickup and not policy.pickup_enabled:
        raise CheckoutError("Store pickup is not currently available.")
    if (
        not pickup
        and policy.delivery_radius_km is not None
        and (
            policy.distance_verification != "manual"
            or policy.origin_latitude is None
            or policy.origin_longitude is None
        )
    ):
        raise CheckoutError("Delivery distance cannot be verified with the current configuration.")
    if (
        enforce_rules
        and not pickup
        and city
        and policy.allowed_cities
        and city.strip().casefold()
        not in {str(value).strip().casefold() for value in policy.allowed_cities}
    ):
        raise CheckoutError("Delivery is not available in this city.")
    subtotal = sum((line["line_total"] for line in lines), Decimal("0.00"))
    minimum = policy.pickup_minimum_order if pickup else policy.minimum_order
    if enforce_rules and subtotal < minimum:
        raise CheckoutError(f"The minimum order is PKR {minimum:.2f}.")
    threshold = None if pickup else policy.free_delivery_threshold
    delivery = (
        policy.pickup_fee
        if pickup
        else Decimal("0.00")
        if threshold is not None and subtotal >= threshold
        else policy.delivery_fee
    )
    tax = (subtotal * policy.tax_rate / 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if subtotal + delivery + tax >= Decimal("100000000000000"):
        raise CheckoutError("The order total is too large. Please reduce the quantities.")
    return {
        "subtotal": subtotal,
        "delivery_fee": delivery,
        "tax": tax,
        "total": subtotal + delivery + tax,
        "policy_revision": policy.updated_at.isoformat(),
        "delivery_method": delivery_method,
        "free_delivery_remaining": max(Decimal("0"), threshold - subtotal)
        if threshold is not None
        else None,
        "free_delivery_threshold": threshold,
    }


def owned_order(order, user, browser_owner):
    if order.user_id is not None:
        return user.is_authenticated and order.user_id == user.pk
    return str(order.browser_owner) == str(browser_owner)


def quote_snapshot(lines, totals):
    return {
        "items": sorted(
            [
                [
                    line["product"].pk,
                    line["variant"].pk if line["variant"] else 0,
                    line["quantity"],
                    str(line["regular_price"]),
                    str(line["unit_price"]),
                ]
                for line in lines
            ]
        ),
        "totals": {key: str(totals[key]) for key in ("subtotal", "delivery_fee", "tax", "total")},
        "policy_revision": totals["policy_revision"],
        "delivery_method": totals["delivery_method"],
    }


@transaction.atomic
def place_order(items, details, user, browser_owner, accepted_quote):
    fingerprint = hashlib.sha256(
        json.dumps(
            {
                "items": sorted(
                    [product_id, variant_id or 0, quantity]
                    for (product_id, variant_id), quantity in cart_quantities(items).items()
                ),
                "details": {
                    key: value for key, value in details.items() if key != "idempotency_key"
                },
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()
    order, created = Order.objects.get_or_create(
        idempotency_key=details["idempotency_key"],
        defaults={
            "user": user if user.is_authenticated else None,
            "browser_owner": browser_owner,
            "contact": {key: details[key] for key in ("email", "phone", "first_name", "last_name")},
            "address": {
                key: details[key] for key in ("address", "landmark", "city", "postal_code", "notes")
            },
            "payment_method": details["payment_method"],
            "delivery_method": details["delivery_method"],
            "request_fingerprint": fingerprint,
        },
    )
    if not owned_order(order, user, browser_owner):
        raise CheckoutError("This checkout request is unavailable. Please start a new checkout.")
    if not created:
        if order.request_fingerprint != fingerprint:
            raise CheckoutError(
                "This checkout was already submitted with different details. Start a new checkout."
            )
        return order
    policy = DeliveryPolicy.objects.filter(pk=1, enabled=True).first()
    if details["payment_method"] != "cod" or not policy or not policy.cash_on_delivery:
        raise CheckoutError("The selected payment method is not available.")
    lines = priced_items(items, lock=True)
    totals = policy_totals(lines, policy, details["city"], details["delivery_method"])
    if quote_snapshot(lines, totals) != accepted_quote:
        raise CheckoutError(
            "Prices or delivery charges changed. Review the refreshed total before placing your order again."
        )
    order.subtotal, order.delivery_fee = totals["subtotal"], totals["delivery_fee"]
    order.tax, order.total = totals["tax"], totals["total"]
    if (
        details["delivery_method"] == "delivery"
        and policy.delivery_radius_km is not None
        and policy.distance_verification == "manual"
    ):
        order.status = "delivery_review"
    order.policy_snapshot = {
        "tax_rate": str(policy.tax_rate),
        "minimum_order": str(policy.minimum_order),
        "delivery_fee": str(policy.delivery_fee),
        "free_delivery_threshold": str(policy.free_delivery_threshold)
        if policy.free_delivery_threshold is not None
        else None,
        "allowed_cities": policy.allowed_cities,
        "pickup_fee": str(policy.pickup_fee),
        "pickup_minimum_order": str(policy.pickup_minimum_order),
        "origin_latitude": str(policy.origin_latitude)
        if policy.origin_latitude is not None
        else None,
        "origin_longitude": str(policy.origin_longitude)
        if policy.origin_longitude is not None
        else None,
        "delivery_radius_km": str(policy.delivery_radius_km)
        if policy.delivery_radius_km is not None
        else None,
        "distance_verification": policy.distance_verification,
    }
    order.save(
        update_fields=["subtotal", "delivery_fee", "tax", "total", "policy_snapshot", "status"]
    )
    for line in lines:
        OrderItem.objects.create(
            order=order,
            **{
                key: line[key]
                for key in (
                    "product",
                    "variant",
                    "name",
                    "sku",
                    "description",
                    "quantity",
                    "regular_price",
                    "unit_price",
                    "line_total",
                )
            },
        )
        Product.objects.filter(pk=line["product"].pk).update(
            quantity=F("quantity") - line["quantity"], updated_at=timezone.now()
        )
    return order
