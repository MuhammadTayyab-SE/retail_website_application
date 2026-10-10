from django.contrib.auth.backends import ModelBackend

from access.models import WorkerProfile


class RoleBackend(ModelBackend):
    """Resolve the current assigned role on every check; never cache session grants."""

    def get_all_permissions(self, user_obj, obj=None):
        if not user_obj.is_active or user_obj.is_anonymous or obj is not None:
            return set()
        if user_obj.is_superuser:
            return super().get_all_permissions(user_obj, obj)
        if not user_obj.is_staff:
            return set()
        from access.audit import current_request

        request = current_request.get()
        cached = getattr(request, "_role_permissions", {})
        if user_obj.pk in cached:
            return cached[user_obj.pk]
        permissions = WorkerProfile.objects.filter(user_id=user_obj.pk).values_list(
            "role__permissions__content_type__app_label", "role__permissions__codename"
        )
        granted = {f"{app}.{code}" for app, code in permissions if app and code}
        if request:
            request._role_permissions = {**cached, user_obj.pk: granted}
        return granted

    def get_user_permissions(self, user_obj, obj=None):
        if user_obj.is_superuser:
            return super().get_user_permissions(user_obj, obj)
        return self.get_all_permissions(user_obj, obj)

    def get_group_permissions(self, user_obj, obj=None):
        if user_obj.is_superuser:
            return super().get_group_permissions(user_obj, obj)
        return set()
