import tempfile
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, close_old_connections, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from PIL import Image

from access.admin import RoleForm
from access.models import AuditEvent, Role, WorkerProfile
from catalog.forms import BrandForm, ProductForm
from catalog.models import Brand, Category, Product


def logo(format="PNG"):
    output = BytesIO()
    Image.new("RGB", (4, 4), "green").save(output, format=format)
    return SimpleUploadedFile("brand.png", output.getvalue(), content_type="image/png")


@override_settings(ALLOWED_HOSTS=["testserver"])
class BrandTests(TestCase):
    def setUp(self):
        self.media = tempfile.TemporaryDirectory()
        self.addCleanup(self.media.cleanup)
        override = override_settings(MEDIA_ROOT=self.media.name)
        override.enable()
        self.addCleanup(override.disable)
        self.owner = get_user_model().objects.create_superuser("brand-owner")
        self.client.force_login(self.owner)
        self.category = Category.objects.create(name="Brand category")
        self.brand = Brand.objects.create(name="Example brand")
        self.list_url = reverse("admin:catalog_brand_changelist")
        self.add_url = reverse("admin:catalog_brand_add")
        self.change_url = reverse("admin:catalog_brand_change", args=[self.brand.pk])

    def worker(self, name, *codenames):
        role = Role.objects.create(name=name)
        role.permissions.set(
            Permission.objects.filter(content_type__app_label="catalog", codename__in=codenames)
        )
        user = get_user_model().objects.create_user(name, is_staff=True)
        WorkerProfile.objects.create(user=user, role=role)
        return user

    def product_data(self, **values):
        return {
            "name": "Branded product",
            "sku": "BRAND-1",
            "unit": "each",
            "price": "10.00",
            "quantity": "5",
            "category": str(self.category.pk),
            "is_active": "on",
            **values,
        }

    def test_name_normalization_and_database_uniqueness(self):
        brand = Brand.objects.create(name="  New brand  ")
        self.assertEqual(brand.name, "New brand")
        self.assertFalse(BrandForm({"name": " EXAMPLE BRAND "}).is_valid())
        with self.assertRaises(ValidationError):
            Brand.objects.create(name="   ")
        with self.assertRaises(IntegrityError), transaction.atomic():
            Brand.objects.bulk_create([Brand(name=" EXAMPLE BRAND ")])
        self.assertEqual(Brand.objects.count(), 2)

    def test_brand_is_optional_and_inactive_associations_stay_sellable(self):
        form = ProductForm(self.product_data())
        self.assertTrue(form.is_valid(), form.errors)
        product = form.save()
        self.assertIsNone(product.brand_id)
        product.brand = self.brand
        product.save()
        self.brand.is_active = False
        self.brand.save()
        self.assertTrue(Product.objects.visible().filter(pk=product.pk).exists())
        edit = ProductForm(self.product_data(brand=str(self.brand.pk)), instance=product)
        self.assertTrue(edit.is_valid(), edit.errors)
        edit.save()
        new = ProductForm(self.product_data(sku="NEW", brand=str(self.brand.pk)))
        self.assertFalse(new.is_valid())
        self.assertIn("brand", new.errors)
        other = Brand.objects.create(name="Other inactive", is_active=False)
        edit = ProductForm(self.product_data(brand=str(other.pk)), instance=product)
        self.assertFalse(edit.is_valid())
        with self.assertRaises(ValidationError):
            Product.objects.create(
                name="Direct invalid association",
                sku="DIRECT",
                unit="each",
                category=self.category,
                brand=self.brand,
            )

    def test_logo_types_limits_and_missing_logo(self):
        self.assertTrue(BrandForm({"name": "No logo"}).is_valid())
        for upload in (
            logo("GIF"),
            SimpleUploadedFile("bad.png", b"not an image", content_type="image/png"),
        ):
            form = BrandForm({"name": "Bad logo"}, {"logo": upload})
            self.assertFalse(form.is_valid())
            self.assertIn("logo", form.errors)
        large = logo()
        large.size = 8 * 1024 * 1024 + 1
        form = BrandForm({"name": "Large logo"}, {"logo": large})
        self.assertFalse(form.is_valid())
        self.assertIn("8 MB", str(form.errors))

    def test_logo_replacement_clear_and_rollback_preserve_old_file_until_commit(self):
        form = BrandForm(
            {"name": self.brand.name, "is_active": "on"}, {"logo": logo()}, instance=self.brand
        )
        self.assertTrue(form.is_valid(), form.errors)
        brand = form.save()
        original = Path(brand.logo.path)
        with self.assertRaises(RuntimeError):
            with transaction.atomic():
                brand.logo = logo()
                brand.save()
                raise RuntimeError("rollback")
        brand.refresh_from_db()
        self.assertEqual(Path(brand.logo.path), original)
        self.assertTrue(original.exists())
        with self.captureOnCommitCallbacks(execute=True):
            brand.logo = logo()
            brand.save()
            self.assertTrue(original.exists())
        self.assertFalse(original.exists())
        current = Path(brand.logo.path)
        with self.captureOnCommitCallbacks(execute=True):
            clear = BrandForm({"name": brand.name, "logo-clear": "on"}, instance=brand)
            self.assertTrue(clear.is_valid(), clear.errors)
            clear.save()
        self.assertFalse(current.exists())

    def test_logo_change_not_saved_does_not_delete_current_file(self):
        self.brand.logo = logo()
        self.brand.save()
        original = Path(self.brand.logo.path)
        with self.captureOnCommitCallbacks(execute=True):
            self.brand.logo = logo()
            self.brand.description = "Changed only description"
            self.brand.save(update_fields=["description"])
        self.assertTrue(original.exists())
        self.brand.refresh_from_db()
        self.assertEqual(Path(self.brand.logo.path), original)

    def test_admin_creation_attribution_audit_and_private_logo(self):
        response = self.client.post(
            self.add_url,
            {
                "name": "Created brand",
                "description": "Details",
                "is_active": "on",
                "logo": logo(),
                "_save": "Save",
            },
        )
        self.assertEqual(response.status_code, 302)
        brand = Brand.objects.get(name="Created brand")
        self.assertEqual(brand.created_by_id, self.owner.pk)
        self.assertTrue(
            AuditEvent.objects.filter(
                module="catalog.brand", action="create", target_id=str(brand.pk)
            ).exists()
        )
        url = reverse("admin:catalog_brand_logo", args=[brand.pk])
        response = self.client.get(url)
        self.assertEqual(response["Content-Type"], "image/png")
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        self.assertIn("no-store", response["Cache-Control"])
        self.assertTrue(b"".join(response.streaming_content).startswith(b"\x89PNG"))
        self.assertEqual(self.client.post(url).status_code, 405)
        self.client.logout()
        self.assertEqual(self.client.get(url).status_code, 302)

    def test_permissions_role_choices_navigation_and_asset_isolation(self):
        self.assertTrue(
            RoleForm().fields["permissions"].queryset.filter(codename="change_brand").exists()
        )
        no_access = self.worker("no-brands", "view_product")
        self.client.force_login(no_access)
        self.assertEqual(self.client.get(self.list_url).status_code, 403)
        self.assertNotContains(self.client.get(reverse("admin:index")), f'href="{self.list_url}"')
        reader = self.worker("brand-reader", "view_brand")
        self.client.force_login(reader)
        self.assertContains(self.client.get(reverse("admin:index")), f'href="{self.list_url}"')
        response = self.client.get(self.change_url)
        self.assertContains(response, "brands.css")
        self.assertNotContains(response, 'name="_save"')
        self.assertEqual(self.client.get(self.add_url).status_code, 403)
        self.assertEqual(self.client.post(self.change_url, {"name": "Tampered"}).status_code, 403)
        self.assertNotContains(self.client.get(reverse("admin:index")), "brands.css")
        self.client.force_login(self.owner)
        self.assertEqual(
            self.client.post(
                reverse("admin:catalog_brand_delete", args=[self.brand.pk]), {"post": "yes"}
            ).status_code,
            403,
        )

    def test_linked_products_filter_and_counts_and_pagination(self):
        for index in range(26):
            Brand.objects.create(name=f"Bulk {index:02d}")
        product = Product.objects.create(
            name="Linked product",
            sku="LINKED",
            unit="each",
            brand=self.brand,
            category=self.category,
        )
        Product.objects.create(
            name="Other product", sku="OTHER", unit="each", category=self.category
        )
        response = self.client.get(self.list_url)
        self.assertEqual(len(response.context["cl"].result_list), 25)
        response = self.client.get(self.list_url, {"q": self.brand.name})
        self.assertContains(response, "1 product")
        response = self.client.get(
            reverse("admin:catalog_product_changelist"), {"brand__id__exact": str(self.brand.pk)}
        )
        self.assertContains(response, product.name)
        self.assertNotContains(response, "Other product")

    def test_editor_changes_are_audited_and_posts_require_csrf(self):
        editor = self.worker("brand-editor", "view_brand", "change_brand")
        self.client.force_login(editor)
        response = self.client.post(
            self.change_url,
            {"name": self.brand.name, "description": "Updated details", "_save": "Save"},
        )
        self.assertEqual(response.status_code, 302)
        self.brand.refresh_from_db()
        self.assertFalse(self.brand.is_active)
        self.assertEqual(self.brand.updated_by_id, editor.pk)
        event = AuditEvent.objects.filter(module="catalog.brand", action="update").latest("pk")
        self.assertEqual(event.actor_id, editor.pk)
        self.assertIn("description", event.details["changed_fields"])
        client = Client(enforce_csrf_checks=True)
        client.force_login(editor)
        self.assertEqual(client.post(self.change_url, {"name": "Forged edit"}).status_code, 403)
        self.brand.refresh_from_db()
        self.assertNotEqual(self.brand.name, "Forged edit")

    def test_inactive_filter_missing_logo_and_denied_logo_access(self):
        self.brand.is_active = False
        self.brand.save()
        Brand.objects.create(name="Visible active brand")
        response = self.client.get(self.list_url, {"is_active__exact": "0"})
        self.assertContains(response, self.brand.name)
        self.assertNotContains(response, "Visible active brand")
        self.assertContains(response, '<option value="0" selected>Inactive</option>', html=True)
        self.assertNotContains(response, 'id="changelist-filter"')
        self.assertContains(response, "Clear filters")
        response = self.client.get(self.list_url, {"q": "Visible", "is_active__exact": "1"})
        self.assertContains(response, "Visible active brand")
        self.assertNotContains(response, self.brand.name)
        self.assertContains(response, 'value="Visible"')
        self.assertContains(response, '<option value="1" selected>Active</option>', html=True)
        logo_url = reverse("admin:catalog_brand_logo", args=[self.brand.pk])
        self.assertEqual(self.client.get(logo_url).status_code, 404)
        self.client.force_login(self.worker("logo-denied", "view_product"))
        self.assertEqual(self.client.get(logo_url).status_code, 403)

    def test_brand_list_links_to_separate_add_and_edit_forms(self):
        response = self.client.get(self.list_url)
        self.assertContains(response, f'href="{self.add_url}"')
        self.assertContains(response, f'href="{self.change_url}"')
        self.assertContains(response, 'class="brand-edit-link"')
        self.assertContains(response, 'class="brand-filter-bar"')
        self.assertNotContains(response, 'id="changelist-filter"')
        self.assertNotContains(response, "data-brand-editor")
        self.assertNotContains(response, "brands.js")
        response = self.client.get(self.add_url)
        self.assertContains(response, "data-brand-editor")
        self.assertContains(response, "data-brand-image")
        self.assertContains(response, "brands.js")
        self.assertContains(response, 'name="logo"')
        self.assertContains(response, 'name="_save"')
        self.assertNotContains(response, 'class="brand-table"')
        html = response.content.decode()
        self.assertLess(html.index("brand-editor-fields"), html.index("brand-logo-editor"))
        self.assertLess(html.index("brand-logo-editor"), html.index("brand-editor-description"))

    def test_edit_and_read_only_views_show_the_existing_logo(self):
        self.brand.logo = logo()
        self.brand.save()
        image_url = reverse("admin:catalog_brand_logo", args=[self.brand.pk])
        response = self.client.get(self.change_url)
        self.assertContains(response, f'src="{image_url}"')
        self.assertContains(response, "Current logo")
        self.assertContains(response, "data-brand-image-remove")
        self.assertContains(response, 'name="logo-clear"')
        self.client.force_login(self.worker("photo-reader", "view_brand"))
        response = self.client.get(self.change_url)
        self.assertContains(response, f'src="{image_url}"')
        self.assertNotContains(response, 'type="file"')
        self.assertNotContains(response, "data-brand-image-remove")
        self.assertNotContains(response, 'name="_save"')

    def test_template_form_keeps_duplicate_errors_and_submitted_values(self):
        response = self.client.post(
            self.add_url,
            {
                "name": self.brand.name,
                "description": "Keep my text",
                "is_active": "on",
                "_save": "Save",
            },
        )
        self.assertContains(response, "A brand with this name already exists.")
        self.assertContains(response, "Keep my text")
        self.assertContains(response, 'class="brand-field brand-field-error"')
        self.assertEqual(Brand.objects.count(), 1)


class BrandConcurrencyTests(TransactionTestCase):
    def test_concurrent_normalized_names_cannot_both_persist(self):
        def create(name):
            close_old_connections()
            try:
                with transaction.atomic():
                    Brand.objects.bulk_create([Brand(name=name)])
                return "created"
            except IntegrityError:
                return "duplicate"
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(create, ["Shared brand", " SHARED BRAND "]))
        self.assertCountEqual(outcomes, ["created", "duplicate"])
        self.assertEqual(Brand.objects.count(), 1)


class BrandMigrationTests(TransactionTestCase):
    def test_additive_migration_and_reverse_preserve_existing_catalog_records(self):
        before = [("catalog", "0011_productphoto_variant_productvariant_description_and_more")]
        after = [("catalog", "0012_brand_management")]
        executor = MigrationExecutor(connection)
        try:
            executor.migrate(before)
            apps = executor.loader.project_state(before).apps
            category = apps.get_model("catalog", "Category").objects.create(name="Legacy category")
            product = apps.get_model("catalog", "Product").objects.create(
                name="Legacy product",
                category=category,
                sku="KEEP-SKU",
                unit="each",
                price="25.50",
                quantity=7,
            )
            photo = apps.get_model("catalog", "ProductPhoto").objects.create(
                product=product, image="products/keep-existing.png", position=3
            )
            executor = MigrationExecutor(connection)
            executor.migrate(after)
            current = Product.objects.get(pk=product.pk)
            self.assertIsNone(current.brand_id)
            self.assertEqual(
                (current.sku, str(current.price), current.quantity), ("KEEP-SKU", "25.50", 7)
            )
            self.assertEqual(
                current.photos.get(pk=photo.pk).image.name, "products/keep-existing.png"
            )
            executor = MigrationExecutor(connection)
            executor.migrate(before)
            restored = (
                executor.loader.project_state(before)
                .apps.get_model("catalog", "Product")
                .objects.get(pk=product.pk)
            )
            self.assertEqual(
                (restored.sku, str(restored.price), restored.quantity), ("KEEP-SKU", "25.50", 7)
            )
        finally:
            MigrationExecutor(connection).migrate(after)
