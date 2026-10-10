from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.db.models.signals import m2m_changed, post_delete, post_save, pre_save
from django.dispatch import receiver

from access.audit import current_request, record
from access.models import AttributedModel, Role


def tracked(sender):
    return sender._meta.label_lower in {
        "catalog.category",
        "auth.user",
        "access.role",
        "access.workerprofile",
    } or issubclass(sender, AttributedModel)


@receiver(pre_save)
def before_save(sender, instance, **kwargs):
    if not tracked(sender):
        return
    request = current_request.get()
    if not request:
        return
    fields = [
        f.attname
        for f in sender._meta.concrete_fields
        if f.name
        in {
            "name",
            "parent",
            "position",
            "is_active",
            "is_staff",
            "is_superuser",
            "username",
            "first_name",
            "last_name",
            "email",
            "role",
            "user",
            "photo_x",
            "photo_y",
            "photo_zoom",
            "photo",
        }
    ]
    instance._audit_before = sender.objects.filter(pk=instance.pk).values(*fields).first()
    if sender._meta.label_lower == "auth.user" and instance.pk:
        old = sender.objects.filter(pk=instance.pk).values_list("password", flat=True).first()
        instance._password_changed = old is not None and old != instance.password


@receiver(post_save)
def after_save(sender, instance, created, **kwargs):
    if not tracked(sender) or not current_request.get():
        return
    before = getattr(instance, "_audit_before", None) or {}
    changed = [name for name, value in before.items() if value != getattr(instance, name)]
    changed_values = {
        name: {"before": before[name], "after": getattr(instance, name)}
        for name in changed
        if name in {"role_id", "parent_id", "position", "is_active", "is_staff", "is_superuser"}
    }
    record(
        "create" if created else "update",
        sender._meta.label_lower,
        instance.pk,
        details={"changed_fields": changed, "changes": changed_values},
    )
    if getattr(instance, "_password_changed", False):
        request = current_request.get()
        record(
            "password_change" if request.user.pk == instance.pk else "password_reset",
            "auth.user",
            instance.pk,
        )


@receiver(post_delete)
def after_delete(sender, instance, **kwargs):
    if tracked(sender) and current_request.get():
        record("delete", sender._meta.label_lower, instance.pk)


@receiver(m2m_changed, sender=Role.permissions.through)
def role_permissions_changed(sender, instance, action, reverse, **kwargs):
    if action.startswith("post_") and current_request.get():
        record(
            "permissions_change",
            "access.role",
            instance.pk,
            details={"operation": action, "reverse": reverse},
        )


@receiver(user_logged_in)
def login_success(sender, request, user, **kwargs):
    if request:
        request._audit_login_recorded = True
    record("login", "authentication", user.pk, request=request)


@receiver(user_logged_out)
def logout(sender, request, user, **kwargs):
    record("logout", "authentication", user.pk if user else "", request=request)


@receiver(user_login_failed)
def login_failed(sender, request, **kwargs):
    # Never persist credentials, even after Django's credential scrubbing.
    if request:
        request._audit_login_recorded = True
    record("login", "authentication", outcome="failed", request=request)
