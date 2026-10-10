import tempfile
from importlib import import_module
from io import BytesIO
from types import SimpleNamespace

from django.apps import apps
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, connection, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from access.models import AuditEvent, Role, WorkerProfile
from catalog.forms import ProductPhotoForm
from catalog.models import Category, Product, ProductPhoto, ProductVariant


def photo_file(name="photo.png", image_format="PNG"):
    stream = BytesIO()
    Image.new("RGB", (20, 20), "green").save(stream, format=image_format)
    return SimpleUploadedFile(name, stream.getvalue(), content_type="image/png")


@override_settings(ALLOWED_HOSTS=["testserver"])
class ProductTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_superuser(
            "owner", password="Synthetic-password-129!"
        )
        cls.parent = Category.objects.create(name="Parent", is_parent_category=True)
        cls.category = Category.objects.create(name="Category", parent=cls.parent)
        cls.independent = Category.objects.create(name="Independent")
        cls.product = Product.objects.create(
            name="Milk", category=cls.category, sku="MILK-1", unit="litre"
        )
        cls.variant = ProductVariant.objects.create(
            product=cls.product, sku="milk-1", attributes={"Size": "1 litre"}
        )
        cls.role = Role.objects.create(name="Product reader")
        cls.role.permissions.set(
            Permission.objects.filter(
                content_type__app_label="catalog",
                codename__in=["view_product", "view_productvariant"],
            )
        )
        cls.worker = get_user_model().objects.create_user("worker", is_staff=True)
        WorkerProfile.objects.create(user=cls.worker, role=cls.role)

    def setUp(self):
        self.media = tempfile.TemporaryDirectory()
        self.addCleanup(self.media.cleanup)
        self.settings_override = override_settings(MEDIA_ROOT=self.media.name)
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)

    def product_data(self, **kwargs):
        return {
            "name": "New product",
            "description": "Description",
            "category": self.independent.pk,
            "is_active": "on",
            "sku": " new-1 ",
            "unit": "each",
            "photos-TOTAL_FORMS": "0",
            "photos-INITIAL_FORMS": "0",
            "photos-MIN_NUM_FORMS": "0",
            "photos-MAX_NUM_FORMS": "1000",
            **kwargs,
        }

    def test_create_product_with_unit_sku_and_attribution(self):
        self.client.force_login(self.owner)
        data = self.product_data(created_by=self.worker.pk, updated_by=self.worker.pk)
        response = self.client.post(reverse("admin:catalog_product_add"), data)
        self.assertEqual(
            response.status_code, 302, response.context and response.context.get("errors")
        )
        product = Product.objects.get(name="New product")
        self.assertFalse(product.variants.exists())
        self.assertEqual(product.sku, "NEW-1")
        self.assertEqual(product.unit, "each")
        self.assertEqual(product.created_by, self.owner)
        self.assertTrue(
            AuditEvent.objects.filter(module="catalog.product", action="create").exists()
        )

    def test_sku_case_and_whitespace_are_normalized_and_unique_across_products(self):
        self.assertEqual(self.variant.sku, "MILK-1")
        other = Product.objects.create(name="Other", category=self.independent)
        with self.assertRaises(ValidationError):
            ProductVariant.objects.create(product=other, sku=" milk-1 ")
        with self.assertRaises(IntegrityError), transaction.atomic():
            ProductVariant.objects.bulk_create([ProductVariant(product=other, sku=" milk-1 ")])
        self.variant.sku = " milk-1 "
        self.variant.save()

    def test_invalid_attributes_and_empty_names_skus_fail(self):
        for attributes in [
            [],
            {"size": 1},
            {"": "large"},
            {"size": ""},
            {"Size": "1", " size ": "2"},
        ]:
            with self.assertRaises(ValidationError):
                ProductVariant.objects.create(
                    product=self.product, sku="TEST", attributes=attributes
                )
        with self.assertRaises(ValidationError):
            ProductVariant.objects.create(product=self.product, sku="  ")
        with self.assertRaises(ValidationError):
            Product.objects.create(name="   ", category=self.independent)
        with self.assertRaises(ValidationError):
            Product.objects.create(name="Wrong category", category=self.parent)

    def test_duplicate_product_sku_fails_without_partial_save(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("admin:catalog_product_add"), self.product_data(sku=" milk-1 ")
        )
        self.assertContains(response, "This SKU is already used in the store.")
        self.assertFalse(Product.objects.filter(name="New product").exists())

    def test_product_creation_requires_valid_unit_and_sku(self):
        self.client.force_login(self.owner)
        for changes in [{"unit": ""}, {"unit": "gallon"}, {"sku": "  "}]:
            with self.subTest(changes=changes):
                response = self.client.post(
                    reverse("admin:catalog_product_add"), self.product_data(**changes)
                )
                self.assertEqual(response.status_code, 200)
                self.assertFalse(Product.objects.filter(name="New product").exists())

    def test_public_visibility_for_product_variant_and_inactive_ancestors(self):
        url = reverse("product-list")
        self.assertContains(self.client.get(url), "MILK-1")
        self.parent.is_active = False
        self.parent.save()
        self.assertNotContains(self.client.get(url), "MILK-1")
        self.parent.is_active = True
        self.parent.save()
        self.variant.is_active = False
        self.variant.save()
        self.assertContains(self.client.get(url), "Milk")
        self.variant.is_active = True
        self.variant.save()
        self.product.is_active = False
        self.product.save()
        self.assertNotContains(self.client.get(url), "Milk")

    def test_product_edit_permission_and_read_only_direct_urls(self):
        self.client.force_login(self.worker)
        for url in [
            reverse("admin:catalog_product_changelist"),
            reverse("admin:catalog_product_change", args=[self.product.pk]),
        ]:
            self.assertEqual(self.client.get(url).status_code, 200)
        for url in [
            reverse("admin:catalog_product_add"),
            reverse("admin:catalog_product_change", args=[self.product.pk]),
            reverse("admin:catalog_product_delete", args=[self.product.pk]),
        ]:
            self.assertEqual(self.client.post(url, {"post": "yes"}).status_code, 403)
        self.role.permissions.add(
            Permission.objects.get(content_type__app_label="catalog", codename="change_product")
        )
        data = self.product_data(
            name="Updated milk",
            sku="EDITED",
            unit="ml",
            category=self.category.pk,
            created_by=self.worker.pk,
        )
        self.assertEqual(
            self.client.post(
                reverse("admin:catalog_product_change", args=[self.product.pk]), data
            ).status_code,
            302,
        )
        self.product.refresh_from_db()
        self.assertEqual(self.product.sku, "EDITED")
        self.assertEqual(self.product.unit, "ml")
        self.assertEqual(self.product.updated_by, self.worker)
        self.assertIsNone(self.product.created_by)
        self.assertTrue(ProductVariant.objects.filter(pk=self.variant.pk).exists())

    def test_anonymous_unrelated_and_inactive_users_cannot_manage_products(self):
        urls = [
            reverse("admin:catalog_product_changelist"),
        ]
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 302)
        self.role.permissions.clear()
        self.client.force_login(self.worker)
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 403)
        self.worker.is_active = False
        self.worker.save()
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 302)

    def test_image_validation_and_path_normalization(self):
        for image_format, extension in [("PNG", "png"), ("JPEG", "jpg"), ("WEBP", "webp")]:
            form = ProductPhotoForm(
                data={"position": 0}, files={"image": photo_file("../../test.png", image_format)}
            )
            self.assertTrue(form.is_valid(), form.errors)
            photo = form.save(commit=False)
            photo.product = self.product
            photo.save()
            self.assertTrue(photo.image.name.startswith("products/"))
            self.assertTrue(photo.image.name.endswith("." + extension))
            self.assertNotIn("..", photo.image.name)
        for upload in [
            SimpleUploadedFile("bad.jpg", b"not an image", content_type="image/jpeg"),
            photo_file("bad.gif", "GIF"),
        ]:
            form = ProductPhotoForm(data={"position": 0}, files={"image": upload})
            self.assertFalse(form.is_valid())
        oversized = photo_file()
        oversized.size = 8 * 1024 * 1024 + 1
        self.assertFalse(
            ProductPhotoForm(data={"position": 0}, files={"image": oversized}).is_valid()
        )

    def test_private_and_public_photo_permissions_and_visibility(self):
        photo = ProductPhoto.objects.create(product=self.product, image=photo_file())
        private_url = reverse("product-photo", args=[photo.pk])
        public_url = reverse("public-product-photo", args=[photo.pk])
        self.assertEqual(self.client.get(private_url).status_code, 302)
        response = self.client.get(public_url)
        self.assertEqual(response.status_code, 200)
        for closer in response._resource_closers:
            closer()
        self.client.force_login(self.worker)
        response = self.client.get(private_url)
        self.assertEqual(response.status_code, 200)
        for closer in response._resource_closers:
            closer()
        self.role.permissions.clear()
        self.assertEqual(self.client.get(private_url).status_code, 403)
        self.product.is_active = False
        self.product.save()
        self.assertEqual(self.client.get(public_url).status_code, 404)

    def test_product_delete_confirmation_cascade_audit_and_photo_cleanup(self):
        photo = ProductPhoto.objects.create(product=self.product, image=photo_file())
        storage, name = photo.image.storage, photo.image.name
        self.client.force_login(self.owner)
        url = reverse("admin:catalog_product_delete", args=[self.product.pk])
        self.assertContains(self.client.get(url), 'name="post" value="yes"')
        self.assertEqual(self.client.post(url).status_code, 400)
        self.assertTrue(Product.objects.filter(pk=self.product.pk).exists())
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(url, {"post": "yes"})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(ProductVariant.objects.filter(pk=self.variant.pk).exists())
        self.assertFalse(storage.exists(name))
        self.assertTrue(
            AuditEvent.objects.filter(action="delete", module="catalog.product").exists()
        )
        self.assertTrue(
            AuditEvent.objects.filter(action="delete", module="catalog.productphoto").exists()
        )

    def test_category_deletion_is_protected_while_product_exists(self):
        with self.assertRaises(ProtectedError):
            self.parent.delete()
        self.assertTrue(Product.objects.filter(pk=self.product.pk).exists())

    def test_product_delete_uses_product_permission_without_variant_grants(self):
        self.role.permissions.add(
            Permission.objects.get(content_type__app_label="catalog", codename="delete_product")
        )
        self.client.force_login(self.worker)
        response = self.client.post(
            reverse("admin:catalog_product_delete", args=[self.product.pk]), {"post": "yes"}
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Product.objects.filter(pk=self.product.pk).exists())

    def test_inline_photo_upload_attribution_and_failed_save(self):
        self.client.force_login(self.owner)
        data = self.product_data(
            **{
                "photos-TOTAL_FORMS": "1",
                "photos-0-image": photo_file(),
                "photos-0-alt_text": "Front of package",
                "photos-0-position": "0",
            }
        )
        response = self.client.post(reverse("admin:catalog_product_add"), data)
        self.assertEqual(response.status_code, 302)
        photo = Product.objects.get(name="New product").photos.get()
        self.assertEqual(photo.created_by, self.owner)
        self.assertTrue(photo.image.storage.exists(photo.image.name))
        data = self.product_data(
            **{
                "name": "Invalid upload",
                "sku": "INVALID-UPLOAD",
                "photos-TOTAL_FORMS": "1",
                "photos-0-position": "0",
                "photos-0-image": SimpleUploadedFile("bad.png", b"invalid"),
            }
        )
        self.assertEqual(
            self.client.post(reverse("admin:catalog_product_add"), data).status_code, 200
        )
        self.assertFalse(Product.objects.filter(name="Invalid upload").exists())
        self.assertTrue(photo.image.storage.exists(photo.image.name))

    def test_product_add_permission_does_not_require_variant_grants(self):
        self.role.permissions.add(
            Permission.objects.get(content_type__app_label="catalog", codename="add_product")
        )
        self.client.force_login(self.worker)
        self.assertEqual(self.client.get(reverse("admin:catalog_product_add")).status_code, 200)

    def test_catalog_forms_use_plain_related_dropdowns(self):
        self.client.force_login(self.owner)
        for route, field in [
            ("catalog_category_add", "parent"),
            ("catalog_product_add", "category"),
        ]:
            response = self.client.get(reverse("admin:" + route))
            self.assertContains(response, f'id="id_{field}"')
            for action in ["add", "change", "delete", "view"]:
                self.assertNotContains(response, f'id="{action}_id_{field}"')
        response = self.client.get(reverse("admin:catalog_category_add") + "?kind=parent")
        self.assertNotContains(response, 'id="add_id_parent"')

    def test_catalog_list_actions_follow_current_role_permissions(self):
        for model, obj in [("product", self.product)]:
            change_url = reverse(f"admin:catalog_{model}_change", args=[obj.pk])
            delete_url = reverse(f"admin:catalog_{model}_delete", args=[obj.pk])
            for actor, change, delete in [
                (self.owner, True, True),
                (self.worker, False, False),
                (self.worker, True, False),
                (self.worker, False, True),
                (self.worker, True, True),
            ]:
                with self.subTest(model=model, actor=actor.username, change=change, delete=delete):
                    codenames = [f"view_{model}"]
                    if change:
                        codenames.append(f"change_{model}")
                    if delete:
                        codenames.append(f"delete_{model}")
                    self.role.permissions.set(
                        Permission.objects.filter(
                            content_type__app_label="catalog", codename__in=codenames
                        )
                    )
                    self.client.force_login(actor)
                    response = self.client.get(reverse(f"admin:catalog_{model}_changelist"))
                    label = "Manage" if change else "View"
                    self.assertContains(
                        response,
                        f'<a class="management-row-button" href="{change_url}">{label}</a>',
                        html=True,
                    )
                    delete_link = f'<a class="category-delete-link" href="{delete_url}">Delete</a>'
                    if delete:
                        self.assertContains(response, delete_link, html=True)
                    else:
                        self.assertNotContains(response, delete_link, html=True)

    def test_product_lists_have_live_filters_aligned_columns_and_matching_counts(self):
        self.client.force_login(self.owner)
        for model in ["product"]:
            response = self.client.get(reverse(f"admin:catalog_{model}_changelist"))
            self.assertContains(response, "data-management-filters")
            self.assertContains(response, "<colgroup>")
            self.assertContains(response, "Showing 1 of 1")
            response = self.client.get(
                reverse(f"admin:catalog_{model}_changelist"), {"is_active__exact": "0"}
            )
            self.assertEqual(response.context["cl"].result_count, 0)
            self.assertContains(response, "Showing 0 of 0")

    def test_unit_choices_and_product_sku_database_uniqueness(self):
        self.client.force_login(self.owner)
        for unit in ["kg", "litre", "ml", "each"]:
            response = self.client.post(
                reverse("admin:catalog_product_add"),
                self.product_data(name=f"Product {unit}", sku=f"UNIT-{unit}", unit=unit),
            )
            self.assertEqual(response.status_code, 302)
            self.assertContains(self.client.get(reverse("product-list")), f"UNIT-{unit.upper()}")
        with self.assertRaises(IntegrityError), transaction.atomic():
            Product.objects.bulk_create(
                [Product(name="Duplicate", category=self.category, sku=" milk-1 ", unit="ml")]
            )

    def test_dashboard_and_navigation_show_products_without_variant_pages(self):
        for user in [self.owner, self.worker]:
            self.client.force_login(user)
            response = self.client.get(reverse("admin:index"))
            self.assertContains(response, "Latest products")
            self.assertEqual(response.context["product_summary"]["total"], 1)
            self.assertNotContains(response, "/admin/catalog/productvariant/")
            self.assertEqual(self.client.get("/admin/catalog/productvariant/").status_code, 404)
        self.role.permissions.clear()
        self.assertNotContains(self.client.get(reverse("admin:index")), "Latest products")

    def test_legacy_sku_migration_preserves_all_options_and_unknown_units(self):
        multi = Product.objects.create(name="Multiple old sizes", category=self.category)
        first = ProductVariant.objects.create(product=multi, sku="OLD-A", is_active=False)
        active = ProductVariant.objects.create(product=multi, sku="OLD-B")
        single = Product.objects.create(name="Known unit", category=self.category)
        ProductVariant.objects.create(product=single, sku="KNOWN", attributes={"unit": "kg"})
        count = ProductVariant.objects.count()
        migration = import_module("catalog.migrations.0007_product_sku_product_unit_and_more")
        migration.copy_existing_skus(apps, SimpleNamespace(connection=connection))
        multi.refresh_from_db()
        single.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual(multi.sku, active.sku)
        self.assertEqual(multi.unit, "")
        self.assertEqual(single.unit, "kg")
        self.assertEqual(self.product.unit, "")
        self.assertEqual(ProductVariant.objects.count(), count)
        self.assertTrue(ProductVariant.objects.filter(pk=first.pk).exists())
