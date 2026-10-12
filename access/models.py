from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import models
from django.utils import timezone


class Role(models.Model):
    name = models.CharField(max_length=100, unique=True)
    permissions = models.ManyToManyField("auth.Permission", blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class WorkerProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    role = models.ForeignKey(Role, on_delete=models.PROTECT, null=True, blank=True)


class AttributedModel(models.Model):
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        editable=False,
        on_delete=models.PROTECT,
        related_name="%(app_label)s_%(class)s_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        editable=False,
        on_delete=models.PROTECT,
        related_name="%(app_label)s_%(class)s_updated",
    )
    created_at = models.DateTimeField(null=True, blank=True, editable=False)
    updated_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        from access.audit import current_request

        request = current_request.get()
        actor = request.user if request and request.user.is_authenticated else None
        now = timezone.now()
        if self._state.adding:
            self.created_at = now
            if request:
                self.created_by = actor
        elif actor:
            # Keep original attribution even if a caller supplies replacement values.
            original = type(self).objects.only("created_at", "created_by").get(pk=self.pk)
            self.created_at, self.created_by_id = original.created_at, original.created_by_id
        self.updated_at = now
        self.updated_by = actor
        if kwargs.get("update_fields") is not None:
            if not kwargs["update_fields"]:
                return
            kwargs["update_fields"] = set(kwargs["update_fields"]) | {"updated_at", "updated_by"}
        return super().save(*args, **kwargs)


class ImmutableLogQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise PermissionDenied("Audit history cannot be changed.")

    def delete(self):
        raise PermissionDenied("Audit history cannot be deleted.")


class AuditEvent(models.Model):
    # Snapshot identifiers deliberately survive deletion of users and business records.
    actor_id = models.PositiveBigIntegerField(null=True, blank=True, db_index=True)
    actor_name = models.CharField(max_length=150, blank=True)
    occurred_at = models.DateTimeField(auto_now_add=True, db_index=True)
    action = models.CharField(max_length=40, db_index=True)
    module = models.CharField(max_length=100, db_index=True)
    target_id = models.CharField(max_length=100, blank=True)
    outcome = models.CharField(max_length=20, default="success", db_index=True)
    details = models.JSONField(default=dict, blank=True)
    objects = ImmutableLogQuerySet.as_manager()

    class Meta:
        ordering = ["-occurred_at", "-pk"]

    def save(self, *args, **kwargs):
        if not self._state.adding or (self.pk and type(self).objects.filter(pk=self.pk).exists()):
            raise PermissionDenied("Audit history cannot be changed.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionDenied("Audit history cannot be deleted.")

    def __str__(self):
        return f"{self.actor_name or 'Anonymous'}: {self.action} ({self.outcome})"

    @property
    def action_label(self):
        return self.action.replace("_", " ").title()

    @property
    def module_label(self):
        return {
            "catalog.category": "Categories",
            "catalog.product": "Products",
            "catalog.productvariant": "Product variants",
            "catalog.productphoto": "Product photos",
            "auth.user": "Workers",
            "access.role": "Roles",
            "access.workerprofile": "Worker roles",
            "access.auditevent": "Activity log",
            "authentication": "Authentication",
            "portal": "Dashboard",
        }.get(self.module, self.module)

    @property
    def actor_display(self):
        return self.details.get("actor_display") or self.actor_name or "Anonymous user"

    @property
    def target_label(self):
        return self.details.get("target_name") or (
            f"Record #{self.target_id}" if self.target_id else ""
        )

    @property
    def target_type(self):
        return self.details.get("target_type") or {
            "catalog.category": "Category",
            "catalog.product": "Product",
            "catalog.productvariant": "Product variant",
            "catalog.productphoto": "Product photo",
            "auth.user": "Worker",
            "access.role": "Role",
            "access.workerprofile": "Worker role",
            "access.auditevent": "Activity entry",
            "portal": "Dashboard",
        }.get(self.module, self.module_label)

    @property
    def activity_title(self):
        if self.module == "authentication":
            return {
                "login": "Signed in" if self.outcome == "success" else "Sign-in failed",
                "logout": "Signed out",
            }.get(self.action, self.action_label)
        sale = self.details.get("changes", {}).get("Active On Sale", {})
        if self.module == "catalog.product" and sale.get("after") == "Yes":
            return "Started sale for Product"
        if self.module == "catalog.product" and sale.get("after") == "No":
            return "Ended sale for Product"
        active = self.details.get("changes", {}).get("Is Active", {})
        if self.action == "update" and active.get("after") == "Yes":
            return f"Activated {self.target_type}"
        if self.action == "update" and active.get("after") == "No":
            return f"Deactivated {self.target_type}"
        if self.module == "catalog.productphoto" and self.action == "create":
            return "Added Product photo"
        if self.module == "catalog.productphoto" and self.action == "delete":
            return "Removed Product photo"
        verbs = {
            "create": "Created",
            "update": "Updated",
            "delete": "Deleted",
            "view": "Viewed",
            "request": "Submitted changes to",
            "permissions_change": "Changed permissions for",
            "password_change": "Changed password for",
            "password_reset": "Reset password for",
            "stock_received": "Added stock to",
        }
        return f"{verbs.get(self.action, self.action_label)} {self.target_type}".strip()

    @property
    def activity_summary(self):
        if self.module == "authentication":
            return "Account authentication"
        if self.target_label:
            return self.target_label
        route = self.details.get("route")
        return route.replace("_", " ").title() if route else self.module_label

    @property
    def change_items(self):
        changes = self.details.get("changes", {})
        return [
            {"field": field, "before": values.get("before"), "after": values.get("after")}
            for field, values in changes.items()
        ]

    @property
    def history_module(self):
        return self.details.get("subject_module") or self.module

    @property
    def history_id(self):
        return self.details.get("subject_id") or self.target_id

    @property
    def has_record_history(self):
        return bool(self.history_id and self.history_module.startswith(("catalog.", "access.")))
