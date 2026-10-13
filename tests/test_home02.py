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
        self.assertEqual(counts, {self.parent.pk: 1})
        self.assertEqual(
            [entry["category"].pk for entry in response.context["homepage_top_categories"]],
            [self.category.pk],
        )
        self.assertEqual(response.context["featured_products"], [product])
        self.assertContains(response, f"/?category={self.parent.pk}#rtsb-container-138192095")
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
        self.assertEqual(len(response.context["featured_products"]), 15)
        self.assertEqual(
            [product.pk for product in response.context["trending_products"]],
            [product.pk for product in reversed(products[-6:])],
        )
        self.assertEqual(response.context["homepage_sale_products"], [])
        self.assertContains(response, "There are no active sale products.")

    def test_sale_section_never_fills_empty_slots_with_regular_products(self):
        sale = Product.objects.create(
            name="Sale first", category=self.category, unit="each", is_on_sale=True
        )
        for i in range(8):
            Product.objects.create(name=f"Regular {i}", category=self.category, unit="each")
        response = self.client.get(reverse("home"))
        self.assertEqual(response.context["homepage_sale_products"], [sale])
        sale_html = response.content.decode().split('data-id="6acfb28"', 1)[1]
        sale_html = sale_html.split('data-id="4f77f4f"', 1)[1]
        for i in range(8):
            self.assertNotIn(f"Regular {i}", sale_html)

    def test_weekly_deals_use_database_discounted_prices_and_exclude_regular_products(self):
        sale = Product.objects.create(
            name="Weekly sale item",
            category=self.category,
            unit="each",
            price=Decimal("10.01"),
            is_on_sale=True,
            discount_percentage=50,
            quantity=0,
        )
        Product.objects.create(name="Weekly regular item", category=self.category, unit="each")
        response = self.client.get(reverse("home"))
        self.assertEqual(response.context["weekly_deal_products"], [sale])
        weekly_html = response.content.decode().split('data-id="e40606d"', 1)[1]
        weekly_html = weekly_html.split('data-id="6acfb28"', 1)[0]
        self.assertIn("Weekly sale item", weekly_html)
        self.assertNotIn("Weekly regular item", weekly_html)
        self.assertIn("PKR 5.01", weekly_html)
        self.assertIn("PKR 10.01", weekly_html)
        self.assertIn("50% off", weekly_html)
        self.assertIn("Out of stock", weekly_html)
        self.assertNotIn('aria-label="Add Weekly sale item to preview basket"', weekly_html)
        Category.objects.filter(pk=self.parent.pk).update(is_active=False)
        hidden = self.client.get(reverse("home"))
        self.assertEqual(hidden.context["weekly_deal_products"], [])
        self.assertContains(hidden, "There are no active weekly deals.")

    def test_category_search_and_old_bookmarks_use_current_home02(self):
        apple = Product.objects.create(
            name="Live apple", category=self.category, unit="each", sku="APPLE-1"
        )
        other = Category.objects.create(name="Other live category")
        Product.objects.create(name="Live rice", category=other, unit="each")
        response = self.client.get(reverse("home"), {"category": self.parent.pk, "q": "apple-1"})
        self.assertEqual(response.context["featured_products"], [apple])
        self.assertContains(response, "Soft <br>")
        self.assertNotContains(response, "Good things")
        self.assertNotContains(response, 'href="/catalogue/')
        self.assertNotContains(response, "Live rice")
        bookmark = self.client.get(reverse("storefront-catalogue"), {"category": self.category.pk})
        self.assertRedirects(
            bookmark,
            f"/?category={self.category.pk}#rtsb-container-138192095",
            fetch_redirect_response=False,
        )

    def test_invalid_or_hidden_category_has_empty_results(self):
        Product.objects.create(name="Live apple", category=self.category, unit="each")
        for value in ["invalid", "9" * 100, "999999"]:
            response = self.client.get(reverse("home"), {"category": value})
            self.assertTrue(response.context["invalid_category"])
            self.assertEqual(response.context["featured_products"], [])
            self.assertContains(response, "That category is unavailable.")

    def test_top_rated_uses_bounded_unique_visible_database_products(self):
        products = [
            Product.objects.create(
                name=f"Random candidate {i}", category=self.category, unit="each"
            )
            for i in range(8)
        ]
        hidden_category = Category.objects.create(name="Hidden random category", is_active=False)
        Product.objects.create(name="Hidden random product", category=hidden_category, unit="each")
        response = self.client.get(reverse("home"))
        selected = response.context["homepage_top_rated_products"]
        selected_ids = {product.pk for product in selected}
        self.assertEqual(len(selected), 5)
        self.assertEqual(len(selected_ids), 5)
        self.assertTrue(selected_ids.issubset({product.pk for product in products}))
        filtered = self.client.get(reverse("home"), {"q": "Random candidate 0"})
        self.assertEqual(filtered.context["homepage_top_rated_products"], [products[0]])

    def test_homepage_top_categories_exclude_parent_groups(self):
        product = Product.objects.create(name="Nested product", category=self.category, unit="each")
        response = self.client.get(reverse("home"))
        self.assertEqual(
            [entry["category"].pk for entry in response.context["homepage_categories"]],
            [self.parent.pk],
        )
        self.assertEqual(response.context["featured_products"], [product])
        self.assertEqual(response.context["featured_categories"][0]["category"], self.parent)
        self.assertEqual(response.context["featured_products"][0].homepage_category, self.parent)
        self.assertContains(response, "Live fruit")
        self.assertNotContains(response, ">Home 01</a>")
        self.assertNotContains(response, ">Home 02</a>")
        self.assertContains(
            response, '<a href="/" data-live-catalogue aria-current="page">Home</a>', count=3
        )
        filtered = self.client.get(reverse("home"), {"category": self.parent.pk})
        self.assertEqual(filtered.context["featured_products"], [product])
