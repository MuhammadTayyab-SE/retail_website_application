from django import forms
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm
from django.contrib.auth.models import Permission
from django.urls import reverse
from django.utils.html import format_html

from access.models import AuditEvent, Role, WorkerProfile
from config.admin import site


class SuperAdminOnly:
    def has_module_permission(self, request):
        return request.user.is_active and request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_add_permission(self, request):
        return self.has_module_permission(request)

    def has_change_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_delete_permission(self, request, obj=None):
        return self.has_module_permission(request)


class WorkerFormMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["role"] = forms.ModelChoiceField(
            queryset=Role.objects.all(),
            required=False,
            help_text="No role means no module access. Super Admins always have full access.",
        )
        if self.instance.pk:
            self.fields["role"].initial = (
                WorkerProfile.objects.filter(user=self.instance)
                .values_list("role_id", flat=True)
                .first()
            )


class WorkerChangeForm(WorkerFormMixin, UserChangeForm):
    role = forms.ModelChoiceField(queryset=Role.objects.all(), required=False)
    password = None


class WorkerCreationForm(WorkerFormMixin, UserCreationForm):
    role = forms.ModelChoiceField(queryset=Role.objects.all(), required=False)

    class Meta(UserCreationForm.Meta):
        model = get_user_model()
        fields = ("username", "first_name", "last_name", "email")


@admin.register(get_user_model(), site=site)
class WorkerAdmin(SuperAdminOnly, UserAdmin):
    form = WorkerChangeForm
    add_form = WorkerCreationForm
    list_display = ["username", "first_name", "last_name", "role_name", "is_active", "is_superuser"]
    list_filter = ["is_active", "is_superuser", "workerprofile__role"]
    fieldsets = [
        ("Account", {"fields": ["username", "first_name", "last_name", "email"]}),
        ("Access", {"fields": ["is_active", "role", "reset_password"]}),
    ]
    add_fieldsets = [
        (
            "New worker",
            {
                "fields": [
                    "username",
                    "first_name",
                    "last_name",
                    "email",
                    "password1",
                    "password2",
                    "role",
                    "is_active",
                ]
            },
        ),
    ]
    readonly_fields = ["reset_password"]
    filter_horizontal = []
    actions = None

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("workerprofile__role")

    def changelist_view(self, request, extra_context=None):
        return super().changelist_view(request, {**(extra_context or {}), "title": "Workers"})

    @admin.display(description="Assigned role")
    def role_name(self, obj):
        profile = getattr(obj, "workerprofile", None)
        return (
            "Super Admin"
            if obj.is_superuser
            else (profile.role if profile and profile.role else "No role")
        )

    @admin.display(description="Password")
    def reset_password(self, obj):
        return format_html(
            '<a href="{}">Set a new password</a>',
            reverse("admin:auth_user_password_change", args=[obj.pk]),
        )

    def save_model(self, request, obj, form, change):
        obj.is_staff = True
        super().save_model(request, obj, form, change)
        WorkerProfile.objects.update_or_create(
            user=obj, defaults={"role": form.cleaned_data["role"]}
        )

    def has_delete_permission(self, request, obj=None):
        # Deactivate accounts to retain authorship and prevent accidental owner removal.
        return False

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        context = dict(extra_context or {})
        context["title"] = "Worker account" if object_id else "Add worker"
        return super().changeform_view(request, object_id, form_url, context)


@admin.register(Role, site=site)
class RoleAdmin(SuperAdminOnly, admin.ModelAdmin):
    list_display = ["name"]
    search_fields = ["name"]
    filter_horizontal = ["permissions"]

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if db_field.name == "permissions":
            # Account/role/audit administration is never delegated.
            kwargs["queryset"] = Permission.objects.filter(
                content_type__app_label="catalog"
            ).order_by("content_type__model", "codename")
        return super().formfield_for_manytomany(db_field, request, **kwargs)


@admin.register(AuditEvent, site=site)
class AuditEventAdmin(SuperAdminOnly, admin.ModelAdmin):
    list_display = ["occurred_at", "actor_name", "action", "module", "target_id", "outcome"]
    list_filter = ["action", "module", "outcome", "actor_name", "occurred_at"]
    date_hierarchy = "occurred_at"
    search_fields = ["actor_name", "=actor_id", "=target_id"]
    readonly_fields = [f.name for f in AuditEvent._meta.fields]
    actions = None

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
