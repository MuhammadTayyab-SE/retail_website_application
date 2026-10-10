from django.contrib.admin import AdminSite
from django.contrib.admin.forms import AdminAuthenticationForm
from django.template.response import TemplateResponse
from django.urls import path

from access.models import WorkerProfile


class RetailAdminAuthenticationForm(AdminAuthenticationForm):
    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if not user.is_superuser and not (
            user.pk and WorkerProfile.objects.filter(user=user, role__isnull=False).exists()
        ):
            raise self.get_invalid_login_error()


class RetailAdminSite(AdminSite):
    login_form = RetailAdminAuthenticationForm
    login_template = "retail_admin/login.html"
    index_template = "retail_admin/index.html"
    index_title = "Store overview"
    site_header = "Retail administration"
    site_title = "Retail admin"

    def get_app_list(self, request, app_label=None):
        apps = super().get_app_list(request, app_label)
        names = {"User": "Workers", "AuditEvent": "Activity log"}
        for app in apps:
            if app["app_label"] == "auth":
                app["name"] = "Employees"
            for model in app["models"]:
                model["name"] = names.get(model["object_name"], model["name"])
        return apps

    def each_context(self, request):
        context = super().each_context(request)
        route = request.resolver_match.url_name if request.resolver_match else ""
        context["workspace_header"] = {
            "index": "Overview",
            "catalog_category_changelist": "Categories",
            "catalog_parent_categories": "Parent categories",
            "settings": "Settings",
            "password_change": "Settings / Change password",
            "password_change_done": "Settings / Change password",
            "auth_user_changelist": "Workers",
            "auth_user_add": "Workers / Add worker",
            "auth_user_change": "Workers / Account",
            "auth_user_password_change": "Workers / Reset password",
            "access_role_changelist": "Roles",
            "access_role_add": "Roles / Add role",
            "access_role_change": "Roles / Edit role",
            "access_auditevent_changelist": "Activity log",
            "access_auditevent_change": "Activity log / Entry",
        }.get(route)
        context["can_view_categories"] = request.user.has_perm(
            "catalog.view_category"
        ) or request.user.has_perm("catalog.change_category")
        context["can_view_parents"] = request.user.has_perm(
            "catalog.view_parentcategory"
        ) or request.user.has_perm("catalog.change_parentcategory")
        context["can_add_categories"] = request.user.has_perm("catalog.add_category")
        context["can_add_parents"] = request.user.has_perm("catalog.add_parentcategory")
        if request.user.is_authenticated and not request.user.is_superuser:
            context["worker_role"] = (
                WorkerProfile.objects.filter(user=request.user).select_related("role").first()
            )
        return context

    def get_urls(self):
        return [
            path("settings/", self.admin_view(self.settings_view), name="settings"),
        ] + super().get_urls()

    def settings_view(self, request):
        return TemplateResponse(
            request,
            "retail_admin/settings.html",
            {**self.each_context(request), "title": "Settings"},
        )

    def has_permission(self, request):
        user = request.user
        if not user.is_active or not user.is_staff:
            return False
        return bool(
            user.is_superuser
            or (user.pk and WorkerProfile.objects.filter(user=user, role__isnull=False).exists())
        )

    def index(self, request, extra_context=None):
        from django.db.models import Count, Exists, OuterRef, Q

        from catalog.models import Category

        context = dict(extra_context or {})
        if not request.user.is_superuser:
            return TemplateResponse(
                request,
                "retail_admin/worker_index.html",
                {
                    **self.each_context(request),
                    **context,
                    "title": "Dashboard",
                },
            )
        if self.has_permission(request) and (
            request.user.has_perm("catalog.view_category")
            or request.user.has_perm("catalog.change_category")
        ):
            entries = Category.objects.alias(
                has_children=Exists(Category.objects.filter(parent_id=OuterRef("pk")))
            )
            categories = entries.filter(is_parent_category=False, has_children=False)
            context["parent_category_count"] = (
                entries.filter(Q(is_parent_category=True) | Q(has_children=True)).count()
                if request.user.has_perm("catalog.view_parentcategory")
                or request.user.has_perm("catalog.change_parentcategory")
                else None
            )
            context["category_summary"] = categories.aggregate(
                total=Count("pk"),
                active=Count("pk", filter=Q(is_active=True)),
                inactive=Count("pk", filter=Q(is_active=False)),
                roots=Count("pk", filter=Q(parent__isnull=True)),
            )
            context["recent_categories"] = categories.select_related("parent").order_by("-pk")[:5]
        return super().index(request, extra_context=context)


site = RetailAdminSite(name="admin")
