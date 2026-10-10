from django.contrib.admin import AdminSite
from django.contrib.admin.forms import AdminAuthenticationForm


class RetailAdminAuthenticationForm(AdminAuthenticationForm):
    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if not user.is_superuser:
            raise self.get_invalid_login_error()


class RetailAdminSite(AdminSite):
    login_form = RetailAdminAuthenticationForm
    site_header = "Retail administration"
    site_title = "Retail admin"

    def has_permission(self, request):
        user = request.user
        return user.is_active and user.is_staff and user.is_superuser


site = RetailAdminSite(name="admin")
