from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from catalog.models import Category


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

    def test_deletion_disabled_for_model_queryset_and_admin(self):
        root = Category.objects.create(name="Fruit")
        Category.objects.create(name="Apples", parent=root)
        with self.assertRaises(ValidationError):
            root.delete()
        with self.assertRaises(ValidationError):
            Category.objects.all().delete()
        self.client.force_login(self.owner)
        url = reverse("admin:catalog_category_delete", args=[root.pk])
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.post(url, {"post": "yes"}).status_code, 403)
        self.assertEqual(Category.objects.count(), 2)

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
        self.assertNotContains(self.client.get(reverse("category-list")), "Apples")
        root.is_active = True
        root.save()
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
