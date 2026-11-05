from django.core.exceptions import FieldDoesNotExist
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

from catalog.models import Product, SkuIdentifier


class VariantMigrationTests(TransactionTestCase):
    before = [("catalog", "0013_durable_sku_registry")]
    after = [("catalog", "0014_variant_identity_and_photos")]

    def setUp(self):
        executor = MigrationExecutor(connection)
        executor.migrate(self.before)
        self.apps = executor.loader.project_state(self.before).apps

    def tearDown(self):
        executor = MigrationExecutor(connection)
        state = self.after if self.after[0] in executor.loader.applied_migrations else self.before
        executor.loader.project_state(state).apps.get_model(
            "catalog", "Product"
        ).objects.all().delete()
        MigrationExecutor(connection).migrate(self.after)

    def test_populated_catalog_is_rejected_without_deleting_or_mapping_records(self):
        category = self.apps.get_model("catalog", "Category").objects.create(name="Old catalog")
        product = self.apps.get_model("catalog", "Product").objects.create(
            name="Old product",
            category=category,
            sku="KEEP",
            unit="each",
            quantity=3,
        )
        with self.assertRaisesMessage(RuntimeError, "explicitly approved isolated target"):
            MigrationExecutor(connection).migrate(self.after)
        product.refresh_from_db()
        self.assertEqual((product.sku, product.quantity), ("KEEP", 3))
        self.assertTrue(SkuIdentifier.objects.filter(code="keep").exists())

    def test_empty_forward_schema_keeps_registry_and_counter(self):
        self.apps.get_model("catalog", "SkuIdentifier").objects.create(
            code="retired", source="legacy"
        )
        with connection.cursor() as cursor:
            cursor.execute("SELECT setval('catalog_sku_number',123,true)")
        MigrationExecutor(connection).migrate(self.after)
        self.assertTrue(SkuIdentifier.objects.filter(code="retired").exists())
        category = self.apps.get_model("catalog", "Category").objects.create(name="New catalog")
        product = Product.objects.create(name="New product", category_id=category.pk)
        self.assertEqual(product.default_variant.sku, "SKU-000124")
        for field in ("sku", "unit"):
            with self.assertRaises(FieldDoesNotExist):
                Product._meta.get_field(field)
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT tgname FROM pg_trigger "
                "WHERE tgrelid='catalog_product'::regclass AND NOT tgisinternal"
            )
            self.assertEqual([row[0] for row in cursor.fetchall()], ["catalog_product_default"])


class HistoricalCatalogMigrationTests(TransactionTestCase):
    def test_legacy_sku_migration_preserves_all_options_and_unknown_units(self):
        before = [("catalog", "0006_product_productphoto_productvariant_and_more")]
        after = [("catalog", "0007_product_sku_product_unit_and_more")]
        executor = MigrationExecutor(connection)
        executor.migrate(before)
        apps = executor.loader.project_state(before).apps
        Product = apps.get_model("catalog", "Product")
        Variant = apps.get_model("catalog", "ProductVariant")
        try:
            category = apps.get_model("catalog", "Category").objects.create(
                name="Historical category"
            )
            multi = Product.objects.create(name="Multiple old sizes", category=category)
            inactive = Variant.objects.create(product=multi, sku="OLD-A", is_active=False)
            active = Variant.objects.create(product=multi, sku="OLD-B")
            single = Product.objects.create(name="Known unit", category=category)
            Variant.objects.create(product=single, sku="KNOWN", attributes={"unit": "kg"})
            MigrationExecutor(connection).migrate(after)
            state = MigrationExecutor(connection).loader.project_state(after).apps
            Product = state.get_model("catalog", "Product")
            self.assertEqual(Product.objects.get(pk=multi.pk).sku, active.sku)
            self.assertEqual(Product.objects.get(pk=multi.pk).unit, "")
            self.assertEqual(Product.objects.get(pk=single.pk).unit, "kg")
            self.assertTrue(
                state.get_model("catalog", "ProductVariant").objects.filter(pk=inactive.pk).exists()
            )
        finally:
            Product.objects.all().delete()
            executor = MigrationExecutor(connection)
            executor.migrate(executor.loader.graph.leaf_nodes())
