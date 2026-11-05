import uuid
from concurrent.futures import ThreadPoolExecutor
from importlib import import_module
from threading import Barrier, Event

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, close_old_connections, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse

from access.admin import RoleForm
from access.models import AuditEvent, Role, WorkerProfile
from catalog.models import Category, Product, ProductVariant, SkuIdentifier
from catalog.skus import assign_sku
from checkout.models import Order, OrderItem
from checkout.services import place_order, policy_totals, priced_items, quote_snapshot
from tests.catalog_fixtures import create_product
from tests.test_checkout import details, fixture


def order_line(product, variant=None):
    variant = variant or product.default_variant
    order = Order.objects.create(
        idempotency_key=uuid.uuid4(),
        browser_owner=uuid.uuid4(),
        contact={},
        address={},
        payment_method="cod",
        request_fingerprint="synthetic",
    )
    return OrderItem.objects.create(
        order=order,
        product=product,
        variant=variant,
        name=product.name,
        sku=variant.sku,
        quantity=1,
        regular_price=10,
        unit_price=10,
        line_total=10,
    )


@override_settings(ALLOWED_HOSTS=["testserver"])
class SkuTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_superuser("sku-owner")
        self.category = Category.objects.create(name="SKU category")
        self.product = create_product(
            name="SKU product", category=self.category, sku="LEGACY", quantity=7
        )
        self.variant = self.product.default_variant

    def worker(self, *permissions):
        role = Role.objects.create(name="SKU role")
        role.permissions.set(
            Permission.objects.filter(content_type__app_label="catalog", codename__in=permissions)
        )
        user = get_user_model().objects.create_user("sku-worker", is_staff=True)
        WorkerProfile.objects.create(user=user, role=role)
        return user, role

    def test_generated_codes_are_independent_and_skip_manual_reservations(self):
        first = assign_sku(self.variant, actor=self.owner)
        number = int(first.removeprefix("SKU-"))
        self.assertEqual(first, f"SKU-{number:06d}")
        other = create_product(name="Other", category=self.category, sku=f"SKU-{number + 1:06d}")
        third = assign_sku(other.default_variant, actor=self.owner)
        self.assertEqual(third, f"SKU-{number + 2:06d}")
        row = SkuIdentifier.objects.get(code=first.lower())
        self.assertEqual(
            (row.product_key, row.actor_id, row.source),
            (self.product.pk, self.owner.pk, "generated"),
        )
        independent = create_product(pk=90000001, name="Independent ID", category=self.category)
        self.assertNotEqual(
            assign_sku(independent.default_variant, actor=self.owner), "SKU-90000001"
        )

    def test_pre_order_correction_after_stock_retains_actor_old_new_and_history(self):
        assign_sku(self.variant, actor=self.owner, code=" corrected ")
        self.variant.refresh_from_db()
        self.assertEqual((self.variant.sku, self.product.quantity), ("CORRECTED", 7))
        assign_sku(self.variant, actor=self.owner, code="V2")
        events = AuditEvent.objects.filter(
            action="sku_corrected", module="catalog.productvariant", target_id=str(self.variant.pk)
        )
        self.assertEqual(events.count(), 2)
        self.assertTrue(
            events.filter(
                actor_id=self.owner.pk,
                details__changes__SKU__before="LEGACY",
                details__changes__SKU__after="CORRECTED",
            ).exists()
        )
        for code in ("legacy", "corrected", "v2"):
            self.assertTrue(SkuIdentifier.objects.filter(code=code, product=self.product).exists())
        with self.assertRaises(ValidationError):
            assign_sku(self.variant, actor=self.owner, code="LEGACY")

    def test_override_permission_is_explicit_and_revocation_applies_immediately(self):
        worker, role = self.worker("change_product")
        with self.assertRaises(PermissionDenied):
            assign_sku(self.variant, actor=worker, code="MANUAL")
        assign_sku(self.variant, actor=worker)
        grant = Permission.objects.get(codename="override_sku", content_type__app_label="catalog")
        self.assertIn(grant, RoleForm().fields["permissions"].queryset)
        role.permissions.add(grant)
        assign_sku(self.variant, actor=worker, code="MANUAL")
        role.permissions.remove(grant)
        with self.assertRaises(PermissionDenied):
            assign_sku(self.variant, actor=worker, code="REVOKED")
        with self.assertRaises(PermissionDenied):
            assign_sku(self.variant, actor=AnonymousUser())

    def test_existing_admin_post_cannot_bypass_override_permission(self):
        worker, role = self.worker("view_product", "change_product")
        self.client.force_login(worker)
        payload = {
            "name": self.product.name,
            "category": self.category.pk,
            "sku": "FORGED",
            "unit": "each",
            "price": 10,
            "quantity": 7,
            "photos-TOTAL_FORMS": 0,
            "photos-INITIAL_FORMS": 0,
            "photos-MIN_NUM_FORMS": 0,
            "photos-MAX_NUM_FORMS": 1000,
        }
        url = reverse("admin:catalog_product_change", args=[self.product.pk])
        self.assertContains(self.client.post(url, payload), "SKU override permission")
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.sku, "LEGACY")
        role.permissions.add(
            Permission.objects.get(codename="override_sku", content_type__app_label="catalog")
        )
        self.assertEqual(self.client.post(url, payload).status_code, 302)
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.sku, "FORGED")

    def test_ordered_codes_freeze_even_if_the_order_is_later_deleted(self):
        item = order_line(self.product)
        item.order.delete()
        for obj in (self.variant,):
            with (
                self.subTest(item=type(obj).__name__),
                self.assertRaisesMessage(ValidationError, "accepted order"),
            ):
                assign_sku(obj, actor=self.owner, code="TOO-LATE")

    def test_an_ordered_variant_does_not_freeze_an_unordered_sibling(self):
        first = ProductVariant.objects.create(product=self.product, sku="FIRST")
        second = ProductVariant.objects.create(product=self.product, sku="SECOND")
        order_line(self.product, first)
        with self.assertRaises(ValidationError):
            assign_sku(first, actor=self.owner, code="NO")
        assign_sku(second, actor=self.owner, code="ALLOWED")

    def test_deletion_retains_identifiers_and_cannot_reuse_even_for_same_product(self):
        option = ProductVariant.objects.create(product=self.product, sku="OPTION")
        option_id = option.pk
        option.delete()
        row = SkuIdentifier.objects.get(code="option")
        self.assertIsNone(row.variant_id)
        self.assertEqual(row.variant_key, option_id)
        with self.assertRaises(ValidationError):
            ProductVariant.objects.create(product=self.product, sku="OPTION")
        product_id = self.product.pk
        self.product.delete()
        row = SkuIdentifier.objects.get(code="legacy")
        self.assertIsNone(row.product_id)
        self.assertEqual(row.product_key, product_id)
        with self.assertRaises(ValidationError):
            create_product(name="Reused", category=self.category, sku="LEGACY")
        with self.assertRaises(PermissionDenied):
            row.delete()
        with self.assertRaises(PermissionDenied):
            SkuIdentifier.objects.all().delete()
        with self.assertRaises(PermissionDenied):
            SkuIdentifier.objects.filter(pk=row.pk).update(code="available")

    def test_bulk_writes_use_the_same_namespace_and_reject_unattributed_corrections(self):
        other = create_product(name="Other", category=self.category)
        with self.assertRaises(IntegrityError), transaction.atomic():
            ProductVariant.objects.bulk_create([ProductVariant(product=other, sku=" legacy ")])
        with self.assertRaises(IntegrityError), transaction.atomic():
            ProductVariant.objects.bulk_create([ProductVariant(product=other, sku="LEGACY")])
        with self.assertRaises(IntegrityError), transaction.atomic():
            ProductVariant.objects.filter(pk=self.variant.pk).update(sku="BYPASS")
        self.assertFalse(SkuIdentifier.objects.filter(code="bypass").exists())
        self.assertEqual(ProductVariant.objects.get(pk=self.variant.pk).sku, "LEGACY")
        variant = ProductVariant.objects.create(product=self.product, sku="OWNED")
        variant.product = other
        with self.assertRaisesMessage(ValidationError, "transferred"):
            variant.save()

    def test_partial_updates_ignore_an_unsaved_sku_change(self):
        self.variant.sku = "UNSAVED"
        self.variant.description = "Keep description"
        self.variant.save(update_fields=["description"])
        self.variant.refresh_from_db()
        self.assertEqual(
            (self.variant.sku, self.variant.description), ("LEGACY", "Keep description")
        )
        self.assertFalse(SkuIdentifier.objects.filter(code="unsaved").exists())

    def test_failed_allocation_rolls_back_assignment_but_does_not_reclaim_number(self):
        with self.assertRaises(RuntimeError), transaction.atomic():
            failed = assign_sku(self.variant, actor=self.owner)
            raise RuntimeError("Synthetic rollback")
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.sku, "LEGACY")
        self.assertFalse(SkuIdentifier.objects.filter(code=failed.lower()).exists())
        next_code = assign_sku(self.variant, actor=self.owner)
        self.assertGreater(int(next_code[4:]), int(failed[4:]))

    def test_sequence_exhaustion_never_wraps(self):
        with connection.cursor() as cursor:
            cursor.execute("SELECT last_value, is_called FROM catalog_sku_number")
            previous = cursor.fetchone()
            cursor.execute("SELECT setval('catalog_sku_number', 9223372036854775807, true)")
        try:
            with self.assertRaisesMessage(ValidationError, "exhausted"):
                assign_sku(self.variant, actor=self.owner)
        finally:
            # This is a disposable test database, not a recovery operation.
            with connection.cursor() as cursor:
                cursor.execute("SELECT setval('catalog_sku_number', %s, %s)", previous)

    def test_checkout_preserves_prices_stock_snapshots_and_freezes_sku(self):
        product, policy = fixture()
        items = [{"id": f"live-{product.pk}:{product.default_variant.pk}", "quantity": 2}]
        lines = priced_items(items)
        quote = quote_snapshot(lines, policy_totals(lines, policy, "Lahore"))
        order = place_order(items, details(), AnonymousUser(), uuid.uuid4(), quote)
        product.refresh_from_db()
        self.assertEqual(product.quantity, 3)
        self.assertEqual(order.items.get().sku, "CHECKOUT-MILK")
        with self.assertRaises(ValidationError):
            assign_sku(product.default_variant, actor=self.owner, code="AFTER-ORDER")


class SkuConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_superuser("sku-concurrent-owner")
        self.category = Category.objects.create(name="Concurrent category")
        self.products = [
            create_product(name=f"Product {n}", category=self.category) for n in range(2)
        ]

    def run_parallel(self, code=None):
        barrier = Barrier(2)

        def write(pk):
            close_old_connections()
            try:
                product = Product.objects.get(pk=pk)
                actor = get_user_model().objects.get(pk=self.owner.pk)
                barrier.wait(timeout=10)
                return assign_sku(product.default_variant, actor=actor, code=code)
            except ValidationError:
                return "duplicate"
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            return list(pool.map(write, [product.pk for product in self.products]))

    def test_parallel_generated_allocations_are_distinct(self):
        codes = self.run_parallel()
        self.assertEqual(len(set(codes)), 2)
        self.assertEqual(SkuIdentifier.objects.count(), 4)

    def test_parallel_manual_override_has_one_winner(self):
        codes = self.run_parallel("RACING-CODE")
        self.assertCountEqual(codes, ["RACING-CODE", "duplicate"])
        self.assertEqual(SkuIdentifier.objects.filter(code="racing-code").count(), 1)

    @override_settings(ALLOWED_HOSTS=["testserver"])
    def test_parallel_admin_posts_show_a_form_error_for_the_losing_override(self):
        from django.test import Client

        barrier = Barrier(2)

        def post(pk):
            close_old_connections()
            try:
                client = Client()
                client.force_login(get_user_model().objects.get(pk=self.owner.pk))
                barrier.wait(timeout=10)
                response = client.post(
                    reverse("admin:catalog_product_change", args=[pk]),
                    {
                        "name": f"Product {pk}",
                        "category": self.category.pk,
                        "sku": "ADMIN-RACE",
                        "unit": "each",
                        "price": 10,
                        "quantity": 7,
                        "photos-TOTAL_FORMS": 0,
                        "photos-INITIAL_FORMS": 0,
                        "photos-MIN_NUM_FORMS": 0,
                        "photos-MAX_NUM_FORMS": 1000,
                    },
                )
                if response.status_code == 200:
                    self.assertContains(response, "This SKU is already used in the store.")
                return response.status_code
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses = list(pool.map(post, [product.pk for product in self.products]))
        self.assertCountEqual(statuses, [302, 200])

    def test_accepted_order_wins_a_racing_correction(self):
        product = self.products[0]
        assign_sku(product.default_variant, actor=self.owner, code="BEFORE-ORDER")
        order_held = Event()
        correction_started = Event()

        def accept():
            close_old_connections()
            try:
                with transaction.atomic():
                    locked = Product.objects.select_for_update().get(pk=product.pk)
                    order_line(locked)
                    order_held.set()
                    self.assertTrue(correction_started.wait(timeout=10))
                return "accepted"
            finally:
                close_old_connections()

        def correct():
            close_old_connections()
            try:
                self.assertTrue(order_held.wait(timeout=10))
                actor = get_user_model().objects.get(pk=self.owner.pk)
                item = Product.objects.get(pk=product.pk)
                correction_started.set()
                assign_sku(item.default_variant, actor=actor, code="RACING-CORRECTION")
                return "changed"
            except ValidationError:
                return "locked"
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            accepted = pool.submit(accept)
            corrected = pool.submit(correct)
            self.assertEqual(accepted.result(timeout=15), "accepted")
            self.assertEqual(corrected.result(timeout=15), "locked")
        product.refresh_from_db()
        self.assertEqual(product.default_variant.sku, "BEFORE-ORDER")
        self.assertEqual(OrderItem.objects.get().sku, "BEFORE-ORDER")


class SkuMigrationTests(TransactionTestCase):
    before = [
        ("catalog", "0012_brand_management"),
        ("checkout", "0003_delivery_label_settings"),
        ("access", "0001_initial"),
    ]
    after = [("catalog", "0013_durable_sku_registry")]

    def setUp(self):
        executor = MigrationExecutor(connection)
        executor.migrate(self.before)
        self.apps = executor.loader.project_state(self.before).apps

    def tearDown(self):
        executor = MigrationExecutor(connection)
        state = (
            executor.loader.project_state(self.after).apps
            if ("catalog", "0013_durable_sku_registry") in executor.loader.applied_migrations
            else self.apps
        )
        state.get_model("catalog", "Product").objects.all().delete()
        executor.migrate(executor.loader.graph.leaf_nodes())

    def legacy(self, code="SKU-000150"):
        category = self.apps.get_model("catalog", "Category").objects.create(name="Legacy category")
        return self.apps.get_model("catalog", "Product").objects.create(
            name="Legacy",
            category=category,
            sku=code,
            quantity=7,
            price="25.50",
            unit="each",
        )

    def test_backfill_preserves_aliases_values_images_and_reserves_deleted_audit_codes(self):
        product = self.legacy()
        option = self.apps.get_model("catalog", "ProductVariant").objects.create(
            product=product, sku=product.sku
        )
        photo = self.apps.get_model("catalog", "ProductPhoto").objects.create(
            product=product, variant=option, image="products/keep.png"
        )
        self.apps.get_model("access", "AuditEvent").objects.create(
            action="update",
            module="catalog.product",
            target_id="98765",
            details={"changes": {"Sku": {"before": "SKU-000900", "after": "DELETED-CODE"}}},
        )
        MigrationExecutor(connection).migrate(self.after)
        product_now = (
            MigrationExecutor(connection)
            .loader.project_state(self.after)
            .apps.get_model("catalog", "Product")
            .objects.get(pk=product.pk)
        )
        self.assertEqual(
            (product_now.sku, product_now.quantity, str(product_now.price)),
            (product.sku, 7, "25.50"),
        )
        self.assertEqual(product_now.photos.get(pk=photo.pk).image.name, "products/keep.png")
        row = SkuIdentifier.objects.get(code=product.sku.lower())
        self.assertEqual((row.product_id, row.variant_id), (product.pk, option.pk))
        self.assertEqual(SkuIdentifier.objects.get(code="deleted-code").product_key, 98765)
        with connection.cursor() as cursor:
            cursor.execute("SELECT catalog_next_sku()")
            self.assertEqual(cursor.fetchone()[0], "SKU-000901")
        count = SkuIdentifier.objects.count()
        MigrationExecutor(connection).migrate(self.after)
        self.assertEqual(SkuIdentifier.objects.count(), count)
        migration = import_module("catalog.migrations.0013_durable_sku_registry")
        with self.assertRaisesMessage(RuntimeError, "Cannot reverse"):
            migration.require_empty_registry(
                MigrationExecutor(connection).loader.project_state(self.after).apps,
                type("Editor", (), {"connection": connection})(),
            )

    def test_cross_product_collision_blocks_migration_without_renumbering(self):
        product = self.legacy("COLLISION")
        other = self.apps.get_model("catalog", "Product").objects.create(
            name="Other", category_id=product.category_id
        )
        variant = self.apps.get_model("catalog", "ProductVariant").objects.create(
            product=other, sku=" collision "
        )
        with self.assertRaisesMessage(RuntimeError, "ownership conflicts"):
            MigrationExecutor(connection).migrate(self.after)
        self.assertEqual(
            self.apps.get_model("catalog", "Product").objects.get(pk=product.pk).sku, "COLLISION"
        )
        variant.delete()

    def test_unknown_deleted_order_code_is_reserved_and_a_known_conflict_is_blocked(self):
        product = self.legacy("CURRENT")
        order = self.apps.get_model("checkout", "Order").objects.create(
            idempotency_key=uuid.uuid4(),
            browser_owner=uuid.uuid4(),
            contact={},
            address={},
            payment_method="cod",
        )
        item = self.apps.get_model("checkout", "OrderItem").objects.create(
            order=order,
            sku="CURRENT",
            name="Unknown old product",
            quantity=1,
            regular_price=1,
            unit_price=1,
            line_total=1,
        )
        with self.assertRaisesMessage(RuntimeError, "ambiguous deleted history"):
            import_module("catalog.migrations.0013_durable_sku_registry").collect_identifiers(
                self.apps, connection
            )
        item.sku = "UNKNOWN-DELETED"
        item.save()
        MigrationExecutor(connection).migrate(self.after)
        row = SkuIdentifier.objects.get(code="unknown-deleted")
        self.assertIsNone(row.product_key)
        self.assertIsNotNone(row.ordered_at)
        self.assertTrue(
            import_module("catalog.migrations.0013_durable_sku_registry").collect_identifiers(
                self.apps, connection
            )
        )
        self.assertEqual(
            self.apps.get_model("catalog", "Product").objects.get(pk=product.pk).sku, "CURRENT"
        )

    def test_legacy_orders_lock_the_product_alias_even_when_another_variant_was_ordered(self):
        product = self.legacy("ALIAS")
        Variant = self.apps.get_model("catalog", "ProductVariant")
        alias = Variant.objects.create(product=product, sku="ALIAS")
        ordered = Variant.objects.create(product=product, sku="ORDERED")
        order = self.apps.get_model("checkout", "Order").objects.create(
            idempotency_key=uuid.uuid4(),
            browser_owner=uuid.uuid4(),
            contact={},
            address={},
            payment_method="cod",
        )
        self.apps.get_model("checkout", "OrderItem").objects.create(
            order=order,
            product=product,
            variant=ordered,
            sku="ORDERED",
            name="Legacy",
            quantity=1,
            regular_price=1,
            unit_price=1,
            line_total=1,
        )
        MigrationExecutor(connection).migrate(self.after)
        self.assertIsNotNone(SkuIdentifier.objects.get(code="alias").ordered_at)
        Order.objects.get(pk=order.pk).delete()
        owner = get_user_model().objects.create_superuser("legacy-order-owner")
        with self.assertRaises(IntegrityError), transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('retail.sku_actor',%s,true)", [str(owner.pk)])
                cursor.execute(
                    "UPDATE catalog_productvariant SET sku='BLOCKED' WHERE id=%s", [alias.pk]
                )
