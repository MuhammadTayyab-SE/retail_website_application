from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse

from catalog.models import Category, Product, ProductPhoto, ProductVariant


@override_settings(ALLOWED_HOSTS=["testserver"])
class ProductDetailTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Fruit")
        self.product = Product.objects.create(
            name="Apples",
            sku="APPLES",
            category=self.category,
            unit="kg",
            price=Decimal("100.01"),
            quantity=5,
            description="Fresh apples",
            is_on_sale=True,
            discount_percentage=50,
        )
        self.variant = ProductVariant.objects.create(
            product=self.product,
            sku="APPLE-RED",
            attributes={"colour": "Red", "size": "Large"},
            price=Decimal("150.01"),
            description="Large red apples",
        )
        self.url = reverse("product-detail", args=[self.product.pk])

    def test_selected_variant_uses_authoritative_price_description_and_photos(self):
        photo = ProductPhoto.objects.create(
            product=self.product, variant=self.variant, image="red.jpg"
        )
        response = self.client.get(self.url, {"variant": self.variant.pk})
        selected = response.context["selected_option"]
        self.assertEqual(selected["price"], "75.01")
        self.assertEqual(selected["description"], "Large red apples")
        self.assertEqual(selected["sku"], "APPLE-RED")
        self.assertEqual(
            response.context["selected_photos"][0]["src"],
            reverse("public-product-photo", args=[photo.pk]),
        )
        self.assertContains(response, 'type="checkbox"')
        self.assertContains(response, "Colour: Red / Size: Large")

    def test_inactive_variant_and_its_photos_are_not_in_payload(self):
        hidden = ProductVariant.objects.create(product=self.product, sku="HIDDEN", is_active=False)
        photo = ProductPhoto.objects.create(
            product=self.product, variant=hidden, image="hidden.jpg"
        )
        response = self.client.get(self.url, {"variant": hidden.pk})
        data = response.context["product_data"]
        self.assertEqual([option["id"] for option in data["options"]], [str(self.variant.pk)])
        self.assertNotIn(
            reverse("public-product-photo", args=[photo.pk]),
            [item["src"] for item in data["photos"]],
        )
        self.assertEqual(data["selected"], str(self.variant.pk))

    def test_variant_defaults_and_zero_price(self):
        self.variant.price = None
        self.variant.description = ""
        self.variant.save()
        response = self.client.get(self.url)
        self.assertEqual(response.context["selected_option"]["price"], "50.01")
        self.assertEqual(response.context["selected_option"]["description"], "Fresh apples")
        self.variant.price = Decimal("0")
        self.assertEqual(self.variant.sale_price, Decimal("0.00"))

    def test_simple_out_of_stock_product_and_inactive_category(self):
        self.variant.delete()
        self.product.quantity = 0
        self.product.save()
        response = self.client.get(self.url)
        self.assertFalse(response.context["has_variants"])
        self.assertEqual(response.context["selected_option"]["price"], "50.01")
        self.assertContains(response, 'id="product-add" disabled')
        self.category.is_active = False
        self.category.save()
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_photo_cannot_reference_another_products_variant(self):
        other = Product.objects.create(name="Pears", category=self.category, unit="kg")
        photo = ProductPhoto(product=other, variant=self.variant, image="invalid.jpg")
        with self.assertRaises(ValidationError):
            photo.full_clean()

    def test_card_links_open_product_page(self):
        response = self.client.get(reverse("home"))
        self.assertContains(response, f'href="{self.url}"')
        response = self.client.get(reverse("shop"))
        self.assertContains(response, f'href="{self.url}"')
