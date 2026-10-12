from django import forms
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html, format_html_join

from access.models import AuditEvent, Role, WorkerProfile
from config.admin import site


def filter_context(request, name, label, options):
    plural = {
        "Status": "statuses",
        "Role": "roles",
        "Employee": "employees",
        "Module": "modules",
        "Outcome": "outcomes",
        "Action": "actions",
    }
    return {
        "name": name,
        "label": label,
        "options": options,
        "empty_label": f"All {plural.get(label, label.lower())}",
        "selected": request.GET.get(name, ""),
    }


def management_context(
    request, title, description, table_title, noun, kind, add_url=None, add_label=None
):
    # Native GET forms submit blank filters; omit those before Django validates lookups.
    params = request.GET.copy()
    for name in list(params):
        if not params[name]:
            del params[name]
    request.GET = params
    return {
        "title": title,
        "management_description": description,
        "management_table_title": table_title,
        "management_noun": noun,
        "management_kind": kind,
        "management_add_url": add_url,
        "management_add_label": add_label,
        "management_filters": [],
    }


class PermissionChoices(forms.ModelMultipleChoiceField):
    def label_from_instance(self, obj):
        return obj.name


class RoleForm(forms.ModelForm):
    permissions = PermissionChoices(
        queryset=Permission.objects.filter(content_type__app_label="catalog")
        .exclude(content_type__model__in=["productphoto", "productvariant"])
        .order_by("codename"),
        widget=forms.CheckboxSelectMultiple(attrs={"class": "permission-grid"}),
        required=False,
        help_text="Select the actions this role can perform. Changes apply on the next request.",
    )

    class Meta:
        model = Role
        fields = ["name", "permissions"]


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

    def clean(self):
        cleaned = super().clean()
        if (
            self.instance.is_superuser
            and not cleaned.get("is_active")
            and not get_user_model()
            .objects.filter(is_active=True, is_staff=True, is_superuser=True)
            .exclude(pk=self.instance.pk)
            .exists()
        ):
            raise forms.ValidationError("Keep at least one active Super Admin.")
        return cleaned


class WorkerCreationForm(WorkerFormMixin, UserCreationForm):
    role = forms.ModelChoiceField(queryset=Role.objects.all(), required=False)

    class Meta(UserCreationForm.Meta):
        model = get_user_model()
        fields = ("username", "first_name", "last_name", "email")


@admin.register(get_user_model(), site=site)
class WorkerAdmin(SuperAdminOnly, UserAdmin):
    list_per_page = 25
    list_max_show_all = 25
    change_list_template = "admin/access/management_list.html"
    change_form_template = "admin/access/management_form.html"
    form = WorkerChangeForm
    add_form = WorkerCreationForm
    list_display = ["username", "email", "role_name", "is_active"]
    list_filter = ["is_active", "is_superuser", "workerprofile__role"]
    fieldsets = [
        ("Account", {"fields": ["username", "first_name", "last_name", "email"]}),
        ("Access", {"fields": ["is_active", "role", "reset_password"]}),
    ]
    add_fieldsets = [
        ("Account", {"fields": ["username", "first_name", "last_name", "email"]}),
        (
            "Access & security",
            {
                "fields": [
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
        context = management_context(
            request,
            "Team & access",
            "Manage your team and give each person the access they need.",
            "Team members",
            "users",
            "workers",
            "admin:auth_user_add",
            "Add worker",
        )
        context["management_filters"] = [
            filter_context(
                request, "is_active__exact", "Status", [("1", "Active"), ("0", "Inactive")]
            ),
            filter_context(
                request,
                "workerprofile__role__id__exact",
                "Role",
                [(str(role.pk), role.name) for role in Role.objects.all()],
            ),
        ]
        return super().changelist_view(request, {**context, **(extra_context or {})})

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
    list_per_page = 25
    list_max_show_all = 25
    change_list_template = "admin/access/management_list.html"
    change_form_template = "admin/access/management_form.html"
    form = RoleForm
    list_display = ["name"]
    search_fields = ["name"]
    filter_horizontal = []
    fieldsets = [
        ("Role details", {"fields": ["name"]}),
        ("Module access", {"fields": ["permissions"]}),
    ]

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .annotate(worker_count=Count("workerprofile", distinct=True))
            .prefetch_related("permissions__content_type")
        )

    def changelist_view(self, request, extra_context=None):
        return super().changelist_view(
            request,
            {
                **management_context(
                    request,
                    "Roles",
                    "Give each role the right access to your store.",
                    "Access roles",
                    "roles",
                    "roles",
                    "admin:access_role_add",
                    "Add role",
                ),
                **(extra_context or {}),
            },
        )

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if db_field.name == "permissions":
            # Account/role/audit administration is never delegated.
            kwargs["queryset"] = Permission.objects.filter(
                content_type__app_label="catalog"
            ).order_by("content_type__model", "codename")
        return super().formfield_for_manytomany(db_field, request, **kwargs)


@admin.register(AuditEvent, site=site)
class AuditEventAdmin(SuperAdminOnly, admin.ModelAdmin):
    list_per_page = 100
    list_max_show_all = 100
    change_list_template = "admin/access/management_list.html"
    change_form_template = "admin/access/management_form.html"
    list_display = ["occurred_at", "actor_name", "action", "module", "target_id", "outcome"]
    list_filter = ["action", "module", "outcome", "actor_name", "occurred_at"]
    search_fields = ["actor_name", "=actor_id", "=target_id"]
    fields = [
        "occurred_at",
        "actor_detail",
        "activity_detail",
        "changes_detail",
        "outcome",
    ]
    readonly_fields = fields
    actions = None
    date_hierarchy = None

    def get_queryset(self, request):
        return (
            super().get_queryset(request).exclude(action__in=["view", "request"], outcome="success")
        )

    def get_urls(self):
        return [
            path(
                "history/<str:module>/<str:object_id>/",
                self.admin_site.admin_view(self.history_view),
                name="access_auditevent_history",
            )
        ] + super().get_urls()

    def history_view(self, request, module, object_id):
        if not self.has_view_permission(request):
            raise PermissionDenied
        events = AuditEvent.objects.filter(
            Q(module=module, target_id=object_id)
            | Q(details__subject_module=module, details__subject_id=object_id)
        ).exclude(action__in=["view", "request"], outcome="success")
        latest = events.first()
        subject_name = f"Record #{object_id}"
        subject_type = AuditEvent(module=module).target_type
        if latest:
            subject_name = (
                latest.details.get("subject_name")
                or latest.details.get("target_name")
                or subject_name
            )
            subject_type = latest.details.get("subject_type") or subject_type
        return TemplateResponse(
            request,
            "admin/access/history.html",
            {
                **self.admin_site.each_context(request),
                "title": f"History for {subject_name}",
                "subject_name": subject_name,
                "subject_type": subject_type,
                "events": events,
                "opts": self.model._meta,
            },
        )

    @admin.display(description="Performed by")
    def actor_detail(self, obj):
        return obj.actor_display

    @admin.display(description="Activity")
    def activity_detail(self, obj):
        return format_html(
            "<strong>{}</strong><br><span>{}</span>",
            obj.activity_title,
            obj.activity_summary,
        )

    @admin.display(description="What changed")
    def changes_detail(self, obj):
        if obj.action == "stock_received":
            shipment = obj.details.get("shipment_number") or "Not provided"
            return format_html(
                "<strong>Quantity added:</strong> {}<br>"
                "<strong>New quantity:</strong> {}<br>"
                "<strong>Shipment:</strong> {}",
                obj.details.get("quantity_added"),
                obj.details.get("new_quantity"),
                shipment,
            )
        if not obj.change_items:
            return "No field changes were recorded for this event."
        return format_html(
            '<div class="activity-change-list">{}</div>',
            format_html_join(
                "",
                '<div><strong>{}</strong><span class="activity-before">{}</span>'
                '<span aria-hidden="true">→</span><span class="activity-after">{}</span></div>',
                ((item["field"], item["before"], item["after"]) for item in obj.change_items),
            ),
        )

    def changelist_view(self, request, extra_context=None):
        context = management_context(
            request,
            "Activity log",
            "A clear record of who did what across your store.",
            "Store activity",
            "events",
            "activity",
        )
        visible_events = self.get_queryset(request)
        context["management_filters"] = [
            filter_context(
                request,
                "actor_name",
                "Employee",
                [
                    (name, name or "Anonymous")
                    for name in visible_events.values_list("actor_name", flat=True)
                    .distinct()
                    .order_by("actor_name")
                ],
            ),
            filter_context(
                request,
                "module",
                "Module",
                [
                    (name, AuditEvent(module=name).module_label)
                    for name in visible_events.values_list("module", flat=True)
                    .distinct()
                    .order_by("module")
                ],
            ),
            filter_context(
                request,
                "outcome",
                "Outcome",
                [("success", "Success"), ("failed", "Failed"), ("denied", "Denied")],
            ),
            filter_context(
                request,
                "action",
                "Action",
                [
                    (name, name.replace("_", " ").title())
                    for name in visible_events.values_list("action", flat=True)
                    .distinct()
                    .order_by("action")
                ],
            ),
        ]
        context["activity_dates"] = {
            "from": request.GET.get("occurred_at__date__gte", ""),
            "to": request.GET.get("occurred_at__date__lte", ""),
        }
        return super().changelist_view(request, {**context, **(extra_context or {})})

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
