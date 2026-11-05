from decimal import ROUND_HALF_UP, Decimal
from uuid import uuid4

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import connection, models, transaction
from django.db.models.functions import Cast, Lower, Round, Trim
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.utils import timezone

from access.models import AttributedModel
from catalog.skus import generated_sku, sku_write, validate_sku


def category_photo_path(instance, filename):
    extension = filename.rsplit(".", 1)[-1].lower()
    return f"categories/{uuid4().hex}.{extension}"


class CategoryQuerySet(models.QuerySet):
    def parents(self):
        return self.alias(
            is_used_as_parent=models.Exists(
                self.model.objects.filter(parent_id=models.OuterRef("pk"))
            )
        ).filter(models.Q(is_parent_category=True) | models.Q(is_used_as_parent=True))

    def delete(self):
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_xact_lock(734003004)")
            return super().delete()


class Category(AttributedModel):
    name = models.CharField(max_length=100, unique=True)
    is_parent_category = models.BooleanField(default=False, editable=False)
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.CASCADE, related_name="children"
    )
    position = models.PositiveIntegerField(default=0, help_text="Lower numbers appear first.")
    is_active = models.BooleanField(default=True)

    photo = models.ImageField(upload_to=category_photo_path, blank=True)
    photo_x = models.PositiveSmallIntegerField(default=50, validators=[MaxValueValidator(100)])
    photo_y = models.PositiveSmallIntegerField(default=50, validators=[MaxValueValidator(100)])
    photo_zoom = models.PositiveSmallIntegerField(
        default=100,
        validators=[MinValueValidator(100), MaxValueValidator(200)],
        help_text="100 to 200 percent.",
    )

    objects = CategoryQuerySet.as_manager()

    class Meta:
        permissions = [
            ("view_parentcategory", "Can view parent categories"),
            ("add_parentcategory", "Can add parent categories"),
            ("change_parentcategory", "Can change parent categories"),
            ("delete_parentcategory", "Can delete parent categories"),
        ]
        ordering = ["position", "name", "pk"]
        verbose_name_plural = "categories"
        constraints = [
            models.UniqueConstraint(Lower(Trim("name")), name="category_name_normalized_unique"),
            models.CheckConstraint(condition=~models.Q(name=""), name="category_name_not_empty"),
        ]

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        self.name = self.name.strip()
        if not self.name:
            raise ValidationError({"name": "Enter a category name."})
        duplicates = Category.objects.filter(name__iexact=self.name).exclude(pk=self.pk)
        if duplicates.exists():
            raise ValidationError({"name": "A category with this name already exists."})
        seen = {self.pk} if self.pk else set()
        ancestor_id = self.parent_id
        while ancestor_id is not None:
            if ancestor_id in seen:
                raise ValidationError(
                    {"parent": "A category cannot contain itself or an ancestor."}
                )
            seen.add(ancestor_id)
            ancestor_id = (
                Category.objects.filter(pk=ancestor_id).values_list("parent_id", flat=True).first()
            )

    def _has_inactive_ancestor(self):
        ancestor_id = self.parent_id
        seen = set()
        while ancestor_id is not None and ancestor_id not in seen:
            seen.add(ancestor_id)
            ancestor = (
                Category.objects.filter(pk=ancestor_id).values("parent_id", "is_active").first()
            )
            if ancestor is None:
                break
            if not ancestor["is_active"]:
                return True
            ancestor_id = ancestor["parent_id"]
        return False

    def _descendant_ids(self):
        descendants, pending = set(), {self.pk}
        while pending:
            children = set(
                Category.objects.filter(parent_id__in=pending).values_list("pk", flat=True)
            )
            children -= descendants
            descendants.update(children)
            pending = children
        return descendants

    def save(self, *args, **kwargs):
        # Serialize hierarchy validation so concurrent reparenting cannot create a cycle.
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_xact_lock(734003004)")
            if self.is_active and self._has_inactive_ancestor():
                self.is_active = False
                if kwargs.get("update_fields") is not None:
                    kwargs["update_fields"] = set(kwargs["update_fields"]) | {"is_active"}
            self.full_clean()
            result = super().save(*args, **kwargs)
            if not self.is_active:
                affected_categories = {self.pk, *self._descendant_ids()}
                Category.objects.filter(pk__in=affected_categories).update(is_active=False)
                Product.objects.filter(category_id__in=affected_categories).update(is_active=False)
            return result

    def delete(self, *args, **kwargs):
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_xact_lock(734003004)")
            return super().delete(*args, **kwargs)


@receiver(post_delete, sender=Category)
def delete_category_photo(sender, instance, using, **kwargs):
    if instance.photo:
        storage, name = instance.photo.storage, instance.photo.name
        transaction.on_commit(lambda: storage.delete(name), using=using)


def product_photo_path(instance, filename):
    extension = filename.rsplit(".", 1)[-1].lower()
    return f"products/{uuid4().hex}.{extension}"


def brand_logo_path(instance, filename):
    extension = filename.rsplit(".", 1)[-1].lower()
    return f"brands/{uuid4().hex}.{extension}"


class Brand(AttributedModel):
    name = models.CharField(max_length=100)
    logo = models.ImageField(upload_to=brand_logo_path, blank=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name", "pk"]
        default_permissions = ("add", "change", "view")
        constraints = [
            models.UniqueConstraint(Lower(Trim("name")), name="brand_name_normalized_unique"),
            models.CheckConstraint(condition=~models.Q(name=""), name="brand_name_not_empty"),
        ]

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        self.name = self.name.strip()
        if not self.name:
            raise ValidationError({"name": "Enter a brand name."})
        if Brand.objects.filter(name__iexact=self.name).exclude(pk=self.pk).exists():
            raise ValidationError({"name": "A brand with this name already exists."})

    def save(self, *args, **kwargs):
        with transaction.atomic():
            previous = (
                Brand.objects.filter(pk=self.pk).values_list("logo", flat=True).first()
                if self.pk
                else ""
            )
            self.full_clean()
            result = super().save(*args, **kwargs)
            if (
                previous
                and previous != self.logo.name
                and (kwargs.get("update_fields") is None or "logo" in kwargs["update_fields"])
            ):
                storage = self.logo.storage
                transaction.on_commit(lambda: storage.delete(previous))
            return result


@receiver(post_delete, sender=Brand)
def delete_brand_logo(sender, instance, using, **kwargs):
    if instance.logo:
        storage, name = instance.logo.storage, instance.logo.name
        transaction.on_commit(lambda: storage.delete(name), using=using)


def discount_multiplier(percentage):
    """Shared arithmetic for Python prices and PostgreSQL price expressions."""
    return (Decimal(100) - percentage) / Decimal(100)


class ProductQuerySet(models.QuerySet):
    def with_selling_price(self):
        price_field = models.DecimalField(max_digits=12, decimal_places=2)
        return self.annotate(
            selling_price=models.Case(
                models.When(
                    is_on_sale=True,
                    discount_percentage__isnull=False,
                    then=Round(
                        models.F("price")
                        # Numeric division preserves fractional discount multipliers in PostgreSQL.
                        * discount_multiplier(
                            Cast("discount_percentage", output_field=price_field)
                        ),
                        precision=2,
                        output_field=price_field,
                    ),
                ),
                default=models.F("price"),
                output_field=price_field,
            )
        )

    def visible(self):
        # Evaluate the category hierarchy without a fixed depth limit.
        parents = dict(Category.objects.values_list("pk", "parent_id"))
        inactive = set(Category.objects.filter(is_active=False).values_list("pk", flat=True))
        hidden = set()
        for category_id in parents:
            current, seen = category_id, set()
            while current is not None:
                if current in inactive or current in seen:
                    hidden.add(category_id)
                    break
                seen.add(current)
                current = parents.get(current)
        return (
            self.filter(is_active=True)
            .filter(models.Q(variants__is_active=True))
            .exclude(category_id__in=hidden)
            .distinct()
        )


class Product(AttributedModel):
    name = models.CharField(max_length=200)
    price = models.DecimalField(
        "Price (PKR)",
        max_digits=12,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
    )
    quantity = models.PositiveIntegerField("Available quantity", default=0)
    is_on_sale = models.BooleanField("Active on sale", default=False)
    discount_percentage = models.PositiveSmallIntegerField(
        "Discount percentage",
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(100)],
        help_text="Enter a percentage from 1 to 100.",
    )
    description = models.TextField(blank=True)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="products")
    brand = models.ForeignKey(
        Brand, on_delete=models.PROTECT, related_name="products", null=True, blank=True
    )
    is_active = models.BooleanField(default=True)
    objects = ProductQuerySet.as_manager()

    class Meta:
        ordering = ["name", "pk"]
        permissions = [("override_sku", "Can override or correct a SKU before its first order")]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(price__gte=0), name="product_price_nonnegative"
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(is_on_sale=False, discount_percentage__isnull=True)
                    | models.Q(
                        is_on_sale=True,
                        discount_percentage__gte=1,
                        discount_percentage__lte=100,
                    )
                ),
                name="product_sale_discount_consistent",
            ),
            models.CheckConstraint(condition=~models.Q(name=""), name="product_name_not_empty"),
        ]

    def __str__(self):
        return self.name

    @property
    def default_variant(self):
        return next((variant for variant in self.variants.all() if variant.is_default), None)

    @property
    def display_variant(self):
        return next((variant for variant in self.variants.all() if variant.is_active), None)

    @property
    def sale_price(self):
        if not self.is_on_sale or self.discount_percentage is None:
            return self.price
        multiplier = discount_multiplier(self.discount_percentage)
        return (self.price * multiplier).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @property
    def is_effectively_active(self):
        if not self.is_active:
            return False
        if not any(variant.is_active for variant in self.variants.all()):
            return False
        category_id = self.category_id
        seen = set()
        while category_id is not None and category_id not in seen:
            seen.add(category_id)
            category = (
                Category.objects.filter(pk=category_id).values("parent_id", "is_active").first()
            )
            if category is None or not category["is_active"]:
                return False
            category_id = category["parent_id"]
        return True

    def clean(self):
        super().clean()
        self.name = self.name.strip()
        if self.brand_id:
            previous_brand = (
                Product.objects.filter(pk=self.pk).values_list("brand_id", flat=True).first()
                if self.pk
                else None
            )
            if (
                previous_brand != self.brand_id
                and not Brand.objects.filter(pk=self.brand_id, is_active=True).exists()
            ):
                raise ValidationError(
                    {"brand": "Choose an active brand, or leave the product unbranded."}
                )
        if not self.name:
            raise ValidationError({"name": "Enter a product name."})
        if self.category_id and Category.objects.parents().filter(pk=self.category_id).exists():
            raise ValidationError({"category": "Choose a category, rather than a parent category."})
        if self.is_on_sale and self.discount_percentage is None:
            raise ValidationError(
                {"discount_percentage": "Enter the percentage discount for this sale."}
            )
        if not self.is_on_sale:
            self.discount_percentage = None

    def save(self, *args, **kwargs):
        if kwargs.get("update_fields") is not None and not kwargs["update_fields"]:
            return
        if self.is_active and self.category_id:
            category_id = self.category_id
            seen = set()
            while category_id is not None and category_id not in seen:
                seen.add(category_id)
                category = (
                    Category.objects.filter(pk=category_id).values("parent_id", "is_active").first()
                )
                if category is None or not category["is_active"]:
                    self.is_active = False
                    if kwargs.get("update_fields") is not None:
                        kwargs["update_fields"] = set(kwargs["update_fields"]) | {"is_active"}
                    break
                category_id = category["parent_id"]
        with transaction.atomic():
            creating = self._state.adding
            self.full_clean()
            result = super().save(*args, **kwargs)
            if creating:
                variant = ProductVariant(
                    product=self,
                    is_default=True,
                    **getattr(self, "_default_variant_initial", {}),
                )
                variant._creating_product = True
                variant.save(force_insert=True)
            return result


class ProductVariant(AttributedModel):
    class Unit(models.TextChoices):
        KG = "kg", "kg"
        EACH = "each", "each"

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="variants")
    sku = models.CharField(max_length=100, unique=True, blank=True, default="")
    is_default = models.BooleanField(default=False)
    barcode = models.CharField(max_length=100, blank=True)
    inventory_unit = models.CharField(max_length=5, choices=Unit.choices, default=Unit.EACH)
    package_content = models.CharField(max_length=100, blank=True)
    price = models.DecimalField(
        "Price (PKR)",
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Leave blank to use the product price.",
    )
    description = models.TextField(
        blank=True, help_text="Leave blank to use the product description."
    )
    attributes = models.JSONField(
        default=dict,
        blank=True,
        help_text='Example: {"size": "1 litre"}. Empty means a standard variant.',
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-is_default", "sku", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["product"], condition=models.Q(is_default=True), name="variant_one_default"
            ),
            models.CheckConstraint(
                condition=models.Q(inventory_unit__in=["kg", "each"]),
                name="variant_inventory_unit_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(price__isnull=True) | models.Q(price__gte=0),
                name="variant_price_nonnegative",
            ),
            models.UniqueConstraint(
                Lower(Trim("sku")), name="product_variant_sku_normalized_unique"
            ),
            models.CheckConstraint(
                condition=~models.Q(sku=""), name="product_variant_sku_not_empty"
            ),
        ]
        verbose_name = "product variant"

    def __str__(self):
        return f"{self.product}: {self.sku}"

    @property
    def label(self):
        return (
            self.package_content
            or " / ".join(f"{key.title()}: {value}" for key, value in self.attributes.items())
            or "Standard"
        )

    @property
    def primary_photo(self):
        return next((photo for photo in self.photos.all() if photo.is_primary), None)

    @property
    def sale_price(self):
        price = self.product.price if self.price is None else self.price
        if not self.product.is_on_sale or self.product.discount_percentage is None:
            return price
        return (price * discount_multiplier(self.product.discount_percentage)).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

    def clean(self):
        super().clean()
        self.sku = self.sku.strip().upper()
        if (not self.sku and not self._state.adding) or (self.sku and not self.sku.isprintable()):
            raise ValidationError({"sku": "Enter a non-empty printable SKU."})
        if (
            self.sku
            and ProductVariant.objects.filter(sku__iexact=self.sku).exclude(pk=self.pk).exists()
        ):
            raise ValidationError({"sku": "This SKU is already used in the store."})
        validate_sku(self)
        for field in ("barcode", "package_content"):
            value = getattr(self, field).strip()
            if value and not value.isprintable():
                raise ValidationError({field: "Enter printable text."})
            setattr(self, field, value)
        if (
            self.pk
            and not self.is_default
            and ProductVariant.objects.filter(pk=self.pk, is_default=True).exists()
            and not ProductVariant.objects.filter(product_id=self.product_id, is_default=True)
            .exclude(pk=self.pk)
            .exists()
        ):
            raise ValidationError({"is_default": "Choose another default variant first."})
        if not isinstance(self.attributes, dict):
            raise ValidationError(
                {"attributes": "Enter an object of attribute names and text values."}
            )
        normalized = {}
        for name, value in self.attributes.items():
            if (
                not isinstance(name, str)
                or not isinstance(value, str)
                or not name.strip()
                or not value.strip()
            ):
                raise ValidationError(
                    {"attributes": "Attribute names and values must be non-empty text."}
                )
            key = name.strip().lower()
            if key in normalized:
                raise ValidationError(
                    {"attributes": "Attribute names must be unique ignoring case and spaces."}
                )
            normalized[key] = value.strip()
        self.attributes = normalized

    def save(self, *args, **kwargs):
        if kwargs.get("update_fields") is not None and not kwargs["update_fields"]:
            return
        with sku_write(self, kwargs.get("update_fields")):
            if self._state.adding and not self.sku.strip():
                self.sku = generated_sku()
                self._generated_sku = True
            if self.is_default and (
                kwargs.get("update_fields") is None or "is_default" in kwargs["update_fields"]
            ):
                ProductVariant.objects.filter(product_id=self.product_id, is_default=True).exclude(
                    pk=self.pk
                ).update(is_default=False)
            try:
                self.full_clean()
                return super().save(*args, **kwargs)
            finally:
                self._generated_sku = False

    def delete(self, *args, **kwargs):
        with transaction.atomic():
            Product.objects.select_for_update().get(pk=self.product_id)
            if type(self).objects.filter(pk=self.pk, is_default=True).exists():
                raise ValidationError("Choose another default before deleting this variant.")
            return super().delete(*args, **kwargs)


class SkuIdentifierQuerySet(models.QuerySet):
    def delete(self):
        raise PermissionDenied("Issued SKUs cannot be deleted or reused.")

    def update(self, **kwargs):
        # Django's deletion collector clears live owners; snapshots remain permanent.
        if not kwargs or any(
            key not in {"product", "variant"} or value is not None for key, value in kwargs.items()
        ):
            raise PermissionDenied("Issued SKU history cannot be changed.")
        return super().update(**kwargs)


class SkuIdentifier(models.Model):
    code = models.CharField(max_length=200, unique=True)
    product = models.ForeignKey(
        Product, null=True, on_delete=models.SET_NULL, related_name="sku_identifiers"
    )
    variant = models.ForeignKey(
        ProductVariant, null=True, on_delete=models.SET_NULL, related_name="sku_identifiers"
    )
    product_key = models.PositiveBigIntegerField(null=True)
    variant_key = models.PositiveBigIntegerField(null=True)
    issued_at = models.DateTimeField(default=timezone.now)
    actor_id = models.PositiveBigIntegerField(null=True)
    actor_name = models.CharField(max_length=150, blank=True)
    source = models.CharField(max_length=16, default="legacy")
    ordered_at = models.DateTimeField(null=True)
    objects = SkuIdentifierQuerySet.as_manager()

    class Meta:
        default_permissions = ()
        constraints = [
            models.CheckConstraint(condition=~models.Q(code=""), name="sku_identifier_not_empty"),
            models.CheckConstraint(
                condition=models.Q(code=Lower(Trim("code"))), name="sku_identifier_normalized"
            ),
        ]

    def save(self, *args, **kwargs):
        raise PermissionDenied("Use the SKU assignment path; issued history is permanent.")

    def delete(self, *args, **kwargs):
        raise PermissionDenied("Issued SKUs cannot be deleted or reused.")


class ProductPhotoQuerySet(models.QuerySet):
    def delete(self):
        with transaction.atomic():
            list(
                ProductVariant.objects.select_for_update()
                .filter(pk__in=self.values("variant_id"))
                .order_by("pk")
                .values_list("pk", flat=True)
            )
            return super().delete()


class ProductPhoto(AttributedModel):
    variant = models.ForeignKey(
        ProductVariant,
        on_delete=models.CASCADE,
        related_name="photos",
    )
    image = models.ImageField(upload_to=product_photo_path)
    alt_text = models.CharField(max_length=200, blank=True)
    position = models.PositiveIntegerField(default=0)
    is_primary = models.BooleanField(default=False)
    objects = ProductPhotoQuerySet.as_manager()

    class Meta:
        ordering = ["position", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["variant"],
                condition=models.Q(is_primary=True),
                name="variant_one_primary_photo",
            )
        ]

    def __str__(self):
        return self.alt_text or f"Photo for {self.variant}"

    def clean(self):
        super().clean()
        if (
            self.pk
            and type(self).objects.filter(pk=self.pk).exclude(variant_id=self.variant_id).exists()
        ):
            raise ValidationError(
                {"variant": "A saved photo cannot be transferred to another variant."}
            )

    def save(self, *args, **kwargs):
        if kwargs.get("update_fields") is not None and not kwargs["update_fields"]:
            return
        with transaction.atomic():
            ProductVariant.objects.select_for_update().get(pk=self.variant_id)
            previous = type(self).objects.filter(pk=self.pk).values_list("image", flat=True).first()
            if (
                self.pk
                and kwargs.get("update_fields") is not None
                and "is_primary" not in kwargs["update_fields"]
            ):
                self.is_primary = type(self).objects.get(pk=self.pk).is_primary
            others = type(self).objects.filter(variant_id=self.variant_id).exclude(pk=self.pk)
            if self.is_primary:
                others.update(is_primary=False)
            elif not others.filter(is_primary=True).exists():
                replacement = others.order_by("position", "pk").first()
                if replacement:
                    type(self).objects.filter(pk=replacement.pk).update(is_primary=True)
                else:
                    self.is_primary = True
                    if kwargs.get("update_fields") is not None:
                        kwargs["update_fields"] = set(kwargs["update_fields"]) | {"is_primary"}
            self.full_clean()
            result = super().save(*args, **kwargs)
            if (
                previous
                and previous != self.image.name
                and (kwargs.get("update_fields") is None or "image" in kwargs["update_fields"])
            ):
                storage = self.image.storage
                transaction.on_commit(lambda: storage.delete(previous))
            return result

    def delete(self, *args, **kwargs):
        with transaction.atomic():
            ProductVariant.objects.select_for_update().get(pk=self.variant_id)
            return super().delete(*args, **kwargs)


@receiver(post_delete, sender=ProductPhoto)
def delete_product_photo(sender, instance, using, **kwargs):
    remaining = ProductPhoto.objects.using(using).filter(variant_id=instance.variant_id)
    if remaining.exists() and not remaining.filter(is_primary=True).exists():
        first = remaining.order_by("position", "pk").first()
        remaining.filter(pk=first.pk).update(is_primary=True)
    if instance.image:
        storage, name = instance.image.storage, instance.image.name
        transaction.on_commit(lambda: storage.delete(name), using=using)
