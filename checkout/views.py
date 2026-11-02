import json
import uuid

from django.core import signing
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from catalog.views import storefront_categories
from checkout.forms import CheckoutForm
from checkout.models import DeliveryPolicy, Order
from checkout.receipts import receipt_details, receipt_pdf
from checkout.services import (
    CheckoutError,
    owned_order,
    place_order,
    policy_totals,
    priced_items,
    quote_snapshot,
)


def browser_owner(request):
    if "checkout_owner" not in request.session:
        request.session["checkout_owner"] = str(uuid.uuid4())
    return request.session["checkout_owner"]


def request_json(request):
    try:
        data = json.loads(request.body)
    except (ValueError, UnicodeError):
        raise CheckoutError("The checkout request is not valid JSON.") from None
    if not isinstance(data, dict):
        raise CheckoutError("The checkout request is invalid.")
    return data


@never_cache
@require_GET
def checkout_page(request):
    browser_owner(request)
    attempt = str(uuid.uuid4())
    policy = DeliveryPolicy.objects.filter(pk=1).first()
    form = CheckoutForm(
        policy=policy,
        initial={
            "idempotency_key": attempt,
            "delivery_method": "delivery",
            "payment_method": "cod",
            "email": request.user.email if request.user.is_authenticated else "",
        },
    )
    return render(
        request,
        "catalog/checkout/page.html",
        {
            "form": form,
            "checkout_enabled": bool(policy and policy.enabled and policy.cash_on_delivery),
            "delivery_radius_km": policy.delivery_radius_km if policy else None,
            "standard_fee": policy.delivery_fee if policy else None,
            "pickup_fee": policy.pickup_fee if policy else None,
            "homepage_categories": [
                entry for entry in storefront_categories() if entry["category"].parent_id is None
            ],
        },
    )


@never_cache
@require_POST
def checkout_quote(request):
    try:
        data = request_json(request)
        lines = priced_items(data.get("items"))
        policy = DeliveryPolicy.objects.filter(pk=1).first()
        method = str(data.get("delivery_method", "delivery"))
        totals = policy_totals(
            lines, policy, str(data.get("city", "")), method, enforce_rules=False
        )
    except CheckoutError as error:
        return JsonResponse({"error": str(error)}, status=400)
    return JsonResponse(
        {
            "items": [
                {
                    "id": f"live-{line['product'].pk}"
                    + (f":{line['variant'].pk}" if line["variant"] else ""),
                    "stock": line["stock"],
                    **{
                        key: line[key]
                        for key in (
                            "name",
                            "quantity",
                            "regular_price",
                            "unit_price",
                            "line_total",
                            "image",
                        )
                    },
                }
                for line in lines
            ],
            **totals,
            "tax_rate": policy.tax_rate,
            "quote_token": signing.dumps(quote_snapshot(lines, totals), salt="checkout-quote"),
        }
    )


@never_cache
@require_POST
def checkout_place(request):
    try:
        data = request_json(request)
        details = data.get("details")
        if not isinstance(details, dict):
            raise CheckoutError("Enter your contact and delivery details.")
        policy = DeliveryPolicy.objects.filter(pk=1).first()
        form = CheckoutForm(details, policy=policy)
        if not form.is_valid():
            return JsonResponse(
                {
                    "error": "Please correct the highlighted fields.",
                    "fields": form.errors.get_json_data(),
                },
                status=400,
            )
        try:
            accepted_quote = signing.loads(
                data.get("quote_token", ""), salt="checkout-quote", max_age=900
            )
        except (signing.BadSignature, TypeError):
            raise CheckoutError(
                "Your price quote has expired. Refresh the order summary and try again."
            ) from None
        order = place_order(
            data.get("items"),
            form.cleaned_data,
            request.user,
            browser_owner(request),
            accepted_quote,
        )
    except CheckoutError as error:
        return JsonResponse({"error": str(error)}, status=409)
    return JsonResponse(
        {"confirmation_url": reverse("checkout-confirmation", args=[order.public_id])}
    )


def owned_order_or_404(request, public_id):
    order = get_object_or_404(Order.objects.prefetch_related("items"), public_id=public_id)
    if not owned_order(order, request.user, request.session.get("checkout_owner")):
        raise Http404
    return order


@never_cache
@require_GET
def confirmation(request, public_id):
    order = owned_order_or_404(request, public_id)
    return render(
        request,
        "catalog/checkout/confirmation.html",
        {"order": order, "receipt": receipt_details(order)},
    )


@never_cache
@require_GET
def download_receipt(request, public_id):
    order = owned_order_or_404(request, public_id)
    return FileResponse(
        receipt_pdf(order),
        as_attachment=True,
        filename=f"{order.number}-receipt.pdf",
        content_type="application/pdf",
    )
