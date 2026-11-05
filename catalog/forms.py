from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Q

from catalog.models import Brand, Category, Product, ProductPhoto, ProductVariant


def validate_photo_upload(image):
    if image and hasattr(image, "content_type"):
        if image.size > 8 * 1024 * 1024:
            raise ValidationError("Choose a photo smaller than 8 MB.")
        if image.image.format not in {"JPEG", "PNG", "WEBP"}:
            raise ValidationError("Choose a JPEG, PNG or WebP photo.")
        extension = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}[image.image.format]
        image.name = f"photo.{extension}"
    return image


class BrandLogoInput(forms.ClearableFileInput):
    template_name = "catalog/widgets/brand_logo.html"


class BrandForm(forms.ModelForm):
    class Meta:
        model = Brand
        fields = ["name", "description", "is_active", "logo"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "logo": BrandLogoInput(attrs={"accept": "image/jpeg,image/png,image/webp"}),
        }
        help_texts = {"logo": "Optional JPEG, PNG or WebP, up to 8 MB."}

    def clean_logo(self):
        return validate_photo_upload(self.cleaned_data.get("logo"))


class CategoryPhotoInput(forms.ClearableFileInput):
    template_name = "catalog/widgets/category_photo.html"


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = "__all__"
        widgets = {
            "photo": CategoryPhotoInput(attrs={"accept": "image/jpeg,image/png,image/webp"}),
            "photo_x": forms.NumberInput(attrs={"type": "range", "min": 0, "max": 100}),
            "photo_y": forms.NumberInput(attrs={"type": "range", "min": 0, "max": 100}),
            "photo_zoom": forms.NumberInput(attrs={"type": "range", "min": 100, "max": 200}),
        }
        labels = {
            "photo_x": "Horizontal position",
            "photo_y": "Vertical position",
            "photo_zoom": "Zoom",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "parent" in self.fields:
            self.fields["parent"].label = "Parent category (optional)"
            self.fields["parent"].empty_label = "No parent — independent category"
            self.fields["parent"].help_text = "Leave empty or select a parent category."
            self.fields["parent"].queryset = Category.objects.parents().exclude(pk=self.instance.pk)
        for name in ("photo_x", "photo_y", "photo_zoom"):
            if name in self.fields:
                self.fields[name].required = False

    def clean(self):
        cleaned = super().clean()
        for name in ("photo_x", "photo_y", "photo_zoom"):
            if name in self.fields and cleaned.get(name) is None:
                cleaned[name] = getattr(self.instance, name)
        return cleaned

    def clean_photo(self):
        return validate_photo_upload(self.cleaned_data.get("photo"))


class ProductForm(forms.ModelForm):
    sku = forms.CharField(
        label="SKU",
        max_length=100,
        required=False,
        help_text="Generated automatically. Manual codes require SKU override permission.",
    )
    unit = forms.ChoiceField(label="Inventory unit", choices=ProductVariant.Unit.choices)
    barcode = forms.CharField(max_length=100, required=False)
    package_content = forms.CharField(
        label="Package content",
        max_length=100,
        required=False,
        help_text="For example, 500 ml or a pack of 6.",
    )

    class Meta:
        model = Product
        fields = [
            "name",
            "sku",
            "unit",
            "barcode",
            "package_content",
            "price",
            "quantity",
            "is_on_sale",
            "discount_percentage",
            "description",
            "category",
            "brand",
            "is_active",
        ]
        labels = {"name": "Product name", "unit": "Selling unit"}
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "price": forms.NumberInput(attrs={"min": 0, "step": "0.01"}),
            "quantity": forms.NumberInput(attrs={"min": 0, "step": 1}),
            "discount_percentage": forms.NumberInput(
                attrs={"min": 1, "max": 100, "step": 1, "inputmode": "numeric"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._creating = self.instance._state.adding
        self.variant = (
            self.instance.default_variant
            if not self._creating
            else ProductVariant(product=self.instance, is_default=True)
        )
        for name, value in {
            "sku": self.variant.sku,
            "unit": self.variant.inventory_unit,
            "barcode": self.variant.barcode,
            "package_content": self.variant.package_content,
        }.items():
            self.initial.setdefault(name, value)
        if "category" in self.fields:
            self.fields["category"].queryset = Category.objects.exclude(
                pk__in=Category.objects.parents()
            ).order_by("name")
        if "brand" in self.fields:
            self.fields["brand"].queryset = Brand.objects.filter(
                Q(is_active=True) | Q(pk=self.instance.brand_id)
            )
            self.fields[
                "brand"
            ].help_text = "Optional. Existing products may keep an inactive brand."

    def clean(self):
        cleaned = super().clean()
        category = cleaned.get("category")
        if cleaned.get("is_active") and category:
            current = category
            seen = set()
            while current and current.pk not in seen:
                seen.add(current.pk)
                if not current.is_active:
                    self.add_error(
                        "is_active",
                        f'This product cannot be activated because the category "{current.name}" '
                        "is inactive. Activate that category first.",
                    )
                    break
                current = current.parent
        if cleaned.get("is_on_sale"):
            if cleaned.get("discount_percentage") is None:
                self.add_error(
                    "discount_percentage", "Enter the percentage discount for this sale."
                )
        else:
            cleaned["discount_percentage"] = None
        return cleaned

    def _post_clean(self):
        super()._post_clean()
        if self.errors:
            return
        for form_name, field in (
            ("sku", "sku"),
            ("unit", "inventory_unit"),
            ("barcode", "barcode"),
            ("package_content", "package_content"),
        ):
            setattr(self.variant, field, self.cleaned_data[form_name])
        try:
            self.variant.full_clean(
                exclude=["product", *(["sku"] if not self.variant.sku and self._creating else [])]
            )
        except ValidationError as error:
            for field, errors in error.message_dict.items():
                name = "unit" if field == "inventory_unit" else field
                self.add_error(name if name in self.fields else None, errors)

    def save(self, commit=True):
        product = super().save(commit=False)
        if self._creating:
            product._default_variant_initial = {
                "sku": self.variant.sku,
                "inventory_unit": self.variant.inventory_unit,
                "barcode": self.variant.barcode,
                "package_content": self.variant.package_content,
            }
        if commit:
            from django.db import transaction

            with transaction.atomic():
                product.save()
                self.save_variant()
                self.save_m2m()
        return product

    def save_variant(self):
        if self._creating:
            self.variant = self.instance.default_variant
        else:
            self.variant.save()
        return self.variant


class VariantForm(forms.ModelForm):
    class Meta:
        model = ProductVariant
        fields = [
            "sku",
            "is_default",
            "barcode",
            "inventory_unit",
            "package_content",
            "attributes",
            "description",
            "is_active",
        ]
        widgets = {
            "attributes": forms.Textarea(attrs={"rows": 2}),
            "description": forms.Textarea(attrs={"rows": 3}),
        }
        help_texts = {
            "sku": "Leave blank to generate a SKU for a new variant.",
            "package_content": "For example, 500 ml or a pack of 6.",
        }

    def _post_clean(self):
        # A new blank SKU is allocated during the atomic save, not during validation.
        if self.instance._state.adding and not self.data.get(self.add_prefix("sku"), "").strip():
            self._generated = True
        super()._post_clean()

    def _get_validation_exclusions(self):
        exclude = super()._get_validation_exclusions()
        # The locked save demotes the previous default before checking its constraint.
        exclude.add("is_default")
        if getattr(self, "_generated", False):
            exclude.add("sku")
        return exclude


class ProductPhotoForm(forms.ModelForm):
    class Meta:
        model = ProductPhoto
        fields = ["image", "alt_text", "position", "is_primary"]
        widgets = {
            "image": forms.ClearableFileInput(attrs={"accept": "image/jpeg,image/png,image/webp"})
        }

    def _get_validation_exclusions(self):
        # The formset checks the selection; the locked save replaces the old primary.
        return super()._get_validation_exclusions() | {"is_primary"}

    def clean_image(self):
        return validate_photo_upload(self.cleaned_data["image"])


class VariantPhotoFormSet(forms.BaseInlineFormSet):
    def add_fields(self, form, index):
        super().add_fields(form, index)
        form.fields["id"].queryset = (
            ProductPhoto.objects.filter(variant=self.instance)
            if self.instance.pk
            else ProductPhoto.objects.none()
        )

    def clean(self):
        super().clean()
        if any(self.errors):
            return
        kept = [
            form for form in self.forms if form.cleaned_data and not form.cleaned_data.get("DELETE")
        ]
        if sum(bool(form.cleaned_data.get("is_primary")) for form in kept) > 1:
            raise ValidationError("Choose only one primary photo for this variant.")
        ids = [form.cleaned_data["id"].pk for form in kept if form.cleaned_data.get("id")]
        if len(ids) != len(set(ids)):
            raise ValidationError("A photo cannot appear more than once.")
