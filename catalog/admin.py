from django.contrib import admin
from django.db import transaction
from django.db.models import Count, Exists, OuterRef, Q
from django.http import HttpResponseBadRequest, HttpResponseRedirect
from django.urls import path, reverse
from django.utils.html import format_html

from catalog.forms import CategoryForm
from catalog.models import Category
from config.admin import site


@admin.register(Category, site=site)
class CategoryAdmin(admin.ModelAdmin):
    form = CategoryForm
    change_list_template = "admin/catalog/category/change_list.html"
    change_form_template = "admin/catalog/category/change_form.html"
    delete_confirmation_template = "admin/catalog/category/delete_confirmation.html"
    list_display = [
        "photo_thumbnail",
        "name",
        "parent",
        "position",
        "active_status",
        "edit_category",
    ]
    list_display_links = ["name"]
    fieldsets = [
        ("Category details", {"fields": ["name", "parent", "position", "is_active"]}),
        ("Category photo", {"fields": ["photo", "photo_x", "photo_y", "photo_zoom"]}),
    ]

    def get_urls(self):
        return [
            path(
                "parents/",
                self.admin_site.admin_view(self.changelist_view),
                name="catalog_parent_categories",
            ),
        ] + super().get_urls()

    def get_list_display(self, request):
        if request.resolver_match.url_name == "catalog_parent_categories":
            return [
                "photo_thumbnail",
                "name",
                "category_count",
                "position",
                "active_status",
                "edit_category",
            ]
        return super().get_list_display(request)

    @admin.display(description="Categories", ordering="child_count")
    def category_count(self, obj):
        return obj.child_count

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if request.resolver_match.url_name == "catalog_parent_categories":
            return (
                queryset.alias(
                    has_children=Exists(Category.objects.filter(parent_id=OuterRef("pk")))
                )
                .filter(Q(is_parent_category=True) | Q(has_children=True))
                .annotate(child_count=Count("children", distinct=True))
            )
        if request.resolver_match.url_name == "catalog_category_changelist":
            # Keep parent records accessible on their edit/photo pages, but out
            # of this list, including legacy entries already used as parents.
            queryset = queryset.alias(
                has_children=Exists(Category.objects.filter(parent_id=OuterRef("pk")))
            ).filter(is_parent_category=False, has_children=False)
        return queryset

    def get_fieldsets(self, request, obj=None):
        if (obj is None and request.GET.get("kind") == "parent") or (
            obj is not None and obj.is_parent_category
        ):
            return [
                ("Parent category details", {"fields": ["name", "position", "is_active"]}),
                self.fieldsets[1],
            ]
        return super().get_fieldsets(request, obj)

    def add_view(self, request, form_url="", extra_context=None):
        context = dict(extra_context or {})
        context["adding_parent"] = request.GET.get("kind") == "parent"
        if context["adding_parent"]:
            context["title"] = "Add parent category"
        return super().add_view(request, form_url, context)

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
            '<span class="category-row-actions"><a href="{}">Edit</a>'
            '<a class="category-delete-link" href="{}">Delete</a></span>',
            reverse("admin:catalog_category_change", args=[obj.pk]),
            reverse("admin:catalog_category_delete", args=[obj.pk]),
        )

    @admin.display(description="Is active", ordering="is_active")
    def active_status(self, obj):
        return format_html(
            '<input type="checkbox" class="category-status-checkbox" disabled {} aria-label="{}">',
            "checked" if obj.is_active else "",
            "Active" if obj.is_active else "Inactive",
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
        context["is_parent_list"] = request.resolver_match.url_name == "catalog_parent_categories"
        if context["is_parent_list"]:
            context["title"] = "Parent categories"
        context.update(
            {
                "category_parents": Category.objects.parents().order_by("name"),
                "selected_parent": request.GET.get("parent__id__exact", ""),
                "selected_status": request.GET.get("is_active__exact", ""),
                "category_metrics": self.get_queryset(request).aggregate(
                    total=Count("pk"),
                    active=Count("pk", filter=Q(is_active=True)),
                    inactive=Count("pk", filter=Q(is_active=False)),
                    independent=Count("pk", filter=Q(parent__isnull=True)),
                ),
            }
        )
        if context["is_parent_list"]:
            context["category_metrics"]["independent"] = (
                self.get_queryset(request).filter(has_children=False).count()
            )
        return super().changelist_view(request, context)

    def response_post_save_add(self, request, obj):
        if obj.is_parent_category:
            return HttpResponseRedirect(reverse("admin:catalog_parent_categories"))
        return super().response_post_save_add(request, obj)

    def response_post_save_change(self, request, obj):
        if obj.is_parent_category:
            return HttpResponseRedirect(reverse("admin:catalog_parent_categories"))
        return super().response_post_save_change(request, obj)

    list_filter = ["is_active", "parent"]
    search_fields = ["name", "=id"]
    list_editable = ["position"]
    list_per_page = 25
    list_select_related = ["parent"]
    actions = None

    def save_model(self, request, obj, form, change):
        old_photo = Category.objects.get(pk=obj.pk).photo if change else None
        if not change and request.GET.get("kind") == "parent":
            obj.is_parent_category = True
        super().save_model(request, obj, form, change)
        if old_photo and old_photo.name != obj.photo.name:
            transaction.on_commit(lambda: old_photo.storage.delete(old_photo.name))

    def delete_view(self, request, object_id, extra_context=None):
        if request.method == "POST" and request.POST.get("post") != "yes":
            return HttpResponseBadRequest("Confirm deletion before submitting.")
        obj = self.get_object(request, object_id)
        request.deleting_parent_category = bool(
            obj and (obj.is_parent_category or obj.children.exists())
        )
        context = dict(extra_context or {})
        context["deleting_parent_category"] = request.deleting_parent_category
        return super().delete_view(request, object_id, context)

    def response_delete(self, request, obj_display, obj_id):
        if getattr(request, "deleting_parent_category", False):
            return HttpResponseRedirect(reverse("admin:catalog_parent_categories"))
        return super().response_delete(request, obj_display, obj_id)
