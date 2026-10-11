from django import forms
from django.core.exceptions import ValidationError

from catalog.models import Category, Product, ProductPhoto


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
        photo = self.cleaned_data.get("photo")
        if photo and hasattr(photo, "content_type"):
            if photo.size > 8 * 1024 * 1024:
                raise ValidationError("Choose a photo smaller than 8 MB.")
            if photo.image.format not in {"JPEG", "PNG", "WEBP"}:
                raise ValidationError("Choose a JPEG, PNG or WebP photo.")
            extension = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}[photo.image.format]
            photo.name = f"photo.{extension}"
        return photo


class ProductForm(forms.ModelForm):
    sku = forms.CharField(label="SKU", max_length=100)
    unit = forms.ChoiceField(choices=[("", "Choose a unit"), *Product.Unit.choices])

    class Meta:
        model = Product
        fields = [
            "name",
            "sku",
            "unit",
            "price",
            "quantity",
            "is_on_sale",
            "discount_percentage",
            "description",
            "category",
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
        if "category" in self.fields:
            self.fields["category"].queryset = Category.objects.exclude(
                pk__in=Category.objects.parents()
            ).order_by("name")

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


class ProductPhotoForm(forms.ModelForm):
    class Meta:
        model = ProductPhoto
        fields = ["image", "alt_text", "position"]
        widgets = {
            "image": forms.ClearableFileInput(attrs={"accept": "image/jpeg,image/png,image/webp"})
        }

    def clean_image(self):
        image = self.cleaned_data["image"]
        if hasattr(image, "content_type"):
            if image.size > 8 * 1024 * 1024:
                raise ValidationError("Choose a photo smaller than 8 MB.")
            if image.image.format not in {"JPEG", "PNG", "WEBP"}:
                raise ValidationError("Choose a JPEG, PNG or WebP photo.")
            extension = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}[image.image.format]
            image.name = f"photo.{extension}"
        return image
