"""Order tracking inside the existing retailer administration workspace."""

import csv
from datetime import datetime, time, timedelta
from decimal import Decimal
from io import StringIO
from textwrap import wrap
from zoneinfo import ZoneInfo

from django import forms
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.core.validators import MinValueValidator
from django.db import IntegrityError, transaction
from django.db.models import CharField, Count, Q, Sum, Value, prefetch_related_objects
from django.db.models.fields.json import KT
from django.db.models.functions import Cast, Concat, Replace, TruncDate
from django.http import FileResponse, Http404, StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from access.audit import record
from access.models import AuditEvent
from checkout.models import DeliveryPolicy, Order
from checkout.receipts import receipt_details, receipt_pdf
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
    "cancelled": "Cancelled",
    "failed": "Delivery failed",
}
ORDER_SECTIONS = {
    "overview": ("Orders overview", "Everything happening across your store, at a glance."),
    "all": ("All orders", "Search, filter and manage every customer order in one place."),
    "fulfillment": ("Fulfillment", "Confirm orders and keep picking and packing moving."),
    "delivery": ("Delivery center", "Track dispatches, pickups and completed deliveries."),
    "payments": ("Payments & COD", "Keep cash collection separate from fulfillment."),
    "attention": ("Needs attention", "Review addresses and orders needing follow-up."),
    "reports": ("Order reports", "Order volume, fulfillment and recorded payments."),
}
QUEUE_FILTERS = {
    "fulfillment": Q(status__in=["placed", "processing", "ready_for_pickup"]),
    "delivery": Q(
        status__in=["ready_for_pickup", "shipped", "delivered", "collected", "complete", "failed"]
    ),
    "payments": Q(payment_status="unpaid") & ~Q(status="cancelled"),
    "attention": Q(status__in=["delivery_review", "failed", "cancelled"]),
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
    date_mode = forms.ChoiceField(
        required=False, choices=[("range", "Custom date range"), ("single", "Specific date")]
    )
    on = forms.DateField(
        required=False, label="Specific date", widget=forms.DateInput(attrs={"type": "date"})
    )
    quick = forms.ChoiceField(
        required=False,
        choices=[
            ("all", "All time"),
            ("today", "Today"),
            ("7", "Last 7 days"),
            ("30", "Last 30 days"),
            ("custom", "Custom"),
        ],
        widget=forms.HiddenInput,
    )
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

    def clean(self):
        values = super().clean()
        if values.get("date_mode") == "single":
            if not values.get("on"):
                self.add_error("on", "Choose a specific date.")
            values["start"] = values["end"] = values.get("on")
        elif values.get("start") and values.get("end") and values["start"] > values["end"]:
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


class CashCollectionForm(forms.Form):
    expected_payment_status = forms.CharField(widget=forms.HiddenInput, initial="unpaid")
    confirmed = forms.BooleanField(label="I confirm this cash payment was received.")


class InternalNoteForm(forms.Form):
    note = forms.CharField(
        label="Private team note",
        max_length=2000,
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Instructions for your team…"}),
    )


class OrderSettingsForm(forms.ModelForm):
    expected_revision = forms.CharField(required=False, widget=forms.HiddenInput)
    allowed_cities = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text="One city per line. Leave blank for unrestricted delivery.",
    )

    class Meta:
        model = DeliveryPolicy
        fields = [
            "enabled",
            "cash_on_delivery",
            "minimum_order",
            "delivery_fee",
            "free_delivery_threshold",
            "tax_rate",
            "pickup_enabled",
            "pickup_fee",
            "pickup_minimum_order",
            "allowed_cities",
            "origin_latitude",
            "origin_longitude",
            "delivery_radius_km",
        ]
        labels = {
            "enabled": "Enable checkout",
            "cash_on_delivery": "Allow cash on delivery / pickup",
            "minimum_order": "Minimum delivery order (PKR)",
            "delivery_fee": "Delivery fee (PKR)",
            "free_delivery_threshold": "Free delivery from (PKR)",
            "tax_rate": "Added tax (%)",
            "pickup_enabled": "Enable store pickup",
            "pickup_fee": "Pickup fee (PKR)",
            "pickup_minimum_order": "Minimum pickup order (PKR)",
        }
        help_texts = {
            "free_delivery_threshold": "Leave blank to disable the free-delivery promotion.",
            "delivery_radius_km": "Driving-distance limit in km. Addresses are checked manually until a routing provider is configured.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.initial["allowed_cities"] = "\n".join(self.instance.allowed_cities or [])
        self.initial["expected_revision"] = (
            self.instance.updated_at.isoformat() if self.instance.updated_at else ""
        )
        for name in ("delivery_fee", "minimum_order", "free_delivery_threshold"):
            self.fields[name].validators.append(MinValueValidator(0))
            self.fields[name].widget.attrs["min"] = 0

    def clean_allowed_cities(self):
        cities = list(
            dict.fromkeys(
                city.strip()
                for city in self.cleaned_data["allowed_cities"].replace(",", "\n").splitlines()
                if city.strip()
            )
        )
        if any(len(city) > 100 for city in cities):
            raise forms.ValidationError("City names must be 100 characters or fewer.")
        return cities


def _can_view(user):
    return user.has_perm("checkout.view_order") or user.has_perm("checkout.change_order")


def _filtered_orders(request, section):
    if section not in ORDER_SECTIONS:
        raise Http404
    params = request.GET.copy()
    quick = params.get("quick", "")
    today = timezone.localdate(timezone=STORE_TIMEZONE)
    if quick in {"all", "today", "7", "30"}:
        params["date_mode"] = "range"
        params.pop("on", None)
        params["start"] = (
            ""
            if quick == "all"
            else str(today - timedelta(days=0 if quick == "today" else int(quick) - 1))
        )
        params["end"] = "" if quick == "all" else str(today)
    form = OrderFilters(params)
    orders = Order.objects.all()
    if not form.is_valid():
        return form, orders.none()
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
            | Q(address__city__icontains=term)
        )
    for field, name in (
        ("status", "status"),
        ("delivery_method", "fulfillment"),
        ("payment_status", "payment"),
    ):
        if values[name]:
            orders = orders.filter(**{field: values[name]})
    return form, orders


def _order_summary(orders):
    # Keep the count alias separate from the price field used by the sums.
    counts = orders.aggregate(
        order_count=Count("pk"),
        awaiting=Count("pk", filter=Q(status="placed")),
        processing=Count("pk", filter=Q(status="processing")),
        ready=Count("pk", filter=Q(status="ready_for_pickup")),
        shipped=Count("pk", filter=Q(status="shipped")),
        fulfilled=Count("pk", filter=Q(status__in=["delivered", "collected", "complete"])),
        paid=Count("pk", filter=Q(payment_status="paid")),
        unpaid=Count("pk", filter=Q(payment_status="unpaid") & ~Q(status="cancelled")),
        review=Count("pk", filter=Q(status="delivery_review")),
        failed=Count("pk", filter=Q(status="failed")),
        cancelled=Count("pk", filter=Q(status="cancelled")),
        cod=Count("pk", filter=Q(payment_method="cod")),
        amount=Sum("total", filter=~Q(status="cancelled"), default=Decimal("0.00")),
        unpaid_amount=Sum(
            "total",
            filter=Q(payment_status="unpaid") & ~Q(status="cancelled"),
            default=Decimal("0.00"),
        ),
        paid_amount=Sum("total", filter=Q(payment_status="paid"), default=Decimal("0.00")),
    )
    counts["total"] = counts.pop("order_count")
    return counts


def _order_queue(orders, section, payment):
    queue = QUEUE_FILTERS.get(section, Q())
    if section == "payments" and payment == "paid":
        queue = Q(payment_status="paid") & ~Q(status="cancelled")
    return orders.filter(queue)


@require_GET
def orders_dashboard(request, section="all"):
    if not _can_view(request.user):
        raise PermissionDenied
    form, all_orders = _filtered_orders(request, section)
    counts = _order_summary(all_orders)
    orders = _order_queue(all_orders, section, form.cleaned_data.get("payment"))
    page = Paginator(orders.prefetch_related("items"), 5 if section == "overview" else 25).get_page(
        request.GET.get("page")
    )
    for order in page:
        order.status_label = ORDER_STATUSES.get(
            order.status, order.status.replace("_", " ").title()
        )
        order.item_quantity = sum(item.quantity for item in order.items.all())
    params = request.GET.copy()
    params.pop("page", None)
    params.pop("order", None)
    params.pop("section", None)
    quick_ranges = []
    for value, label in [
        ("all", "All time"),
        ("today", "Today"),
        ("7", "Last 7 days"),
        ("30", "Last 30 days"),
    ]:
        quick_params = params.copy()
        quick_params["quick"] = value
        quick_ranges.append(
            {
                "label": label,
                "query": quick_params.urlencode(),
                "active": request.GET.get("quick", "all" if not request.GET else "custom") == value,
            }
        )
    activity = []
    if section in {"overview", "reports"}:
        end = form.cleaned_data.get("end") if form.is_valid() else None
        end = end or timezone.localdate(timezone=STORE_TIMEZONE)
        start = end - timedelta(days=min(11, end.toordinal() - 1))
        if form.is_valid() and form.cleaned_data.get("start"):
            start = max(start, form.cleaned_data["start"])
        daily = {
            row["day"]: row
            for row in orders.filter(
                created_at__range=(
                    datetime.combine(start, time.min, STORE_TIMEZONE),
                    datetime.combine(end, time.max, STORE_TIMEZONE),
                )
            )
            .annotate(day=TruncDate("created_at", tzinfo=STORE_TIMEZONE))
            .values("day")
            .annotate(total=Count("pk"), paid=Count("pk", filter=Q(payment_status="paid")))
            .order_by()
        }
        maximum = max((row["total"] for row in daily.values()), default=1) or 1
        for offset in range((end - start).days + 1):
            day = start + timedelta(days=offset)
            row = daily.get(day, {"total": 0, "paid": 0})
            activity.append(
                {
                    "day": day,
                    "total": row["total"],
                    "paid": row["paid"],
                    "height": round(row["total"] / maximum * 100),
                    "paid_height": round(row["paid"] / maximum * 100),
                }
            )
    pipeline = [
        {
            "label": label,
            "count": counts[key],
            "percent": round(counts[key] / max(counts["total"], 1) * 100),
        }
        for key, label in [
            ("awaiting", "New orders"),
            ("processing", "Processing"),
            ("ready", "Ready for pickup"),
            ("shipped", "Out for delivery"),
            ("fulfilled", "Delivered / collected"),
        ]
    ]
    return TemplateResponse(
        request,
        "retail_admin/orders.html",
        {
            **site.each_context(request),
            "title": ORDER_SECTIONS[section][0],
            "section": section,
            "description": ORDER_SECTIONS[section][1],
            "filters": form,
            "order_page": page,
            "filter_query": params.urlencode(),
            "order_counts": counts,
            "quick_ranges": quick_ranges,
            "activity": activity,
            "pipeline": pipeline,
            "can_change_orders": request.user.has_perm("checkout.change_order"),
        },
    )


def _detail_context(request, order, form=None, payment_form=None, note_form=None):
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
    events = list(
        AuditEvent.objects.filter(
            module="checkout.order",
            target_id=str(order.pk),
            action__in=["status_change", "cash_collected", "internal_note"],
        ).order_by("-occurred_at", "-pk")[:50]
    )
    for event in events:
        event.summary = (
            (
                "Status: "
                + ORDER_STATUSES.get(event.details.get("to"), str(event.details.get("to", "")))
            )
            if event.action == "status_change"
            else "Cash payment collected"
            if event.action == "cash_collected"
            else "Private note added"
        )
    return {
        **site.each_context(request),
        "title": order.number,
        "order": order,
        "receipt": receipt,
        "status_label": ORDER_STATUSES.get(order.status, order.status.replace("_", " ").title()),
        "status_form": status_form,
        "payment_form": payment_form if payment_form is not None else CashCollectionForm(),
        "note_form": note_form if note_form is not None else InternalNoteForm(),
        "can_change_orders": request.user.has_perm("checkout.change_order"),
        "can_collect_cash": request.user.has_perm("checkout.change_order")
        and order.payment_method == "cod"
        and order.payment_status == "unpaid"
        and order.status != "cancelled",
        "order_activity": events,
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
    return TemplateResponse(
        request, "retail_admin/order_detail_page.html", _detail_context(request, order)
    )


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
        return redirect("admin:order-detail", object_id=order.public_id)
    return TemplateResponse(
        request,
        "retail_admin/order_detail_page.html",
        _detail_context(request, order, form),
        status=409 if stale else 400,
    )


@require_POST
@transaction.atomic
def order_payment(request, object_id):
    if not request.user.has_perm("checkout.change_order"):
        raise PermissionDenied
    order = get_object_or_404(Order.objects.select_for_update(), public_id=object_id)
    form = CashCollectionForm(request.POST)
    valid = form.is_valid()
    stale = form.cleaned_data.get("expected_payment_status") != order.payment_status
    if stale:
        form.add_error(None, "Payment changed since you opened this order. Reload its details.")
    if (
        order.payment_method != "cod"
        or order.payment_status != "unpaid"
        or order.status == "cancelled"
    ):
        form.add_error(None, "Only an unpaid cash order can be marked collected here.")
    if valid and not form.errors:
        order.payment_status = "paid"
        order.save(update_fields=["payment_status"])
        record(
            "cash_collected",
            "checkout.order",
            order.pk,
            details={"from": "unpaid", "to": "paid", "amount": str(order.total)},
            request=request,
        )
        messages.success(request, f"Cash collection recorded for {order.number}.")
        return redirect("admin:order-detail", object_id=order.public_id)
    return TemplateResponse(
        request,
        "retail_admin/order_detail_page.html",
        _detail_context(request, order, payment_form=form),
        status=409 if stale else 400,
    )


@require_POST
@transaction.atomic
def order_note(request, object_id):
    if not request.user.has_perm("checkout.change_order"):
        raise PermissionDenied
    order = get_object_or_404(Order, public_id=object_id)
    form = InternalNoteForm(request.POST)
    if form.is_valid():
        record(
            "internal_note",
            "checkout.order",
            order.pk,
            details={"note": form.cleaned_data["note"]},
            request=request,
        )
        messages.success(request, "Private order note added.")
        return redirect("admin:order-detail", object_id=order.public_id)
    return TemplateResponse(
        request,
        "retail_admin/order_detail_page.html",
        _detail_context(request, order, note_form=form),
        status=400,
    )


@require_GET
def orders_export(request):
    if not _can_view(request.user):
        raise PermissionDenied
    form, orders = _filtered_orders(request, request.GET.get("section", "all"))
    orders = _order_queue(
        orders, request.GET.get("section", "all"), form.cleaned_data.get("payment")
    )
    if not form.is_valid():
        messages.error(request, "Correct the order filters before exporting.")
        return redirect("admin:orders")

    def rows():
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "Order ID",
                "Customer",
                "Date (PKT)",
                "Status",
                "Payment",
                "Method",
                "Fulfillment",
                "Total (PKR)",
            ]
        )
        yield output.getvalue()
        for order in orders.iterator(chunk_size=500):
            output.seek(0)
            output.truncate(0)
            values = [
                order.number,
                f"{order.contact.get('first_name', '')} {order.contact.get('last_name', '')}",
                timezone.localtime(order.created_at, STORE_TIMEZONE).isoformat(),
                ORDER_STATUSES.get(order.status, order.status),
                order.payment_status,
                order.payment_method,
                order.delivery_method,
                str(order.total),
            ]
            # Prefix formula-like user input so spreadsheet software treats it as text.
            writer.writerow(
                [
                    "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) else value
                    for value in values
                ]
            )
            yield output.getvalue()

    response = StreamingHttpResponse(rows(), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="retail-orders.csv"'
    return response


@require_GET
def order_receipt(request, object_id):
    if not _can_view(request.user):
        raise PermissionDenied
    order = get_object_or_404(Order.objects.prefetch_related("items"), public_id=object_id)
    return FileResponse(
        receipt_pdf(order),
        as_attachment=True,
        filename=f"{order.number}-receipt.pdf",
        content_type="application/pdf",
    )


@require_GET
def order_label(request, object_id):
    if not _can_view(request.user):
        raise PermissionDenied
    order = get_object_or_404(Order, public_id=object_id)
    context = {"order": order, "receipt": receipt_details(order)}
    destination = (
        ["Collection from store"]
        if order.delivery_method == "pickup"
        else [
            str(order.address.get(key, ""))
            for key in ("address", "landmark", "city", "postal_code")
        ]
    )
    text_lines = [
        f"{order.contact.get('first_name', '')} {order.contact.get('last_name', '')}",
        str(order.contact.get("phone", "")),
        *destination,
    ]
    lines = [line for value in text_lines if value.strip() for line in wrap(value, width=58)]
    height = max(520, 280 + len(lines) * 24)
    context.update(
        label_lines=[{"text": line, "y": 180 + index * 24} for index, line in enumerate(lines)],
        label_height=height,
        label_footer=height - 55,
    )
    if request.GET.get("download") == "1":
        response = TemplateResponse(
            request, "retail_admin/order_label.svg", context, content_type="image/svg+xml"
        )
        response["Content-Disposition"] = f'attachment; filename="{order.number}-label.svg"'
        return response
    return TemplateResponse(request, "retail_admin/order_label.html", context)


@require_http_methods(["GET", "POST"])
@transaction.atomic
def order_settings(request):
    can_change = request.user.has_perm("checkout.change_deliverypolicy")
    if not (can_change or request.user.has_perm("checkout.view_deliverypolicy")):
        raise PermissionDenied
    if request.method == "POST" and not can_change:
        raise PermissionDenied
    policy = DeliveryPolicy.objects.select_for_update().filter(pk=1).first()
    policy = policy if policy is not None else DeliveryPolicy(pk=1)
    revision = policy.updated_at.isoformat() if policy.updated_at else ""
    form = OrderSettingsForm(request.POST if request.method == "POST" else None, instance=policy)
    response_status = 200
    if request.method == "POST":
        before = {name: str(getattr(policy, name)) for name in OrderSettingsForm.Meta.fields}
        valid = form.is_valid()
        if form.cleaned_data.get("expected_revision", "") != revision:
            form.add_error(
                None, "Order settings changed while this page was open. Reload before saving."
            )
            response_status = 409
        if valid and not form.errors:
            if not policy._state.adding and not any(
                name in OrderSettingsForm.Meta.fields for name in form.changed_data
            ):
                messages.info(request, "Order settings are already up to date.")
                return redirect("admin:order-settings")
            try:
                with transaction.atomic():
                    saved = form.save()
                    record(
                        "order_settings_change",
                        "checkout.deliverypolicy",
                        saved.pk,
                        details={
                            "changes": {
                                name: {"from": before[name], "to": str(getattr(saved, name))}
                                for name in form.changed_data
                                if name in OrderSettingsForm.Meta.fields
                            }
                        },
                        request=request,
                    )
            except IntegrityError:
                form.add_error(
                    None,
                    "These settings were changed by another administrator. Reload before saving.",
                )
                response_status = 409
            else:
                messages.success(
                    request, "Order settings saved. New checkout quotes use these rules."
                )
                return redirect("admin:order-settings")
        elif response_status == 200:
            response_status = 400
    return TemplateResponse(
        request,
        "retail_admin/order_settings.html",
        {
            **site.each_context(request),
            "title": "Settings / Orders",
            "settings_form": form,
            "can_change_order_settings": can_change,
        },
        status=response_status,
    )
