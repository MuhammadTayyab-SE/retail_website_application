from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from access.models import AuditEvent
from catalog.models import Category


class Command(BaseCommand):
    help = (
        "Make an existing active user Super Admin and assign existing catalog attribution to them."
    )

    def add_arguments(self, parser):
        parser.add_argument("username")

    @transaction.atomic
    def handle(self, *args, **options):
        try:
            user = get_user_model().objects.select_for_update().get(username=options["username"])
        except get_user_model().DoesNotExist as exc:
            raise CommandError("The selected account does not exist.") from exc
        if not user.is_active:
            raise CommandError("Select an active account.")
        if not user.is_superuser or not user.is_staff:
            user.is_staff = user.is_superuser = True
            user.save(update_fields=["is_staff", "is_superuser"])
            AuditEvent.objects.create(
                actor_id=user.pk,
                actor_name=user.username,
                action="super_admin_promoted",
                module="auth.user",
                target_id=str(user.pk),
                details={"source": "operator_assignment"},
            )
        records = Category.objects.select_for_update().exclude(
            Q(created_by=user) & Q(updated_by=user)
        )
        count = 0
        for category in records:
            before = {
                "created_by_id": category.created_by_id,
                "updated_by_id": category.updated_by_id,
            }
            # Explicit administrative reassignment: keep unknown historical creation times.
            Category.objects.filter(pk=category.pk).update(
                created_by=user, updated_by=user, updated_at=timezone.now()
            )
            AuditEvent.objects.create(
                actor_id=user.pk,
                actor_name=user.username,
                action="attribution_assignment",
                module="catalog.category",
                target_id=str(category.pk),
                details={"source": "operator_assignment", "previous": before},
            )
            count += 1
        self.stdout.write(
            self.style.SUCCESS(f"Super Admin verified; assigned {count} catalog records.")
        )
