from importlib import import_module

from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.db import connection


class Command(BaseCommand):
    help = "Read-only preflight for recoverable SKU ownership; no catalog values are changed."

    def handle(self, **options):
        migration = import_module("catalog.migrations.0013_durable_sku_registry")
        try:
            rows = migration.collect_identifiers(apps, connection)
            migration.numeric_seed(rows)
        except RuntimeError as error:
            raise CommandError(str(error)) from error
        self.stdout.write(
            f"SKU preflight passed: {len(rows)} recoverable codes; "
            f"{sum(row['product_key'] is None for row in rows)} without recoverable ownership."
        )
