from decimal import ROUND_HALF_UP, Decimal
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import connection, models, transaction
from django.db.models.functions import Lower, Trim
from django.db.models.signals import post_delete
from django.dispatch import receiver

from access.models import AttributedModel


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

    def save(self, *args, **kwargs):
        # Serialize hierarchy validation so concurrent reparenting cannot create a cycle.
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_xact_lock(734003004)")
            self.full_clean()
            return super().save(*args, **kwargs)

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


class ProductQuerySet(models.QuerySet):
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
            .filter(
                models.Q(unit__in=["kg", "litre", "ml", "each"])
                | models.Q(variants__is_active=True)
            )
            .exclude(category_id__in=hidden)
            .distinct()
        )


class Product(AttributedModel):
    class Unit(models.TextChoices):
        KG = "kg", "kg"
        LITRE = "litre", "litre"
        ML = "ml", "ml"
        EACH = "each", "each"

    name = models.CharField(max_length=200)
    sku = models.CharField("SKU", max_length=100, blank=True, default="")
    unit = models.CharField(max_length=5, choices=Unit.choices, blank=True, default="")
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
    is_active = models.BooleanField(default=True)
    objects = ProductQuerySet.as_manager()

    class Meta:
        ordering = ["name", "pk"]
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
            models.UniqueConstraint(
                Lower(Trim("sku")),
                condition=~models.Q(sku=""),
                name="product_sku_normalized_unique",
            ),
            models.CheckConstraint(condition=~models.Q(name=""), name="product_name_not_empty"),
        ]

    def __str__(self):
        return self.name

    @property
    def sale_price(self):
        if not self.is_on_sale or self.discount_percentage is None:
            return self.price
        multiplier = Decimal(100 - self.discount_percentage) / Decimal(100)
        return (self.price * multiplier).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def clean(self):
        super().clean()
        self.name = self.name.strip()
        self.sku = self.sku.strip().upper()
        if self.sku and not self.sku.isprintable():
            raise ValidationError({"sku": "Enter a printable SKU."})
        if self.sku and (
            Product.objects.filter(sku__iexact=self.sku).exclude(pk=self.pk).exists()
            or ProductVariant.objects.filter(sku__iexact=self.sku)
            .exclude(product_id=self.pk)
            .exists()
        ):
            raise ValidationError({"sku": "This SKU is already used in the store."})
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
        self.full_clean()
        return super().save(*args, **kwargs)


class ProductVariant(AttributedModel):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="variants")
    sku = models.CharField(max_length=100, unique=True)
    attributes = models.JSONField(
        default=dict,
        blank=True,
        help_text='Example: {"size": "1 litre"}. Empty means a standard variant.',
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["sku", "pk"]
        constraints = [
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

    def clean(self):
        super().clean()
        self.sku = self.sku.strip().upper()
        if not self.sku or not self.sku.isprintable():
            raise ValidationError({"sku": "Enter a non-empty printable SKU."})
        if ProductVariant.objects.filter(sku__iexact=self.sku).exclude(pk=self.pk).exists():
            raise ValidationError({"sku": "This SKU is already used in the store."})
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
        self.full_clean()
        return super().save(*args, **kwargs)


class ProductPhoto(AttributedModel):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="photos")
    image = models.ImageField(upload_to=product_photo_path)
    alt_text = models.CharField(max_length=200, blank=True)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["position", "pk"]

    def __str__(self):
        return self.alt_text or f"Photo for {self.product}"


@receiver(post_delete, sender=ProductPhoto)
def delete_product_photo(sender, instance, using, **kwargs):
    if instance.image:
        storage, name = instance.image.storage, instance.image.name
        transaction.on_commit(lambda: storage.delete(name), using=using)
