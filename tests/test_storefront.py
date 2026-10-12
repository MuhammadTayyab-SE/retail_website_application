import tempfile
from decimal import Decimal

from django.test import TestCase, override_settings
from django.urls import reverse

from catalog.models import Category, Product, ProductPhoto, ProductVariant
from tests.test_products import photo_file


@override_settings(ALLOWED_HOSTS=["testserver"])
class StorefrontTests(TestCase):
    def setUp(self):
        self.media = tempfile.TemporaryDirectory()
        self.addCleanup(self.media.cleanup)
        settings = override_settings(MEDIA_ROOT=self.media.name)
        settings.enable()
        self.addCleanup(settings.disable)
        self.parent = Category.objects.create(name="Food", is_parent_category=True)
        self.category = Category.objects.create(name="Fruit", parent=self.parent)
        self.other = Category.objects.create(name="Pantry")

    def product(self, **kwargs):
        return Product.objects.create(
            **{"name": "Apples", "category": self.category, "unit": "kg", **kwargs}
        )

    def test_empty_home_and_safe_methods(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "The shelves are getting ready")
        self.assertNotContains(response, "Currently on sale")
        self.assertEqual(self.client.head(reverse("home")).status_code, 200)
        self.assertEqual(self.client.post(reverse("home")).status_code, 405)

    def test_price_rounding_sale_and_stock_use_existing_fields(self):
        self.product(price=Decimal("10.01"), is_on_sale=True, discount_percentage=50)
        self.product(name="Pears", price=20, quantity=4)
        response = self.client.get(reverse("home"))
        self.assertContains(response, "PKR 5.01")
        self.assertContains(response, "50% off")
        self.assertContains(response, "<del>PKR 10.01</del>", html=True)
        self.assertContains(response, "Out of stock")
        self.assertContains(response, "In stock")
        self.assertContains(response, "Currently on sale")

    def test_search_sku_and_parent_descendant_filter(self):
        apple = self.product(sku="APPLE-1")
        self.product(name="Rice", category=self.other)
        response = self.client.get(reverse("home"), {"q": " apple-1 ", "category": self.parent.pk})
        self.assertEqual(list(response.context["page_obj"]), [apple])
        self.assertEqual(response.context["query"], "apple-1")
        self.assertNotContains(response, "Currently on sale")
        self.assertEqual(
            self.client.get(reverse("home"), {"q": "missing"}).context["page_obj"].paginator.count,
            0,
        )

    def test_invalid_filters_never_expose_other_products(self):
        self.product()
        for category in ["bogus", "-1", "9" * 100, "١", "999999", "<script>"]:
            with self.subTest(category=category):
                response = self.client.get(reverse("home"), {"category": category, "page": "bad"})
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context["invalid_category"])
                self.assertEqual(response.context["page_obj"].paginator.count, 0)
        response = self.client.get(reverse("home"), {"q": "<script>alert(1)</script>"})
        self.assertNotContains(response, "<script>alert(1)</script>")
        self.assertContains(response, "&lt;script&gt;")

    def test_inactive_ancestor_hides_cards_products_and_public_photos(self):
        product = self.product()
        photo = ProductPhoto.objects.create(product=product, image=photo_file())
        self.category.photo = photo_file("category.png")
        self.category.save()
        response = self.client.get(reverse("public-category-photo", args=[self.category.pk]))
        self.assertEqual(response.status_code, 200)
        # Close only the file: response.close() emits request_finished and closes
        # the database connection inside this TestCase's transaction.
        response._resource_closers[0]()
        # Bypass save cascade to exercise read-time ancestor protection.
        Category.objects.filter(pk=self.parent.pk).update(is_active=False)
        response = self.client.get(reverse("home"))
        self.assertNotContains(response, "Apples")
        self.assertNotContains(response, ">Fruit<")
        for route, pk in [
            ("public-category-photo", self.category.pk),
            ("public-product-photo", photo.pk),
        ]:
            self.assertEqual(self.client.get(reverse(route, args=[pk])).status_code, 404)

    def test_public_category_photo_validation_missing_and_headers(self):
        url = reverse("public-category-photo", args=[self.category.pk])
        self.assertEqual(self.client.get(url).status_code, 404)
        self.category.photo = photo_file()
        self.category.save()
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "image/png")
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response["Cache-Control"], "private, no-store")
        response._resource_closers[0]()
        self.category.photo.storage.delete(self.category.photo.name)
        self.assertEqual(self.client.get(url).status_code, 404)
        Category.objects.filter(pk=self.category.pk).update(photo="categories/unsafe.svg")
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_visibility_and_photo_order(self):
        product = self.product()
        second = ProductPhoto.objects.create(product=product, image=photo_file(), position=2)
        first = ProductPhoto.objects.create(product=product, image=photo_file(), position=1)
        self.product(name="Hidden product", is_active=False)
        legacy = self.product(name="Legacy product", unit="")
        response = self.client.get(reverse("home"))
        self.assertContains(response, reverse("public-product-photo", args=[first.pk]))
        self.assertNotContains(response, reverse("public-product-photo", args=[second.pk]))
        self.assertNotContains(response, "Hidden product")
        self.assertNotContains(response, "Legacy product")
        ProductVariant.objects.create(product=legacy, sku="LEGACY-1")
        self.assertContains(self.client.get(reverse("home")), "Legacy product")

    def test_pagination_bounded_queries_and_preserved_filters(self):
        Product.objects.bulk_create(
            [
                Product(name=f"Item {number:02}", category=self.category, unit="each")
                for number in range(30)
            ]
        )
        # Category hierarchy, visibility hierarchy, page count, products, photos.
        with self.assertNumQueries(6):
            response = self.client.get(reverse("home"), {"q": "Item", "category": self.parent.pk})
        self.assertEqual(len(response.context["page_obj"]), 24)
        self.assertContains(response, "page=2")
        response = self.client.get(
            reverse("home"), {"q": "Item", "category": self.parent.pk, "page": 2}
        )
        self.assertEqual(len(response.context["page_obj"]), 6)
        self.assertEqual(response.context["page_obj"].paginator.count, 30)
        self.assertEqual(
            self.client.get(reverse("home"), {"page": "bad"}).context["page_obj"].number, 1
        )

    def test_existing_public_routes_remain_available(self):
        for route in ["health", "category-list", "product-list"]:
            self.assertEqual(self.client.get(reverse(route)).status_code, 200)
