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
