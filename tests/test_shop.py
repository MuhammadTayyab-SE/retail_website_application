from decimal import Decimal

from django.test import TestCase, override_settings
from django.urls import reverse

from catalog.models import Category, Product


@override_settings(ALLOWED_HOSTS=["testserver"])
class ShopTests(TestCase):
    def setUp(self):
        self.parent = Category.objects.create(name="Fresh", is_parent_category=True)
        self.child = Category.objects.create(name="Fruit", parent=self.parent)
        self.other = Category.objects.create(name="Pantry")
        self.sale = Product.objects.create(
            name="Sale apple",
            category=self.child,
            unit="kg",
            price="10.01",
            quantity=3,
            is_on_sale=True,
            discount_percentage=50,
        )
        self.regular = Product.objects.create(
            name="Regular pear",
            category=self.other,
            unit="each",
            price="7.00",
            quantity=0,
        )

    def test_combined_filters_use_current_discounted_price(self):
        response = self.client.get(
            reverse("shop"),
            {
                "category": self.parent.pk,
                "unit": "kg",
                "sale": "sale",
                "stock": "in",
                "min_price": "5.01",
                "max_price": "5.01",
                "q": "apple",
            },
        )
        self.assertEqual(list(response.context["page_obj"]), [self.sale])
        self.assertContains(response, "PKR 5.01")
        self.assertNotContains(response, "Regular pear")

    def test_database_price_annotation_matches_existing_business_logic(self):
        for product in Product.objects.with_selling_price():
            self.assertEqual(product.selling_price, product.sale_price)
        self.assertEqual(
            Product.objects.with_selling_price().get(pk=self.sale.pk).selling_price, Decimal("5.01")
        )
        self.sale.discount_percentage = 100
        self.sale.save()
        self.assertEqual(Product.objects.with_selling_price().get(pk=self.sale.pk).selling_price, 0)

    def test_price_sort_and_multi_category_selection(self):
        response = self.client.get(
            reverse("shop"),
            {
                "category": [self.parent.pk, self.other.pk],
                "sort": "price",
            },
        )
        self.assertEqual(list(response.context["page_obj"]), [self.sale, self.regular])
        response = self.client.get(reverse("shop"), {"sort": "price-desc"})
        self.assertEqual(list(response.context["page_obj"]), [self.regular, self.sale])

    def test_invalid_filters_fail_safely_and_hidden_products_are_excluded(self):
        for values in [
            {"category": "999999"},
            {"unit": "invalid"},
            {"min_price": "NaN"},
            {"min_price": "8", "max_price": "2"},
            {"stock": "bogus"},
            {"sort": "invalid"},
        ]:
            with self.subTest(values=values):
                response = self.client.get(reverse("shop"), values)
                self.assertTrue(response.context["filter_form"].errors)
                self.assertEqual(response.context["page_obj"].paginator.count, 0)
        Category.objects.filter(pk=self.parent.pk).update(is_active=False)
        response = self.client.get(reverse("shop"))
        self.assertEqual(list(response.context["page_obj"]), [self.regular])
        self.assertNotContains(response, "Sale apple")

    def test_pagination_preserves_filters_and_empty_results(self):
        Product.objects.bulk_create(
            [
                Product(name=f"Item {i:02}", category=self.other, unit="each", price="1.00")
                for i in range(30)
            ]
        )
        response = self.client.get(
            reverse("shop"),
            {
                "category": self.other.pk,
                "unit": "each",
                "q": "Item",
                "page": "bad",
            },
        )
        self.assertEqual(len(response.context["page_obj"]), 25)
        self.assertContains(response, f"category={self.other.pk}")
        self.assertContains(response, "page=2")
        second_page = self.client.get(
            reverse("shop"),
            {"category": self.other.pk, "unit": "each", "q": "Item", "page": "2"},
        )
        self.assertEqual(len(second_page.context["page_obj"]), 5)
        self.assertFalse(
            {product.pk for product in response.context["page_obj"]}
            & {product.pk for product in second_page.context["page_obj"]}
        )
        response = self.client.get(reverse("shop"), {"q": "missing"})
        self.assertEqual(response.context["page_obj"].paginator.count, 0)
        self.assertContains(response, "No matching products")

    def test_homepage_shop_links_and_safe_methods(self):
        response = self.client.get(reverse("home"))
        self.assertContains(response, 'href="/shop/" data-live-shop')
        self.assertEqual(self.client.post(reverse("shop")).status_code, 405)
        self.assertEqual(self.client.head(reverse("shop")).status_code, 200)
