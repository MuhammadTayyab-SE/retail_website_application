from django.contrib import admin
from django.db import transaction
from django.db.models import Count, Q
from django.http import HttpResponseBadRequest
from django.urls import reverse
from django.utils.html import format_html

from catalog.admin_widgets import PlainRelatedChoicesMixin
from catalog.forms import ProductForm, ProductPhotoForm
from catalog.models import Category, Product, ProductPhoto
from config.admin import site


class PhotoInline(admin.StackedInline):
    model = ProductPhoto
    form = ProductPhotoForm
    fields = ["preview", "image", "alt_text", "position"]
    readonly_fields = ["preview"]
    extra = 1

    @admin.display(description="Preview")
    def preview(self, obj):
        if not obj.pk or not obj.image:
            return "Select a photo and save to preview."
        return format_html(
            '<img class="product-photo-thumb" src="{}" alt="{}">',
            reverse("product-photo", args=[obj.pk]),
            obj.alt_text,
        )

    def has_view_permission(self, request, obj=None):
        return request.user.has_perm("catalog.view_product") or request.user.has_perm(
            "catalog.change_product"
        )

    def has_add_permission(self, request, obj=None):
        return (
            request.user.has_perm("catalog.add_product")
            if obj is None
            else request.user.has_perm("catalog.change_product")
        )

    def has_change_permission(self, request, obj=None):
        return request.user.has_perm("catalog.change_product")

    def has_delete_permission(self, request, obj=None):
        return self.has_change_permission(request, obj)


class ProductAdminBase(PlainRelatedChoicesMixin, admin.ModelAdmin):
    change_form_template = "admin/catalog/product/change_form.html"
    change_list_template = "admin/catalog/product/change_list.html"
    delete_confirmation_template = "admin/catalog/product/delete_confirmation.html"
    readonly_fields = ["created_by", "created_at", "updated_by", "updated_at"]
    list_per_page = 25
    actions = None

    def changelist_view(self, request, extra_context=None):
        related = Category.objects.exclude(pk__in=Category.objects.parents())
        filter_name = "category__id__exact"
        context = {
            "title": "Products",
            "has_change_permission": self.has_change_permission(request),
            "has_delete_permission": self.has_delete_permission(request),
            "product_metrics": self.get_queryset(request).aggregate(
                total=Count("pk", distinct=True),
                active=Count("pk", filter=Q(is_active=True), distinct=True),
                inactive=Count("pk", filter=Q(is_active=False), distinct=True),
            ),
            "management_filters": [
                {
                    "label": "Status",
                    "name": "is_active__exact",
                    "empty_label": "All statuses",
                    "options": [("1", "Active"), ("0", "Inactive")],
                    "selected": request.GET.get("is_active__exact", ""),
                },
                {
                    "label": "Category",
                    "name": filter_name,
                    "empty_label": "All categories",
                    "options": [(str(item.pk), item.name) for item in related],
                    "selected": request.GET.get(filter_name, ""),
                },
                {
                    "label": "Unit",
                    "name": "unit__exact",
                    "empty_label": "All units",
                    "options": Product.Unit.choices,
                    "selected": request.GET.get("unit__exact", ""),
                },
            ],
            **(extra_context or {}),
        }
        return super().changelist_view(request, context)

    def get_fieldsets(self, request, obj=None):
        fields = list(super().get_fieldsets(request, obj))
        if obj:
            fields.append(("Record history", {"fields": self.readonly_fields}))
        return fields

    def delete_view(self, request, object_id, extra_context=None):
        if request.method == "POST" and request.POST.get("post") != "yes":
            return HttpResponseBadRequest("Confirm deletion before submitting.")
        return super().delete_view(request, object_id, extra_context)


@admin.register(Product, site=site)
class ProductAdmin(ProductAdminBase):
    form = ProductForm
    list_display = ["name", "sku", "category", "unit", "is_active"]
    search_fields = ["name", "description", "sku"]
    list_filter = ["is_active", "category", "unit"]
    list_select_related = ["category"]
    fieldsets = [
        (
            "Product details",
            {"fields": ["name", "sku", "unit", "category", "description", "is_active"]},
        )
    ]
    inlines = [PhotoInline]

    def save_formset(self, request, form, formset, change):
        if formset.model is ProductPhoto:
            previous = {
                photo.pk: photo.image
                for photo in ProductPhoto.objects.filter(product=form.instance)
            }
            instances = formset.save(commit=False)
            for photo in formset.deleted_objects:
                photo.delete()
            for photo in instances:
                old = previous.get(photo.pk)
                photo.save()
                if old and old.name != photo.image.name:
                    transaction.on_commit(lambda old=old: old.storage.delete(old.name))
            formset.save_m2m()
        else:
            super().save_formset(request, form, formset, change)
