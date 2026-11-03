"""Order tracking inside the existing retailer administration workspace."""

from datetime import datetime, time
from zoneinfo import ZoneInfo

from django import forms
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import CharField, Count, Q, Value, prefetch_related_objects
from django.db.models.fields.json import KT
from django.db.models.functions import Cast, Concat, Replace
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from access.audit import record
from checkout.models import Order
from checkout.receipts import receipt_details
from config.admin import site

ORDER_STATUSES = {
    "placed": "New",
    "delivery_review": "Distance review",
    "processing": "Processing",
    "shipped": "Shipped",
    "ready_for_pickup": "Ready for pickup",
    "delivered": "Delivered",
    "collected": "Collected",
    "complete": "Complete",
}
STATUS_PATHS = {
    "delivery": ["placed", "processing", "shipped", "delivered", "complete"],
    "pickup": ["placed", "processing", "ready_for_pickup", "collected", "complete"],
}
STORE_TIMEZONE = ZoneInfo("Asia/Karachi")


class OrderFilters(forms.Form):
    q = forms.CharField(required=False, max_length=100, label="Search orders")
    start = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    end = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    status = forms.ChoiceField(
        required=False, choices=[("", "All statuses"), *ORDER_STATUSES.items()]
    )
    fulfillment = forms.ChoiceField(
        required=False,
        choices=[("", "All fulfillment"), ("delivery", "Delivery"), ("pickup", "Store pickup")],
    )
    payment = forms.ChoiceField(
        required=False, choices=[("", "All payments"), ("unpaid", "Unpaid"), ("paid", "Paid")]
    )
    order = forms.UUIDField(required=False, widget=forms.HiddenInput)

    def clean(self):
        values = super().clean()
        if values.get("start") and values.get("end") and values["start"] > values["end"]:
            raise forms.ValidationError("The end date must be on or after the start date.")
        return values


class OrderStatusForm(forms.Form):
    expected_status = forms.CharField(widget=forms.HiddenInput)
    status = forms.ChoiceField(label="Update status to", choices=())
    distance_verified = forms.BooleanField(
        required=False, label="I verified this address is within the allowed driving distance."
    )

    def __init__(self, *args, order, **kwargs):
        super().__init__(*args, **kwargs)
        path = STATUS_PATHS.get(order.delivery_method, [])
        current = "placed" if order.status == "delivery_review" else order.status
        next_status = (
            path[path.index(current) + 1 : path.index(current) + 2] if current in path else []
        )
        self.fields["status"].choices = [(value, ORDER_STATUSES[value]) for value in next_status]
        self.fields["expected_status"].initial = order.status
        self.fields["distance_verified"].required = order.status == "delivery_review"
        if order.status != "delivery_review":
            del self.fields["distance_verified"]


def _can_view(user):
    return user.has_perm("checkout.view_order") or user.has_perm("checkout.change_order")


@require_GET
def orders_dashboard(request):
    if not _can_view(request.user):
        raise PermissionDenied
    form = OrderFilters(request.GET)
    orders = Order.objects.all()
    if form.is_valid():
        values = form.cleaned_data
        if values["start"]:
            orders = orders.filter(
                created_at__gte=datetime.combine(values["start"], time.min, STORE_TIMEZONE)
            )
        if values["end"]:
            orders = orders.filter(
                created_at__lte=datetime.combine(values["end"], time.max, STORE_TIMEZONE)
            )
        if values["q"]:
            term = values["q"]
            orders = orders.alias(
                reference=Replace(Cast("public_id", CharField()), Value("-"), Value("")),
                customer_name=Concat(
                    KT("contact__first_name"),
                    Value(" "),
                    KT("contact__last_name"),
                    output_field=CharField(),
                ),
            ).filter(
                Q(reference__icontains=term.upper().removeprefix("ZLY-").replace("-", ""))
                | Q(customer_name__icontains=term)
                | Q(contact__email__icontains=term)
                | Q(contact__phone__icontains=term)
            )
        for field, name in (
            ("status", "status"),
            ("delivery_method", "fulfillment"),
            ("payment_status", "payment"),
        ):
            if values[name]:
                orders = orders.filter(**{field: values[name]})
    else:
        orders = orders.none()
    today = timezone.localdate(timezone=STORE_TIMEZONE)
    counts = orders.aggregate(
        total=Count("pk"),
        new=Count(
            "pk",
            filter=Q(
                created_at__range=(
                    datetime.combine(today, time.min, STORE_TIMEZONE),
                    datetime.combine(today, time.max, STORE_TIMEZONE),
                )
            ),
        ),
        processing=Count("pk", filter=Q(status="processing")),
        shipped=Count("pk", filter=Q(status="shipped")),
        paid=Count("pk", filter=Q(payment_status="paid")),
        review=Count("pk", filter=Q(status="delivery_review")),
    )
    page = Paginator(orders.prefetch_related("items"), 25).get_page(request.GET.get("page"))
    for order in page:
        order.status_label = ORDER_STATUSES.get(
            order.status, order.status.replace("_", " ").title()
        )
    params = request.GET.copy()
    for name in ("page", "order"):
        params.pop(name, None)
    selected = form.cleaned_data.get("order") if form.is_valid() else None
    return TemplateResponse(
        request,
        "retail_admin/orders.html",
        {
            **site.each_context(request),
            "title": "Orders Dashboard",
            "filters": form,
            "order_page": page,
            "filter_query": params.urlencode(),
            "order_counts": counts,
            "open_order_url": reverse("admin:order-detail", args=[selected]) if selected else "",
        },
    )


def _detail_context(request, order, form=None):
    prefetch_related_objects([order], "items__product__photos")
    receipt = receipt_details(order)
    for item in receipt["items"]:
        photos = list(item.product.photos.all()) if item.product else []
        photo = next((photo for photo in photos if photo.variant_id == item.variant_id), None)
        photo = photo or next((photo for photo in photos if photo.variant_id is None), None)
        item.image_url = reverse("public-product-photo", args=[photo.pk]) if photo else ""
    path = STATUS_PATHS.get(order.delivery_method, [])
    current = "placed" if order.status == "delivery_review" else order.status
    position = path.index(current) if current in path else -1
    status_form = form if form is not None else OrderStatusForm(order=order)
    return {
        **site.each_context(request),
        "title": order.number,
        "order": order,
        "receipt": receipt,
        "status_label": ORDER_STATUSES.get(order.status, order.status.replace("_", " ").title()),
        "status_form": status_form,
        "can_update_order": request.user.has_perm("checkout.change_order")
        and bool(status_form.fields["status"].choices),
        "progress": [
            {"label": ORDER_STATUSES[value], "done": index < position, "current": index == position}
            for index, value in enumerate(path)
        ],
    }


@require_GET
def order_detail(request, object_id):
    if not _can_view(request.user):
        raise PermissionDenied
    order = get_object_or_404(Order, public_id=object_id)
    template = (
        "retail_admin/order_detail.html"
        if request.GET.get("panel") == "1"
        else "retail_admin/order_detail_page.html"
    )
    return TemplateResponse(request, template, _detail_context(request, order))


@require_POST
@transaction.atomic
def order_status(request, object_id):
    if not request.user.has_perm("checkout.change_order"):
        raise PermissionDenied
    order = get_object_or_404(Order.objects.select_for_update(), public_id=object_id)
    form = OrderStatusForm(request.POST, order=order)
    valid = form.is_valid()
    stale = form.cleaned_data.get("expected_status") != order.status
    if stale:
        form.add_error(
            None, "This order changed since you opened it. Reload its details before updating."
        )
    if valid and not stale:
        previous = order.status
        order.status = form.cleaned_data["status"]
        order.save(update_fields=["status"])
        record(
            "status_change",
            "checkout.order",
            order.pk,
            details={
                "from": previous,
                "to": order.status,
                "distance_verified": bool(form.cleaned_data.get("distance_verified")),
            },
            request=request,
        )
        messages.success(request, f"{order.number} updated to {ORDER_STATUSES[order.status]}.")
        return redirect(reverse("admin:orders") + f"?order={order.public_id}")
    return TemplateResponse(
        request,
        "retail_admin/order_detail_page.html",
        _detail_context(request, order, form),
        status=409 if stale else 400,
    )
