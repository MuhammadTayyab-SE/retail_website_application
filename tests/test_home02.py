from decimal import Decimal

from django.core.paginator import Paginator
from django.template.loader import render_to_string
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import translation

from catalog.models import Category, Product
from tests.catalog_fixtures import create_product, new_product


class Home02QARegressionTests(SimpleTestCase):
    def test_home_shop_and_product_pages_share_one_floating_cart(self):
        context = {
            "product": {"pk": 11, "name": "Milk", "quantity": 3, "category_id": 7},
            "page_obj": Paginator([], 25).get_page(1),
            "product_data": {},
        }
        for template in (
            "catalog/home02/home.html",
            "catalog/shop/page.html",
            "catalog/product/page.html",
        ):
            with self.subTest(template=template):
                html = render_to_string(template, context)
                self.assertEqual(html.count('id="rtsb-cart-float-menu"'), 1)
                self.assertEqual(html.count('id="homepage-cart-drawer"'), 1)
                self.assertIn("snapshot.js?v=49", html)

    def test_cart_metadata_uses_existing_discount_and_unlocalized_prices(self):
        product = new_product(
            name="Milk & cream",
            description="<b>Full cream</b>",
            price=Decimal("390.00"),
            is_on_sale=True,
            discount_percentage=50,
            quantity=3,
        )
        with translation.override("de"):
            html = render_to_string(
                "catalog/home02/dynamic/card-actions.html", {"product": product}
            )
        self.assertIn('data-cart-price="390.00"', html)
        self.assertIn('data-cart-sale-price="195.00"', html)
        self.assertIn('data-cart-stock="3"', html)
        self.assertIn('data-cart-description="&lt;b&gt;Full cream&lt;/b&gt;"', html)

    def test_floating_basket_has_accessible_empty_cart_drawer(self):
        html = render_to_string("catalog/home02/snapshot/overlays.html")
        self.assertIn('aria-controls="homepage-cart-drawer"', html)
        self.assertIn('role="button" tabindex="0"', html)
        self.assertIn('<dialog id="homepage-cart-drawer"', html)
        self.assertIn('aria-label="Close basket"', html)
        self.assertIn("No products in the cart.", html)
        self.assertIn('href="/shop/"', html)
        self.assertIn("Go Shopping", html)
        self.assertIn('href="/checkout/"', html)
        self.assertIn('aria-disabled="true"', html)
        self.assertNotIn("loading-cart", html)

    def test_preview_basket_keeps_count_without_an_unsupported_total(self):
        html = render_to_string("catalog/home02/snapshot/overlays.html")
        self.assertIn('class="rtsb-cart-icon-num"', html)
        self.assertNotIn('class="rtsb-cart-icon-total"', html)
        self.assertNotIn("woocommerce-Price-amount", html)

    def test_search_anchor_contains_results_even_when_search_is_empty(self):
        for query in ("", "zzzz-no-product-qa"):
            with self.subTest(query=query):
                html = render_to_string(
                    "catalog/home02/snapshot/featured-and-sidebar.html",
                    {"query": query, "page_obj": Paginator([], 12).get_page(1)},
                )
                self.assertEqual(html.count('id="products"'), 1)
                results = html.split('id="products"', 1)[1]
                self.assertIn('id="rtsb-container-138192095"', results)
                if query:
                    self.assertIn('class="homepage-results"', results)
                    self.assertIn(
                        "No matching products. Choose another category or search.", results
                    )
                    self.assertIn("Show all products", results)


class DiscountTicketTemplateTests(SimpleTestCase):
    def test_explicit_discount_renders_without_a_product(self):
        html = render_to_string("catalog/home02/dynamic/discount-ticket.html", {"discount": 43})
        self.assertIn("-43%", html)

    def test_database_discount_renders_without_an_explicit_discount(self):
        html = render_to_string(
            "catalog/home02/dynamic/discount-ticket.html",
            {"product": {"discount_percentage": 50}},
        )
        self.assertIn("-50%", html)


@override_settings(ALLOWED_HOSTS=["testserver"])
class Home02DatabaseTests(TestCase):
    def setUp(self):
        self.parent = Category.objects.create(name="Live food", is_parent_category=True)
        self.category = Category.objects.create(name="Live fruit", parent=self.parent)

    def test_categories_counts_and_ancestor_visibility(self):
        product = create_product(name="Live apple", category=self.category, unit="each")
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
        sale = create_product(
            name="Live sale apple",
            category=self.category,
            unit="each",
            price=Decimal("10.01"),
            is_on_sale=True,
            discount_percentage=50,
            quantity=0,
        )
        create_product(name="Live regular pear", category=self.category, unit="each")
        response = self.client.get(reverse("home"))
        self.assertEqual(response.context["homepage_sale_products"], [sale])
        self.assertContains(response, "PKR 5.01")
        self.assertContains(response, "PKR 10.01")
        self.assertContains(response, "-50%")
        self.assertNotContains(response, 'aria-label="Add Live sale apple to preview basket"')

    def test_trending_uses_newest_products_and_collections_are_bounded(self):
        products = [
            create_product(name=f"Live item {i:02}", category=self.category, unit="each")
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
        sale = create_product(
            name="Sale first",
            category=self.category,
            unit="each",
            is_on_sale=True,
            discount_percentage=25,
        )
        for i in range(8):
            create_product(name=f"Regular {i}", category=self.category, unit="each")
        response = self.client.get(reverse("home"))
        self.assertEqual(response.context["homepage_sale_products"], [sale])
        sale_html = response.content.decode().split('data-id="6acfb28"', 1)[1]
        sale_html = sale_html.split('data-id="4f77f4f"', 1)[1]
        for i in range(8):
            self.assertNotIn(f"Regular {i}", sale_html)

    def test_category_search_and_old_bookmarks_use_current_home02(self):
        apple = create_product(
            name="Live apple", category=self.category, unit="each", sku="APPLE-1"
        )
        other = Category.objects.create(name="Other live category")
        create_product(name="Live rice", category=other, unit="each")
        response = self.client.get(reverse("home"), {"category": self.parent.pk, "q": "apple-1"})
        self.assertEqual(response.context["featured_products"], [apple])
        self.assertContains(response, 'id="homepage-hero-slider"')
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
        create_product(name="Live apple", category=self.category, unit="each")
        for value in ["invalid", "9" * 100, "999999"]:
            response = self.client.get(reverse("home"), {"category": value})
            self.assertTrue(response.context["invalid_category"])
            self.assertEqual(response.context["featured_products"], [])
            self.assertContains(response, "That category is unavailable.")

    def test_top_rated_uses_bounded_unique_visible_database_products(self):
        products = [
            create_product(name=f"Random candidate {i}", category=self.category, unit="each")
            for i in range(8)
        ]
        hidden_category = Category.objects.create(name="Hidden random category", is_active=False)
        create_product(name="Hidden random product", category=hidden_category, unit="each")
        response = self.client.get(reverse("home"))
        selected = response.context["homepage_top_rated_products"]
        selected_ids = {product.pk for product in selected}
        self.assertEqual(len(selected), 5)
        self.assertEqual(len(selected_ids), 5)
        self.assertTrue(selected_ids.issubset({product.pk for product in products}))
        filtered = self.client.get(reverse("home"), {"q": "Random candidate 0"})
        self.assertEqual(filtered.context["homepage_top_rated_products"], [products[0]])

    def test_homepage_top_categories_exclude_parent_groups(self):
        product = create_product(name="Nested product", category=self.category, unit="each")
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

    def test_best_selling_uses_five_visible_live_products_and_respects_search(self):
        products = [
            create_product(
                name=f"Best candidate {i}", category=self.category, unit="each", price=100 + i
            )
            for i in range(7)
        ]
        create_product(
            name="Hidden candidate", category=self.category, unit="each", is_active=False
        )
        response = self.client.get(reverse("home"))
        self.assertEqual(response.context["best_selling_products"], products[:5])
        self.assertContains(response, 'data-id="live-')
        best_selling_html = render_to_string(
            "catalog/home02/dynamic/best-selling.html",
            {"best_selling_products": response.context["best_selling_products"]},
        )
        self.assertNotIn("delicious-lays-potato-chips-classic-8-oz-bag", best_selling_html)
        self.assertEqual(best_selling_html.count('data-id="live-'), 5)
        filtered = self.client.get(reverse("home"), {"q": "Best candidate 6"})
        self.assertEqual(filtered.context["best_selling_products"], [products[6]])
        empty = self.client.get(reverse("home"), {"category": "999999"})
        self.assertEqual(empty.context["best_selling_products"], [])

    def test_top_category_cards_are_bounded_and_prioritize_populated_categories(self):
        for i in range(8):
            Category.objects.create(name=f"Empty category {i}")
        create_product(name="Visible fruit", category=self.category, unit="each")
        response = self.client.get(reverse("home"))
        cards = response.context["homepage_top_categories"]
        self.assertEqual(len(cards), 6)
        self.assertEqual(cards[0]["category"], self.category)
        self.assertEqual(cards[0]["product_count"], 1)
        self.assertNotIn(self.parent, [entry["category"] for entry in cards])
