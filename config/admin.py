from django.contrib.admin import AdminSite
from django.contrib.admin.forms import AdminAuthenticationForm


class RetailAdminAuthenticationForm(AdminAuthenticationForm):
    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if not user.is_superuser:
            raise self.get_invalid_login_error()


class RetailAdminSite(AdminSite):
    login_form = RetailAdminAuthenticationForm
    login_template = "retail_admin/login.html"
    index_template = "retail_admin/index.html"
    index_title = "Store overview"
    site_header = "Retail administration"
    site_title = "Retail admin"

    def has_permission(self, request):
        user = request.user
        return user.is_active and user.is_staff and user.is_superuser

    def index(self, request, extra_context=None):
        from django.db.models import Count, Q

        from catalog.models import Category

        context = dict(extra_context or {})
        if self.has_permission(request):
            context["category_summary"] = Category.objects.aggregate(
                total=Count("pk"),
                active=Count("pk", filter=Q(is_active=True)),
                inactive=Count("pk", filter=Q(is_active=False)),
                roots=Count("pk", filter=Q(parent__isnull=True)),
            )
            context["recent_categories"] = Category.objects.select_related("parent").order_by(
                "-pk"
            )[:5]
        return super().index(request, extra_context=context)


site = RetailAdminSite(name="admin")
