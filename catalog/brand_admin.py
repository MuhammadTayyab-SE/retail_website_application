from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.db.models import Count
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from django.urls import path, reverse
from django.utils.html import format_html
from django.views.decorators.http import require_safe

from catalog.forms import BrandForm
from catalog.models import Brand
from config.admin import site


@admin.register(Brand, site=site)
class BrandAdmin(admin.ModelAdmin):
    form = BrandForm
    change_list_template = "admin/catalog/brand/change_list.html"
    change_form_template = "admin/catalog/brand/change_form.html"
    list_display = ["logo_preview", "name", "is_active", "product_count"]
    search_fields = ["name", "description"]
    list_filter = ["is_active"]
    list_per_page = 25
    list_max_show_all = 25
    actions = None
    readonly_fields = ["logo_preview", "created_by", "created_at", "updated_by", "updated_at"]
    fieldsets = [
        ("Brand information", {"fields": ["name", "description", "is_active"]}),
        ("Logo", {"fields": ["logo_preview", "logo"]}),
        (
            "Record history",
            {
                "fields": ["created_by", "created_at", "updated_by", "updated_at"],
                "classes": ["collapse"],
            },
        ),
    ]

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(associated_product_count=Count("products"))

    def changelist_view(self, request, extra_context=None):
        context = {
            "can_edit_brands": self.has_change_permission(request),
            "can_view_brand_products": request.user.has_perm("catalog.view_product")
            or request.user.has_perm("catalog.change_product"),
            **(extra_context or {}),
        }
        return super().changelist_view(request, context)

    def get_object(self, request, object_id, from_field=None):
        obj = super().get_object(request, object_id, from_field)
        if obj is not None and request.method == "POST":
            # ModelAdmin wraps POST in a transaction; bind files against the locked current row.
            return Brand.objects.select_for_update().filter(pk=obj.pk).first()
        return obj

    def get_list_display(self, request):
        columns = list(self.list_display)
        if request.user.has_perm("catalog.view_product") or request.user.has_perm(
            "catalog.change_product"
        ):
            columns[-1] = "linked_products"
        return columns

    @admin.display(description="Products", ordering="associated_product_count")
    def product_count(self, obj):
        return obj.associated_product_count

    @admin.display(description="Products", ordering="associated_product_count")
    def linked_products(self, obj):
        return format_html(
            '<a href="{}?brand__id__exact={}">{} product{}</a>',
            reverse("admin:catalog_product_changelist"),
            obj.pk,
            obj.associated_product_count,
            "" if obj.associated_product_count == 1 else "s",
        )

    @admin.display(description="Logo")
    def logo_preview(self, obj):
        if not obj or not obj.pk or not obj.logo:
            return "No logo"
        return format_html(
            '<img class="brand-logo" src="{}" alt="{}">',
            reverse("admin:catalog_brand_logo", args=[obj.pk]),
            obj.name,
        )

    def has_delete_permission(self, request, obj=None):
        return False

    def get_urls(self):
        return [
            path(
                "<int:object_id>/logo/",
                self.admin_site.admin_view(require_safe(self.logo_view)),
                name="catalog_brand_logo",
            )
        ] + super().get_urls()

    def logo_view(self, request, object_id):
        if not self.has_view_permission(request):
            raise PermissionDenied
        brand = get_object_or_404(Brand, pk=object_id)
        if not brand.logo:
            raise Http404
        content_type = {"jpg": "image/jpeg", "png": "image/png", "webp": "image/webp"}.get(
            brand.logo.name.rsplit(".", 1)[-1].lower()
        )
        if not content_type:
            raise Http404
        try:
            response = FileResponse(brand.logo.open("rb"), content_type=content_type)
        except FileNotFoundError as error:
            raise Http404 from error
        response["X-Content-Type-Options"] = "nosniff"
        return response
