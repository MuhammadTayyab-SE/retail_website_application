import uuid
from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.core.exceptions import ValidationError
from django.db import models


class DeliveryPolicy(models.Model):
    """Retailer-local checkout rules; admin management is a separate backlog item."""

    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    enabled = models.BooleanField(default=False)
    delivery_fee = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    free_delivery_threshold = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    minimum_order = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    pickup_enabled = models.BooleanField(default=False)
    pickup_fee = models.DecimalField(
        max_digits=12, decimal_places=2, default=0, validators=[MinValueValidator(0)]
    )
    pickup_minimum_order = models.DecimalField(
        max_digits=12, decimal_places=2, default=0, validators=[MinValueValidator(0)]
    )
    tax_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    allowed_cities = models.JSONField(default=list, blank=True)
    origin_latitude = models.DecimalField(
        max_digits=18,
        decimal_places=15,
        null=True,
        blank=True,
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
    )
    origin_longitude = models.DecimalField(
        max_digits=18,
        decimal_places=15,
        null=True,
        blank=True,
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
    )
    delivery_radius_km = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    distance_verification = models.CharField(
        max_length=16,
        default="manual",
        choices=[("manual", "Manual distance review"), ("routing", "Routing provider")],
    )
    cash_on_delivery = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        super().clean()
        if (
            self.enabled
            and self.delivery_radius_km is not None
            and self.distance_verification != "manual"
        ):
            raise ValidationError(
                "A routing provider is not configured. Use manual review or keep checkout disabled."
            )
        if (
            self.enabled
            and self.delivery_radius_km is not None
            and (self.origin_latitude is None or self.origin_longitude is None)
        ):
            raise ValidationError(
                "Set the store's delivery origin before enabling a delivery radius."
            )
        if not isinstance(self.allowed_cities, list) or any(
            not isinstance(city, str) or not city.strip() or len(city) > 100
            for city in self.allowed_cities
        ):
            raise ValidationError(
                {"allowed_cities": "Use a list of city names, or [] for unrestricted delivery."}
            )

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(pk=1), name="checkout_single_policy"),
            models.CheckConstraint(
                condition=models.Q(
                    delivery_fee__gte=0, minimum_order__gte=0, tax_rate__gte=0, tax_rate__lte=100
                ),
                name="checkout_policy_nonnegative",
            ),
            models.CheckConstraint(
                condition=models.Q(free_delivery_threshold__isnull=True)
                | models.Q(free_delivery_threshold__gte=0),
                name="checkout_free_threshold_nonnegative",
            ),
        ]


class Order(models.Model):
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    idempotency_key = models.UUIDField(unique=True)
    request_fingerprint = models.CharField(max_length=64)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )
    browser_owner = models.UUIDField()
    contact = models.JSONField()
    address = models.JSONField()
    payment_method = models.CharField(max_length=24)
    delivery_method = models.CharField(
        max_length=16,
        default="delivery",
        choices=[("delivery", "Standard"), ("pickup", "Store Pickup")],
    )
    payment_status = models.CharField(max_length=24, default="unpaid")
    status = models.CharField(max_length=24, default="placed")
    subtotal = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal("0"))
    delivery_fee = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal("0"))
    tax = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal("0"))
    total = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal("0"))
    policy_snapshot = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-pk"]

    @property
    def number(self):
        return f"ZLY-{self.public_id.hex[:12].upper()}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey("catalog.Product", null=True, on_delete=models.SET_NULL)
    variant = models.ForeignKey(
        "catalog.ProductVariant", null=True, blank=True, on_delete=models.SET_NULL
    )
    name = models.CharField(max_length=400)
    sku = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    regular_price = models.DecimalField(max_digits=12, decimal_places=2)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    line_total = models.DecimalField(max_digits=16, decimal_places=2)

    class Meta:
        ordering = ["pk"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    quantity__gte=1, regular_price__gte=0, unit_price__gte=0, line_total__gte=0
                ),
                name="checkout_order_item_positive",
            )
        ]
