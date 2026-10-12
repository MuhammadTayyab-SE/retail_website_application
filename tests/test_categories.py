from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from access.models import AuditEvent
from catalog.models import Category, Product


@override_settings(ALLOWED_HOSTS=["testserver"])
class CategoryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_superuser(
            "owner", "owner@example.invalid", "synthetic-password-832!"
        )

    def test_owner_creates_edits_orders_and_deactivates(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("admin:catalog_category_add"),
            {"name": " Fruit ", "parent": "", "position": 2, "is_active": "on", "_save": "Save"},
        )
        self.assertEqual(response.status_code, 302)
        category = Category.objects.get(name="Fruit")
        response = self.client.post(
            reverse("admin:catalog_category_change", args=[category.pk]),
            {"name": "Fresh fruit", "parent": "", "position": 0, "_save": "Save"},
        )
        self.assertEqual(response.status_code, 302)
        category.refresh_from_db()
        self.assertEqual(category.name, "Fresh fruit")
        self.assertEqual(category.position, 0)
        self.assertFalse(category.is_active)
        history_url = reverse(
            "admin:access_auditevent_history", args=["catalog.category", category.pk]
        )
        category_list = self.client.get(reverse("admin:catalog_category_changelist"))
        self.assertContains(category_list, history_url)
        history = self.client.get(history_url)
        self.assertContains(history, "Created Category")
        self.assertContains(history, "Deactivated Category")
        self.assertContains(history, "Fresh fruit")
        self.assertContains(history, "owner")
        self.assertEqual(
            AuditEvent.objects.filter(
                details__subject_module="catalog.category",
                details__subject_id=str(category.pk),
            ).count(),
            2,
        )

    def test_hierarchy_cycles_and_invalid_values_rejected(self):
        root = Category.objects.create(name="Fruit")
        child = Category.objects.create(name="Apples", parent=root)
        leaf = Category.objects.create(name="Green apples", parent=child)
        for parent in (root, child, leaf):
            root.parent = parent
            with self.subTest(parent=parent), self.assertRaises(ValidationError):
                root.save()
        for name in ("", "   ", "fruit", " FRUIT ", "a" * 101):
            with self.subTest(name=name), self.assertRaises(ValidationError):
                Category.objects.create(name=name)
        with self.assertRaises(ValidationError):
            Category.objects.create(name="Invalid order", position=-1)

    def test_database_rejects_duplicate_names(self):
        Category.objects.create(name="Fruit")
        with self.assertRaises(IntegrityError), transaction.atomic():
            Category.objects.bulk_create([Category(name=" FRUIT ")])

    def test_parent_delete_requires_confirmation_and_cascades(self):
        root = Category.objects.create(name="Fruit", is_parent_category=True)
        child = Category.objects.create(name="Apples", parent=root)
        Category.objects.create(name="Green apples", parent=child)
        survivor = Category.objects.create(name="Unrelated")
        self.client.force_login(self.owner)
        url = reverse("admin:catalog_category_delete", args=[root.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Delete parent and subcategories")
        self.assertContains(response, "Green apples")
        self.assertEqual(Category.objects.count(), 4)
        self.assertEqual(self.client.post(url, {"unconfirmed": "1"}).status_code, 400)
        self.assertEqual(Category.objects.count(), 4)
        response = self.client.post(url, {"post": "yes"})
        self.assertRedirects(response, reverse("admin:catalog_parent_categories"))
        self.assertEqual(list(Category.objects.all()), [survivor])

    def test_subcategory_delete_preserves_parent_and_siblings(self):
        root = Category.objects.create(name="Fruit", is_parent_category=True)
        child = Category.objects.create(name="Apples", parent=root)
        sibling = Category.objects.create(name="Bananas", parent=root)
        self.client.force_login(self.owner)
        url = reverse("admin:catalog_category_delete", args=[child.pk])
        self.assertEqual(self.client.get(url).status_code, 200)
        response = self.client.post(url, {"post": "yes"})
        self.assertRedirects(response, reverse("admin:catalog_category_changelist"))
        self.assertEqual(set(Category.objects.all()), {root, sibling})

    def test_category_with_products_is_deactivated_after_confirmation(self):
        root = Category.objects.create(name="Dairy", is_parent_category=True)
        child = Category.objects.create(name="Milk", parent=root)
        product = Product.objects.create(name="Fresh milk", category=child, sku="MILK-1")
        self.client.force_login(self.owner)
        url = reverse("admin:catalog_category_delete", args=[root.pk])

        response = self.client.get(url)
        self.assertContains(response, "This category contains 1 product and cannot be deleted.")
        self.assertContains(response, "You can only deactivate it.")
        self.assertContains(response, "Deactivate category")
        self.assertEqual(self.client.post(url, {"cancel": "1"}).status_code, 400)
        root.refresh_from_db()
        self.assertTrue(root.is_active)

        response = self.client.post(url, {"post": "yes"}, follow=True)
        self.assertRedirects(response, reverse("admin:catalog_parent_categories"))
        self.assertContains(response, "was deactivated", count=1)
        self.assertNotContains(response, "was deleted successfully")
        root.refresh_from_db()
        child.refresh_from_db()
        product.refresh_from_db()
        self.assertFalse(root.is_active)
        self.assertFalse(child.is_active)
        self.assertFalse(product.is_active)

    def test_delete_requires_permission_and_csrf(self):
        root = Category.objects.create(name="Fruit")
        url = reverse("admin:catalog_category_delete", args=[root.pk])
        self.assertEqual(self.client.post(url, {"post": "yes"}).status_code, 302)
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        self.assertEqual(client.post(url, {"post": "yes"}).status_code, 403)
        self.assertTrue(Category.objects.filter(pk=root.pk).exists())

    def test_cascade_photos_removed_only_after_commit(self):
        from unittest.mock import patch

        root = Category.objects.create(name="Fruit", photo="categories/root.png")
        Category.objects.create(name="Apples", parent=root, photo="categories/child.png")
        with patch.object(root.photo.storage, "delete") as remove:
            with self.captureOnCommitCallbacks(execute=True):
                root.delete()
                remove.assert_not_called()
            self.assertEqual(
                {call.args[0] for call in remove.call_args_list},
                {"categories/root.png", "categories/child.png"},
            )

    def test_public_categories_order_hierarchy_visibility_and_escaping(self):
        root = Category.objects.create(name="Fruit", position=2)
        Category.objects.create(name="Apples", parent=root)
        Category.objects.create(name="Bananas", parent=root, position=1)
        Category.objects.create(name="Vegetables", position=1)
        hidden = Category.objects.create(name="Hidden", is_active=False)
        Category.objects.create(name="Hidden child", parent=hidden)
        Category.objects.create(name="<script>alert(1)</script>", position=3)
        response = self.client.get(reverse("category-list"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [row["category"].name for row in response.context["categories"]],
            ["Vegetables", "Fruit", "Apples", "Bananas", "<script>alert(1)</script>"],
        )
        self.assertContains(response, "Fruit / Apples")
        self.assertNotContains(response, "Hidden")
        self.assertNotContains(response, "<script>")
        root.is_active = False
        root.save()
        self.assertFalse(Category.objects.get(name="Apples").is_active)
        self.assertNotContains(self.client.get(reverse("category-list")), "Apples")
        root.is_active = True
        root.save()
        self.assertNotContains(self.client.get(reverse("category-list")), "Apples")
        apples = Category.objects.get(name="Apples")
        apples.is_active = True
        apples.save()
        self.assertContains(self.client.get(reverse("category-list")), "Apples")

    def test_empty_catalog_and_read_only_public_endpoint(self):
        self.assertContains(
            self.client.get(reverse("category-list")), "No categories are available yet."
        )
        self.assertEqual(self.client.head(reverse("category-list")).content, b"")
        for method in ("post", "put", "patch", "delete"):
            self.assertEqual(
                getattr(self.client, method)(reverse("category-list")).status_code, 405
            )

    def test_admin_invalid_input_and_csrf_do_not_write(self):
        self.client.force_login(self.owner)
        Category.objects.create(name="Fruit")
        response = self.client.post(
            reverse("admin:catalog_category_add"),
            {"name": "fruit", "position": 0, "is_active": "on", "_save": "Save"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "already exists")
        self.assertEqual(Category.objects.count(), 1)
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        self.assertEqual(
            client.post(
                reverse("admin:catalog_category_add"), {"name": "CSRF attempt", "position": 0}
            ).status_code,
            403,
        )
        self.assertEqual(Category.objects.count(), 1)
