import json
from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from checkout.models import DeliveryPolicy


class Command(BaseCommand):
    help = "Apply explicitly supplied retailer checkout rules; never seeds demo defaults."

    def add_arguments(self, parser):
        parser.add_argument("rules_file", type=Path)

    @transaction.atomic
    def handle(self, *args, **options):
        required = {
            "enabled",
            "delivery_fee",
            "free_delivery_threshold",
            "minimum_order",
            "tax_rate",
            "allowed_cities",
            "cash_on_delivery",
            "pickup_enabled",
            "pickup_fee",
            "pickup_minimum_order",
            "origin_latitude",
            "origin_longitude",
            "delivery_radius_km",
            "distance_verification",
        }
        try:
            values = json.loads(options["rules_file"].read_text(encoding="utf-8-sig"))
            if not isinstance(values, dict) or set(values) != required:
                raise CommandError("Rules must provide exactly: " + ", ".join(sorted(required)))
            if type(values["enabled"]) is not bool or type(values["cash_on_delivery"]) is not bool:
                raise CommandError("enabled and cash_on_delivery must be JSON booleans.")
            policy = DeliveryPolicy.objects.select_for_update().filter(pk=1).first()
            if policy is None:
                policy = DeliveryPolicy(pk=1)
            for name, value in values.items():
                setattr(policy, name, value)
            policy.full_clean(validate_unique=False)
            policy.save()
        except (OSError, ValueError, ValidationError) as error:
            raise CommandError(str(error)) from error
        self.stdout.write(self.style.SUCCESS("Checkout policy saved."))
