import tempfile
from concurrent.futures import ThreadPoolExecutor
from io import StringIO
from threading import Barrier
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import FieldDoesNotExist, ValidationError
from django.core.management import CommandError, call_command
from django.db import IntegrityError, close_old_connections, transaction
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse

from access.audit import current_request
from access.models import AuditEvent, Role, WorkerProfile
from catalog.forms import ProductForm
from catalog.models import Category, Product, ProductPhoto, ProductVariant, SkuIdentifier
from catalog.skus import assign_sku
from checkout.services import CheckoutError, priced_items
from tests.test_products import photo_file


@override_settings(ALLOWED_HOSTS=["testserver"])
class VariantTests(TestCase):
    def setUp(self):
        self.media = tempfile.TemporaryDirectory()
        self.addCleanup(self.media.cleanup)
        self.override = override_settings(MEDIA_ROOT=self.media.name)
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.owner = get_user_model().objects.create_superuser("variant-owner")
        self.category = Category.objects.create(name="Variants")
        self.product = Product.objects.create(
            name="Milk", category=self.category, price="125", quantity=9
        )
        self.variant = self.product.default_variant

    def payload(self, **fields):
        return {
            "name": "Fresh product",
            "category": self.category.pk,
            "unit": "each",
            "price": "125",
            "quantity": 9,
            "is_active": "on",
            "photos-TOTAL_FORMS": 0,
            "photos-INITIAL_FORMS": 0,
            "photos-MIN_NUM_FORMS": 0,
            "photos-MAX_NUM_FORMS": 1000,
            **fields,
        }

    def test_creation_is_automatic_and_metadata_is_owned_by_default_variant(self):
        self.assertEqual(self.product.variants.count(), 1)
        self.assertTrue(self.variant.is_default)
        self.assertRegex(self.variant.sku, r"^SKU-[0-9]{6,}$")
        self.assertEqual(self.variant.inventory_unit, "each")
        self.assertTrue(SkuIdentifier.objects.filter(variant=self.variant).exists())
        for field in ("sku", "unit"):
            with self.assertRaises(FieldDoesNotExist):
                Product._meta.get_field(field)
        with self.assertRaises(FieldDoesNotExist):
            ProductPhoto._meta.get_field("product")

    def test_add_only_worker_can_create_generated_default_and_images(self):
        user = get_user_model().objects.create_user("variant-creator", is_staff=True)
        role = Role.objects.create(name="Product creator")
        role.permissions.add(
            Permission.objects.get(codename="add_product", content_type__app_label="catalog")
        )
        WorkerProfile.objects.create(user=user, role=role)
        self.client.force_login(user)
        payload = self.payload(
            barcode="0123456789",
            package_content="500 ml",
            **{
                "photos-TOTAL_FORMS": 1,
                "photos-0-image": photo_file(),
                "photos-0-position": 0,
                "photos-0-alt_text": "Front",
            },
        )
        response = self.client.post(reverse("admin:catalog_product_add"), payload)
        self.assertEqual(response.status_code, 302, getattr(response, "context_data", None))
        product = Product.objects.get(name="Fresh product")
        variant = product.default_variant
        self.assertEqual((variant.barcode, variant.package_content), ("0123456789", "500 ml"))
        self.assertEqual(variant.created_by_id, user.pk)
        self.assertEqual(variant.photos.count(), 1)
        self.assertTrue(variant.primary_photo.is_primary)
        self.assertEqual(SkuIdentifier.objects.get(variant=variant).source, "generated")
        response = self.client.post(
            reverse("admin:catalog_product_add"), self.payload(name="Manual", sku="UNAUTHORIZED")
        )
        self.assertContains(response, "SKU override permission")
        self.assertFalse(Product.objects.filter(name="Manual").exists())

    def test_form_validates_units_barcodes_and_package_text(self):
        for field, value in (
            ("unit", "ml"),
            ("barcode", "bad\nbarcode"),
            ("package_content", "bad\x00text"),
        ):
            form = ProductForm(self.payload(**{field: value}))
            self.assertFalse(form.is_valid())
            self.assertIn(field, form.errors)
        form = ProductForm(self.payload(unit="kg", package_content="Price per kg"))
        self.assertTrue(form.is_valid(), form.errors)
        product = form.save()
        self.assertEqual(product.default_variant.inventory_unit, "kg")

    def test_default_switching_and_removal(self):
        other = ProductVariant.objects.create(product=self.product, package_content="1 litre")
        with self.assertRaisesMessage(ValidationError, "another default"):
            self.variant.delete()
        other.is_default = True
        other.save()
        self.variant.refresh_from_db()
        self.assertFalse(self.variant.is_default)
        self.variant.delete()
        self.assertEqual(self.product.default_variant.pk, other.pk)
        other.is_default = False
        with self.assertRaisesMessage(ValidationError, "another default"):
            other.save()

    def test_database_rejects_two_defaults(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            ProductVariant.objects.bulk_create(
                [ProductVariant(product=self.product, is_default=True)]
            )

    def test_variant_gallery_primary_and_order_are_independent(self):
        front = ProductPhoto.objects.create(variant=self.variant, image=photo_file(), position=0)
        back = ProductPhoto.objects.create(variant=self.variant, image=photo_file(), position=1)
        back.is_primary = True
        back.save()
        front.refresh_from_db()
        self.assertFalse(front.is_primary)
        self.assertEqual(self.variant.primary_photo.pk, back.pk)
        self.assertEqual(
            list(self.variant.photos.values_list("pk", flat=True)), [front.pk, back.pk]
        )
        back.position = 5
        back.save()
        self.assertEqual(self.variant.primary_photo.pk, back.pk)
        self.assertEqual(back.position, 5)
        back.delete()
        front.refresh_from_db()
        self.assertTrue(front.is_primary)

    def test_gallery_rejects_transfer_and_retains_photos_on_rollback(self):
        front = ProductPhoto.objects.create(variant=self.variant, image=photo_file())
        other = ProductVariant.objects.create(product=self.product)
        front.variant = other
        with self.assertRaisesMessage(ValidationError, "transferred"):
            front.save()
        front.refresh_from_db()
        with self.assertRaises(RuntimeError), transaction.atomic():
            front.is_primary = False
            front.save()
            raise RuntimeError("synthetic")
        front.refresh_from_db()
        self.assertTrue(front.is_primary)

    def test_selected_variant_has_no_other_variant_image_fallback(self):
        photo = ProductPhoto.objects.create(variant=self.variant, image=photo_file())
        other = ProductVariant.objects.create(product=self.product, package_content="No image")
        response = self.client.get(
            reverse("product-detail", args=[self.product.pk]), {"variant": other.pk}
        )
        self.assertEqual(response.context["selected_photos"], [])
        lines = priced_items([{"id": f"live-{self.product.pk}:{other.pk}", "quantity": 1}])
        self.assertEqual(lines[0]["image"], "")
        self.assertEqual(lines[0]["sku"], other.sku)
        home = self.client.get(reverse("shop"))
        self.assertContains(home, reverse("public-product-photo", args=[photo.pk]))
        with self.assertRaises(CheckoutError):
            priced_items([{"id": f"live-{self.product.pk}", "quantity": 1}])

    def test_variant_editor_saves_and_scopes_photo_ids(self):
        self.client.force_login(self.owner)
        other = ProductVariant.objects.create(product=self.product)
        foreign = ProductPhoto.objects.create(variant=self.variant, image=photo_file())
        url = reverse("admin:catalog_product_variant_change", args=[self.product.pk, other.pk])
        payload = {
            "sku": other.sku,
            "inventory_unit": "each",
            "package_content": "500 ml",
            "is_active": "on",
            "attributes": "{}",
            "photos-TOTAL_FORMS": 1,
            "photos-INITIAL_FORMS": 0,
            "photos-MIN_NUM_FORMS": 0,
            "photos-MAX_NUM_FORMS": 1000,
            "photos-0-image": photo_file(),
            "photos-0-position": 0,
        }
        self.assertEqual(self.client.post(url, payload).status_code, 302)
        own = other.photos.get()
        payload.update({"photos-INITIAL_FORMS": 1, "photos-0-id": foreign.pk, "photos-0-image": ""})
        response = self.client.post(url, payload)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context_data["gallery"].formset.errors)
        own.refresh_from_db()
        self.assertEqual(own.variant_id, other.pk)
        stranger = Product.objects.create(name="Other product", category=self.category)
        self.assertEqual(
            self.client.get(
                reverse("admin:catalog_product_variant_change", args=[stranger.pk, other.pk])
            ).status_code,
            404,
        )

    def test_primary_uniqueness_is_database_enforced(self):
        ProductPhoto.objects.create(variant=self.variant, image=photo_file())
        with self.assertRaises(IntegrityError), transaction.atomic():
            ProductPhoto.objects.bulk_create(
                [ProductPhoto(variant=self.variant, image="synthetic.png", is_primary=True)]
            )

    def test_product_deletion_retains_issued_identity(self):
        key, code = self.variant.pk, self.variant.sku.lower()
        self.product.delete()
        row = SkuIdentifier.objects.get(code=code)
        self.assertEqual(row.variant_key, key)
        self.assertIsNone(row.variant_id)

    def test_variant_correction_uses_existing_audit_and_registry(self):
        old = self.variant.sku
        assign_sku(self.variant, actor=self.owner, code="CORRECTED")
        self.assertTrue(SkuIdentifier.objects.filter(code=old.lower()).exists())
        self.assertTrue(
            AuditEvent.objects.filter(
                action="sku_corrected",
                actor_id=self.owner.pk,
                details__changes__SKU__after="CORRECTED",
            ).exists()
        )

    def test_registry_command_checks_current_variant_ownership(self):
        output = StringIO()
        call_command("check_skus", stdout=output)
        self.assertIn("SKU registry check passed", output.getvalue())
        SkuIdentifier.objects.filter(variant=self.variant).update(variant=None)
        with self.assertRaises(CommandError):
            call_command("check_skus", stdout=StringIO())

    def test_partial_photo_save_cannot_restore_a_stale_primary_selection(self):
        first = ProductPhoto.objects.create(variant=self.variant, image=photo_file())
        second = ProductPhoto.objects.create(
            variant=self.variant, image=photo_file(), is_primary=True
        )
        first.alt_text = "Updated alt"
        first.save(update_fields=["alt_text"])
        first.refresh_from_db()
        self.assertFalse(first.is_primary)
        self.assertEqual(self.variant.primary_photo.pk, second.pk)

    def test_failed_generation_cannot_bypass_a_later_override_permission_check(self):
        role = Role.objects.create(name="Variant editor")
        role.permissions.add(
            Permission.objects.get(codename="change_product", content_type__app_label="catalog")
        )
        user = get_user_model().objects.create_user("variant-editor", is_staff=True)
        WorkerProfile.objects.create(user=user, role=role)
        token = current_request.set(SimpleNamespace(user=user))
        try:
            variant = ProductVariant(product=self.product, barcode="bad\nbarcode")
            with self.assertRaises(ValidationError):
                variant.save()
            variant.barcode = ""
            variant.sku = "MANUAL-WITHOUT-PERMISSION"
            with self.assertRaisesMessage(ValidationError, "SKU override permission"):
                variant.save()
        finally:
            current_request.reset(token)


class VariantTransactionTests(TransactionTestCase):
    def test_deferred_default_and_primary_constraints_reject_incomplete_writes(self):
        category = Category.objects.create(name="Deferred variants")
        product = Product.objects.create(name="Product", category=category)
        with self.assertRaises(IntegrityError), transaction.atomic():
            product.variants.update(is_default=False)
        with self.assertRaises(IntegrityError), transaction.atomic():
            ProductPhoto.objects.bulk_create(
                [ProductPhoto(variant=product.default_variant, image="missing-primary.png")]
            )
        self.assertEqual(product.variants.filter(is_default=True).count(), 1)
        self.assertFalse(product.default_variant.photos.exists())

    def test_parallel_default_changes_leave_exactly_one(self):
        category = Category.objects.create(name="Concurrent variants")
        product = Product.objects.create(name="Product", category=category)
        options = [ProductVariant.objects.create(product=product) for _ in range(2)]
        barrier = Barrier(2)

        def choose(pk):
            close_old_connections()
            try:
                option = ProductVariant.objects.get(pk=pk)
                barrier.wait(timeout=10)
                option.is_default = True
                option.save()
                return option.pk
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(choose, [option.pk for option in options]))
        self.assertEqual(product.variants.filter(is_default=True).count(), 1)
