from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Count, Exists, OuterRef, Q
from django.http import HttpResponseBadRequest, HttpResponseRedirect
from django.urls import path, reverse
from django.utils.html import format_html, format_html_join

from catalog.forms import CategoryForm
from catalog.models import Category
from config.admin import site


@admin.register(Category, site=site)
class CategoryAdmin(admin.ModelAdmin):
    readonly_fields = ["created_by", "created_at", "updated_by", "updated_at"]

    def _parent_record(self, request, obj=None):
        if obj is not None:
            return obj.is_parent_category or obj.children.exists()
        match = request.resolver_match
        return bool(
            (match and match.url_name == "catalog_parent_categories")
            or request.GET.get("kind") == "parent"
        )

    def _allowed(self, request, action, obj=None):
        model = "parentcategory" if self._parent_record(request, obj) else "category"
        return request.user.has_perm(f"catalog.{action}_{model}")

    def has_module_permission(self, request):
        return any(
            request.user.has_perm(f"catalog.{action}_{model}")
            for model in ("category", "parentcategory")
            for action in ("view", "add", "change", "delete")
        )

    def has_view_permission(self, request, obj=None):
        return self._allowed(request, "view", obj) or self._allowed(request, "change", obj)

    def has_add_permission(self, request):
        return self._allowed(request, "add")

    def has_change_permission(self, request, obj=None):
        return self._allowed(request, "change", obj)

    def has_delete_permission(self, request, obj=None):
        return self._allowed(request, "delete", obj)

    def get_deleted_objects(self, objs, request):
        deleted, counts, permissions, protected = super().get_deleted_objects(objs, request)
        for obj in objs:
            for child in Category.objects.filter(pk__in=self._descendant_ids(obj)):
                if not self.has_delete_permission(request, child):
                    permissions.add("categories")
        return deleted, counts, permissions, protected

    def _descendant_ids(self, obj):
        seen, pending = set(), {obj.pk}
        while pending:
            seen.update(pending)
            pending = (
                set(Category.objects.filter(parent_id__in=pending).values_list("pk", flat=True))
                - seen
            )
        return seen

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
        @admin.display(description="Actions")
        def permitted_actions(obj):
            links = []
            if self.has_view_permission(request, obj):
                links.append(
                    format_html(
                        '<a href="{}">{}</a>',
                        reverse("admin:catalog_category_change", args=[obj.pk]),
                        "Edit" if self.has_change_permission(request, obj) else "View",
                    )
                )
            if self.has_delete_permission(request, obj):
                links.append(
                    format_html(
                        '<a class="category-delete-link" href="{}">Delete</a>',
                        reverse("admin:catalog_category_delete", args=[obj.pk]),
                    )
                )
            return format_html(
                '<span class="category-row-actions">{}</span>',
                format_html_join("", "{}", ((link,) for link in links)),
            )

        permitted_actions.__name__ = "edit_category"
        if request.resolver_match.url_name == "catalog_parent_categories":
            return [
                "photo_thumbnail",
                "name",
                "category_count",
                "position",
                "active_status",
                permitted_actions,
            ]
        fields = list(super().get_list_display(request))
        fields[-1] = permitted_actions
        if not (
            request.user.has_perm("catalog.view_parentcategory")
            or request.user.has_perm("catalog.change_parentcategory")
        ):
            fields.remove("parent")
        return fields

    def get_list_editable(self, request):
        return self.list_editable if self.has_change_permission(request) else []

    def get_changelist_instance(self, request):
        result = super().get_changelist_instance(request)
        result.list_editable = self.get_list_editable(request)
        return result

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
            fieldsets = [
                ("Parent category details", {"fields": ["name", "position", "is_active"]}),
                self.fieldsets[1],
            ]
        else:
            fieldsets = list(super().get_fieldsets(request, obj))
            if not (
                request.user.has_perm("catalog.view_parentcategory")
                or request.user.has_perm("catalog.change_parentcategory")
            ):
                fieldsets[0] = (
                    fieldsets[0][0],
                    {"fields": [f for f in fieldsets[0][1]["fields"] if f != "parent"]},
                )
        if obj:
            fieldsets.append(
                ("Record history (blank means legacy / unknown)", {"fields": self.readonly_fields})
            )
        return fieldsets

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
        if not self.has_view_permission(request):
            raise PermissionDenied
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
            context["title"] = "Parent Categories"
        context.update(
            {
                "category_parents": Category.objects.parents().order_by("name")
                if (
                    request.user.has_perm("catalog.view_parentcategory")
                    or request.user.has_perm("catalog.change_parentcategory")
                )
                else Category.objects.none(),
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
