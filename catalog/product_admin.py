from django.contrib import admin
from django.db import transaction
from django.db.models import Count
from django.http import HttpResponseBadRequest
from django.urls import reverse
from django.utils.html import format_html

from catalog.forms import ProductForm, ProductPhotoForm, VariantInlineFormSet
from catalog.models import Category, Product, ProductPhoto, ProductVariant
from config.admin import site


class VariantInline(admin.TabularInline):
    model = ProductVariant
    fields = ["sku", "attributes", "is_active"]
    formset = VariantInlineFormSet
    extra = 1
    min_num = 1
    validate_min = True

    def get_formset(self, request, obj=None, **kwargs):
        # Require a variant when the user can add them. Read-only editing remains possible.
        kwargs["validate_min"] = self.has_add_permission(request, obj)
        return super().get_formset(request, obj, **kwargs)


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


class ProductAdminBase(admin.ModelAdmin):
    change_form_template = "admin/access/management_form.html"
    change_list_template = "admin/catalog/product/change_list.html"
    delete_confirmation_template = "admin/catalog/product/delete_confirmation.html"
    readonly_fields = ["created_by", "created_at", "updated_by", "updated_at"]
    list_per_page = 25
    actions = None

    def get_fieldsets(self, request, obj=None):
        fields = list(super().get_fieldsets(request, obj))
        if obj:
            fields.append(("Record history", {"fields": self.readonly_fields}))
        return fields

    def delete_view(self, request, object_id, extra_context=None):
        if request.method == "POST" and request.POST.get("post") != "yes":
            return HttpResponseBadRequest("Confirm deletion before submitting.")
        return super().delete_view(request, object_id, extra_context)

    def get_list_display(self, request):
        @admin.display(description="Actions")
        def row_actions(obj):
            from django.utils.html import format_html_join

            links = [
                format_html(
                    '<a href="{}">{}</a>',
                    reverse(f"admin:catalog_{self.opts.model_name}_change", args=[obj.pk]),
                    "Manage" if self.has_change_permission(request, obj) else "View",
                )
            ]
            if self.has_delete_permission(request, obj):
                links.append(
                    format_html(
                        '<a class="category-delete-link" href="{}">Delete</a>',
                        reverse(f"admin:catalog_{self.opts.model_name}_delete", args=[obj.pk]),
                    )
                )
            return format_html(
                '<span class="category-row-actions">{}</span>',
                format_html_join("", "{}", ((link,) for link in links)),
            )

        return [*super().get_list_display(request), row_actions]


@admin.register(Product, site=site)
class ProductAdmin(ProductAdminBase):
    form = ProductForm
    list_display = ["name", "category", "variant_count", "is_active"]
    search_fields = ["name", "description", "variants__sku"]
    list_filter = ["is_active", "category"]
    list_select_related = ["category"]
    fieldsets = [("Product details", {"fields": ["name", "description", "category", "is_active"]})]
    inlines = [VariantInline, PhotoInline]

    def changelist_view(self, request, extra_context=None):
        return super().changelist_view(
            request,
            {
                "product_categories": Category.objects.exclude(pk__in=Category.objects.parents()),
                "title": "Products",
                "selected_category": request.GET.get("category__id__exact", ""),
                **(extra_context or {}),
            },
        )

    def get_queryset(self, request):
        return (
            super().get_queryset(request).annotate(variants_total=Count("variants", distinct=True))
        )

    @admin.display(description="Variants", ordering="variants_total")
    def variant_count(self, obj):
        return obj.variants_total

    def has_add_permission(self, request):
        # An initial variant is required when creating a product.
        return super().has_add_permission(request) and request.user.has_perm(
            "catalog.add_productvariant"
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


@admin.register(ProductVariant, site=site)
class ProductVariantAdmin(ProductAdminBase):
    list_display = ["sku", "product", "is_active"]
    list_filter = ["is_active", "product"]
    search_fields = ["sku", "product__name"]
    list_select_related = ["product"]
    fieldsets = [("Variant details", {"fields": ["product", "sku", "attributes", "is_active"]})]


# Register during the catalog app's normal admin autodiscovery.
