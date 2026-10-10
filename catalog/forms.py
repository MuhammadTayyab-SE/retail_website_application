from django import forms
from django.core.exceptions import ValidationError

from catalog.models import Category


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
