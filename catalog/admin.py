from django.contrib import admin
from django.db import transaction
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.html import format_html

from catalog.forms import CategoryForm
from catalog.models import Category
from config.admin import site


@admin.register(Category, site=site)
class CategoryAdmin(admin.ModelAdmin):
    form = CategoryForm
    change_list_template = "admin/catalog/category/change_list.html"
    change_form_template = "admin/catalog/category/change_form.html"
    list_display = ["photo_thumbnail", "name", "parent", "position", "is_active", "edit_category"]
    list_display_links = ["name"]
    fieldsets = [
        ("Category details", {"fields": ["name", "parent", "position", "is_active"]}),
        ("Category photo", {"fields": ["photo", "photo_x", "photo_y", "photo_zoom"]}),
    ]

    @admin.display(description="Photo")
    def photo_thumbnail(self, obj):
        if not obj.photo:
            return format_html('<span class="category-photo-placeholder">{}</span>', "No photo")
        return format_html(
            '<span class="category-thumb"><img src="{}" alt="" '
            'style="object-position:{}% {}%;transform:scale({})"></span>',
            reverse("category-photo", args=[obj.pk]),
            obj.photo_x,
            obj.photo_y,
            obj.photo_zoom / 100,
        )

    @admin.display(description="Actions")
    def edit_category(self, obj):
        return format_html(
            '<a href="{}">Edit</a>', reverse("admin:catalog_category_change", args=[obj.pk])
        )

    def changelist_view(self, request, extra_context=None):
        filters = request.GET.copy()
        for name in ("is_active__exact", "parent__id__exact"):
            if name in filters and not filters[name]:
                del filters[name]
        if filters != request.GET:
            query = filters.urlencode()
            return HttpResponseRedirect(request.path + ("?" + query if query else ""))
        context = dict(extra_context or {})
        context.update(
            {
                "category_parents": Category.objects.order_by("name"),
                "selected_parent": request.GET.get("parent__id__exact", ""),
                "selected_status": request.GET.get("is_active__exact", ""),
            }
        )
        return super().changelist_view(request, context)

    list_filter = ["is_active", "parent"]
    search_fields = ["name", "=id"]
    list_editable = ["position", "is_active"]
    list_select_related = ["parent"]
    actions = None

    def save_model(self, request, obj, form, change):
        old_photo = Category.objects.get(pk=obj.pk).photo if change else None
        super().save_model(request, obj, form, change)
        if old_photo and old_photo.name != obj.photo.name:
            transaction.on_commit(lambda: old_photo.storage.delete(old_photo.name))

    def has_delete_permission(self, request, obj=None):
        return False
