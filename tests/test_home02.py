from decimal import Decimal

from django.test import TestCase, override_settings
from django.urls import reverse

from catalog.models import Category, Product


@override_settings(ALLOWED_HOSTS=["testserver"])
class Home02DatabaseTests(TestCase):
    def setUp(self):
        self.parent = Category.objects.create(name="Live food", is_parent_category=True)
        self.category = Category.objects.create(name="Live fruit", parent=self.parent)

    def test_categories_counts_and_ancestor_visibility(self):
        product = Product.objects.create(name="Live apple", category=self.category, unit="each")
        response = self.client.get(reverse("home"))
        counts = {
            entry["category"].pk: entry["product_count"]
            for entry in response.context["homepage_categories"]
        }
        self.assertEqual(counts, {self.parent.pk: 1, self.category.pk: 1})
        self.assertEqual(response.context["featured_products"], [product])
        self.assertContains(response, f"/catalogue/?category={self.category.pk}#products")
        Category.objects.filter(pk=self.parent.pk).update(is_active=False)
        response = self.client.get(reverse("home"))
        self.assertEqual(response.context["homepage_categories"], [])
        self.assertEqual(response.context["featured_products"], [])
        self.assertNotContains(response, "Live apple")

    def test_sale_uses_existing_price_and_stock_rules(self):
        sale = Product.objects.create(
            name="Live sale apple",
            category=self.category,
            unit="each",
            price=Decimal("10.01"),
            is_on_sale=True,
            discount_percentage=50,
            quantity=0,
        )
        Product.objects.create(name="Live regular pear", category=self.category, unit="each")
        response = self.client.get(reverse("home"))
        self.assertEqual(response.context["homepage_sale_products"], [sale])
        self.assertContains(response, "PKR 5.01")
        self.assertContains(response, "PKR 10.01")
        self.assertContains(response, "50% off")
        self.assertNotContains(response, 'aria-label="Add Live sale apple to preview basket"')

    def test_trending_uses_newest_products_and_collections_are_bounded(self):
        products = [
            Product.objects.create(name=f"Live item {i:02}", category=self.category, unit="each")
            for i in range(15)
        ]
        Product.objects.filter(pk=products[0].pk).update(created_at=None)
        response = self.client.get(reverse("home"))
        self.assertEqual(len(response.context["featured_products"]), 12)
        self.assertEqual(
            [product.pk for product in response.context["trending_products"]],
            [product.pk for product in reversed(products[-6:])],
        )
        self.assertEqual(response.context["homepage_sale_products"], [])
        self.assertContains(response, "There are no active sale products.")
