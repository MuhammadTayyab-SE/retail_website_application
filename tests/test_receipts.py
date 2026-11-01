from decimal import Decimal
from io import BytesIO
import uuid

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from pypdf import PdfReader

from catalog.models import Product
from checkout.models import OrderItem
from checkout.receipts import receipt_pdf
from checkout.services import place_order, policy_totals, priced_items, quote_snapshot
from tests.test_checkout import details, fixture


@override_settings(ALLOWED_HOSTS=["testserver"])
class ReceiptTests(TestCase):
    def setUp(self):
        self.product, self.policy = fixture()
        self.owner = uuid.uuid4()
        session = self.client.session
        session["checkout_owner"] = str(self.owner)
        session.save()
        items = [{"id": f"live-{self.product.pk}", "quantity": 2}]
        lines = priced_items(items)
        accepted = quote_snapshot(lines, policy_totals(lines, self.policy, "Lahore"))
        self.order = place_order(items, details(), AnonymousUser(), self.owner, accepted)

    def url(self):
        return reverse("checkout-receipt", args=[self.order.public_id])

    def downloaded(self):
        response = self.client.get(self.url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn("attachment", response["Content-Disposition"])
        self.assertIn(f"{self.order.number}-receipt.pdf", response["Content-Disposition"])
        self.assertIn("no-store", response["Cache-Control"])
        content = b"".join(response.streaming_content)
        self.assertTrue(content.startswith(b"%PDF-"))
        return PdfReader(BytesIO(content))

    def test_confirmation_shows_full_receipt_and_pdf_download(self):
        response = self.client.get(reverse("checkout-confirmation", args=[self.order.public_id]))
        for text in (
            "Customer details",
            "Payment details",
            "Original price",
            "Price after deal",
            "Financial breakdown",
            "Original item total",
            "Item discount",
            "Net item subtotal",
            "Download PDF",
            "Print receipt",
            "PKT",
            "307.50",
            "50.00",
        ):
            self.assertContains(response, text)
        self.assertContains(response, self.url())
        self.assertNotContains(response, "WhatsApp receipt have been sent")

    def test_download_contains_authoritative_receipt_details(self):
        reader = self.downloaded()
        text = "\n".join(page.extract_text() for page in reader.pages)
        for value in (
            self.order.number,
            "Test Customer",
            "checkout@example.test",
            "42 Test Street",
            "Checkout milk",
            "CHECKOUT-MILK",
            "100.00",
            "75.00",
            "150.00",
            "7.50",
            "307.50",
            "Unpaid",
            "PKT",
            "Page 1",
        ):
            self.assertIn(value, text)

    def test_item_columns_distinguish_original_discounted_and_line_prices(self):
        url = reverse("checkout-confirmation", args=[self.order.public_id])
        html = self.client.get(url).content.decode()
        self.assertInHTML('<td class="receipt-original-price"><del>PKR 100.00</del></td>', html)
        self.assertInHTML('<td class="receipt-discount-price">PKR 75.00</td>', html)
        self.assertInHTML("<td><strong>PKR 150.00</strong></td>", html)
        Product.objects.filter(pk=self.product.pk).update(
            is_on_sale=False, discount_percentage=None
        )
        items = [{"id": f"live-{self.product.pk}", "quantity": 2}]
        lines = priced_items(items)
        accepted = quote_snapshot(lines, policy_totals(lines, self.policy, "Lahore"))
        regular_order = place_order(items, details(), AnonymousUser(), self.owner, accepted)
        html = self.client.get(
            reverse("checkout-confirmation", args=[regular_order.public_id])
        ).content.decode()
        self.assertInHTML('<td class="receipt-original-price">PKR 100.00</td>', html)
        self.assertInHTML("<td>PKR 100.00</td>", html)
        self.assertInHTML("<td><strong>PKR 200.00</strong></td>", html)

    def test_pdf_is_private_to_guest_browser_or_account_owner(self):
        self.assertEqual(Client().get(self.url()).status_code, 404)
        owner = get_user_model().objects.create_user(username="receipt-owner")
        other = get_user_model().objects.create_user(username="receipt-other")
        self.order.user = owner
        self.order.save(update_fields=["user"])
        self.client.force_login(owner)
        self.downloaded()
        self.client.force_login(other)
        self.assertEqual(self.client.get(self.url()).status_code, 404)
        self.assertEqual(
            self.client.get(reverse("checkout-receipt", args=[uuid.uuid4()])).status_code, 404
        )

    def test_later_catalog_changes_cannot_change_receipt_prices_or_names(self):
        Product.objects.filter(pk=self.product.pk).update(
            name="Mutated product", price=Decimal("9999.00")
        )
        text = "\n".join(page.extract_text() for page in self.downloaded().pages)
        self.assertIn("Checkout milk", text)
        self.assertIn("75.00", text)
        self.assertNotIn("Mutated product", text)
        self.assertNotIn("9999.00", text)

    def test_receipt_handles_special_characters_and_long_multipage_orders(self):
        self.order.contact["first_name"] = "Zoë & <Customer>"
        self.order.address["notes"] = "Please call <before> arrival & keep the bag upright.\n" * 20
        OrderItem.objects.bulk_create(
            [
                OrderItem(
                    order=self.order,
                    name=f"Product {index:03}: " + "Long grocery product name " * 5,
                    sku=f"LONG-{index}",
                    quantity=1,
                    regular_price=100,
                    unit_price=75,
                    line_total=75,
                )
                for index in range(65)
            ]
        )
        self.order.subtotal = Decimal("5025.00")
        self.order.delivery_fee = Decimal("0.00")
        self.order.tax = Decimal("251.25")
        self.order.total = Decimal("5276.25")
        self.order.save()
        reader = PdfReader(receipt_pdf(self.order))
        self.assertGreater(len(reader.pages), 1)
        text = "\n".join(page.extract_text() for page in reader.pages)
        self.assertIn("Zoë & <Customer>", text)
        self.assertIn("Product 064", text)
        self.assertIn("5276.25", text)
        self.assertIn("Please call <before>", text)
        for page in reader.pages:
            self.assertIn(self.order.number, page.extract_text())

    def test_pdf_preserves_pickup_and_manual_review_status(self):
        self.order.delivery_method = "pickup"
        self.order.delivery_fee = Decimal("0.00")
        self.order.total = self.order.subtotal + self.order.tax
        self.order.save()
        text = "\n".join(page.extract_text() for page in self.downloaded().pages)
        self.assertIn("Store Pickup", text)
        self.assertIn("Cash on collection", text)
        self.assertIn("Free (PKR 0.00)", text)
        self.order.delivery_method = "delivery"
        self.order.status = "delivery_review"
        self.order.save()
        text = "\n".join(page.extract_text() for page in self.downloaded().pages)
        self.assertIn("Pending delivery-distance review", text)
