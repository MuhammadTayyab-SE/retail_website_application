from django.contrib.admin import AdminSite
from django.contrib.admin.forms import AdminAuthenticationForm
from django.template.response import TemplateResponse
from django.urls import path


class RetailAdminAuthenticationForm(AdminAuthenticationForm):
    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if not user.is_superuser:
            raise self.get_invalid_login_error()


class RetailAdminSite(AdminSite):
    login_form = RetailAdminAuthenticationForm
    login_template = "retail_admin/login.html"
    site_header = "Retail administration"
    site_title = "Retail admin"

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
        }.get(route)
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
        return user.is_active and user.is_staff and user.is_superuser

    def index(self, request, extra_context=None):
        from django.db.models import Count, Exists, OuterRef, Q

        from catalog.models import Category

        context = dict(extra_context or {})
        if self.has_permission(request):
            entries = Category.objects.alias(
                has_children=Exists(Category.objects.filter(parent_id=OuterRef("pk")))
            )
            categories = entries.filter(is_parent_category=False, has_children=False)
            context["parent_category_count"] = entries.filter(
                Q(is_parent_category=True) | Q(has_children=True)
            ).count()
            context["category_summary"] = categories.aggregate(
                total=Count("pk"),
                active=Count("pk", filter=Q(is_active=True)),
                inactive=Count("pk", filter=Q(is_active=False)),
                roots=Count("pk", filter=Q(parent__isnull=True)),
            )
            context["recent_categories"] = categories.select_related("parent").order_by("-pk")[:5]
        return super().index(request, extra_context=context)


site = RetailAdminSite(name="admin")
