from django import forms
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import HttpResponseBadRequest, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html

from access.audit import record
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

    def get_extra(self, request, obj=None, **kwargs):
        # New products receive several hidden slots so one multi-file selection
        # doesn't depend on the admin dynamically creating each additional form.
        return 4 if obj is None else 1

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
    list_max_show_all = 25
    actions = None

    def changelist_view(self, request, extra_context=None):
        related = Category.objects.exclude(pk__in=Category.objects.parents())
        filter_name = "category__id__exact"
        context = {
            "title": "Inventory",
            "has_change_permission": self.has_change_permission(request),
            "has_delete_permission": self.has_delete_permission(request),
            "can_view_history": request.user.is_superuser,
            "management_filters": [
                {
                    "label": "Category",
                    "name": filter_name,
                    "empty_label": "All categories",
                    "options": [(str(item.pk), item.name) for item in related],
                    "selected": request.GET.get(filter_name, ""),
                },
                {
                    "label": "Sale",
                    "name": "is_on_sale__exact",
                    "empty_label": "All products",
                    "options": [("1", "On sale"), ("0", "Regular price")],
                    "selected": request.GET.get("is_on_sale__exact", ""),
                },
            ],
            **(extra_context or {}),
        }
        return super().changelist_view(request, context)

    def delete_view(self, request, object_id, extra_context=None):
        if request.method == "POST" and request.POST.get("post") != "yes":
            return HttpResponseBadRequest("Confirm deletion before submitting.")
        return super().delete_view(request, object_id, extra_context)


@admin.register(Product, site=site)
class ProductAdmin(ProductAdminBase):
    form = ProductForm
    list_display = ["name", "sku", "category", "unit", "is_active"]
    search_fields = ["name", "description", "sku"]
    list_filter = ["is_active", "is_on_sale", "category", "unit"]
    list_select_related = ["category"]
    fieldsets = [
        (
            "Product details",
            {
                "fields": [
                    "name",
                    ("category", "sku"),
                    ("price", "quantity"),
                    "unit",
                    "description",
                    "is_active",
                    "is_on_sale",
                    "discount_percentage",
                ]
            },
        )
    ]
    inlines = [PhotoInline]

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("photos")

    def get_urls(self):
        return [
            path(
                "<int:object_id>/stock/",
                self.admin_site.admin_view(self.stock_view),
                name="catalog_product_stock",
            ),
        ] + super().get_urls()

    def stock_view(self, request, object_id):
        product = get_object_or_404(self.get_queryset(request), pk=object_id)
        if not self.has_change_permission(request, product):
            raise PermissionDenied
        form = StockForm(request.POST if request.method == "POST" else None)
        if request.method == "POST" and form.is_valid():
            with transaction.atomic():
                product = Product.objects.select_for_update().get(pk=product.pk)
                product.quantity += form.cleaned_data["quantity"]
                if product.quantity > 2147483647:
                    form.add_error("quantity", "The resulting quantity is too large.")
                else:
                    product.save()
                    shipment_number = form.cleaned_data["shipment_number"]
                    record(
                        "stock_received",
                        "catalog.product",
                        product.pk,
                        details={
                            "target_name": product.name,
                            "target_type": "Product",
                            "subject_module": "catalog.product",
                            "subject_id": str(product.pk),
                            "subject_name": product.name,
                            "quantity_added": form.cleaned_data["quantity"],
                            "new_quantity": product.quantity,
                            "shipment_number": shipment_number,
                        },
                        request=request,
                    )
                    message = f"Added {form.cleaned_data['quantity']} units to {product.name}."
                    if shipment_number:
                        message += f" Shipment {shipment_number} was recorded."
                    self.message_user(request, message, messages.SUCCESS)
                    return HttpResponseRedirect(reverse("admin:catalog_product_changelist"))
        return TemplateResponse(
            request,
            "admin/catalog/product/stock.html",
            {
                **self.admin_site.each_context(request),
                "title": "Receive inventory",
                "workspace_header": "Products / Receive inventory",
                "product": product,
                "form": form,
                "opts": self.model._meta,
            },
        )

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


class StockForm(forms.Form):
    quantity = forms.IntegerField(label="Quantity to add", min_value=1, max_value=2147483647)
    shipment_number = forms.CharField(
        label="Shipment number",
        max_length=100,
        required=False,
        help_text="Optional. Add a delivery or shipment reference for the activity log.",
        widget=forms.TextInput(attrs={"placeholder": "e.g. SHP-2026-0042"}),
    )

    def clean_shipment_number(self):
        shipment_number = self.cleaned_data["shipment_number"].strip()
        if shipment_number and not shipment_number.isprintable():
            raise forms.ValidationError("Enter a printable shipment number.")
        return shipment_number
