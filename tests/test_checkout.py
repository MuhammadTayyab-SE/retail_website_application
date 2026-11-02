import json
import tempfile
import uuid
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.management import CommandError, call_command
from django.db import close_old_connections, connection
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from catalog.models import Category, Product, ProductVariant
from checkout.models import DeliveryPolicy, Order, OrderItem
from checkout.services import (
    CheckoutError,
    place_order,
    policy_totals,
    priced_items,
    quote_snapshot,
)


def fixture():
    category = Category.objects.create(name="Checkout dairy")
    product = Product.objects.create(
        name="Checkout milk",
        category=category,
        sku="CHECKOUT-MILK",
        unit="each",
        price=Decimal("100.00"),
        quantity=5,
        is_on_sale=True,
        discount_percentage=25,
    )
    policy = DeliveryPolicy.objects.create(
        enabled=True,
        delivery_fee=Decimal("150.00"),
        free_delivery_threshold=Decimal("1000"),
        minimum_order=0,
        tax_rate=Decimal("5"),
        allowed_cities=["Lahore"],
    )
    return product, policy


def details(key=None):
    return {
        "email": "checkout@example.test",
        "phone": "+923001234567",
        "first_name": "Test",
        "last_name": "Customer",
        "address": "42 Test Street",
        "landmark": "",
        "city": "Lahore",
        "postal_code": "",
        "notes": "",
        "payment_method": "cod",
        "delivery_method": "delivery",
        "idempotency_key": str(key or uuid.uuid4()),
    }


@override_settings(ALLOWED_HOSTS=["testserver"])
class CheckoutTests(TestCase):
    def setUp(self):
        self.product, self.policy = fixture()
        self.items = [{"id": f"live-{self.product.pk}", "quantity": 2}]

    def quote(self, items=None, client=None, method="delivery"):
        return (client or self.client).post(
            reverse("checkout-quote"),
            data=json.dumps(
                {
                    "items": self.items if items is None else items,
                    "city": "Lahore",
                    "delivery_method": method,
                }
            ),
            content_type="application/json",
        )

    def payload(self, client=None):
        client = client or self.client
        response = client.get(reverse("checkout"))
        quote = self.quote(client=client).json()
        return {
            "items": self.items,
            "details": details(response.context["form"]["idempotency_key"].value()),
            "quote_token": quote["quote_token"],
        }

    def place(self, payload, client=None):
        return (client or self.client).post(
            reverse("checkout-place"), data=json.dumps(payload), content_type="application/json"
        )

    def test_quote_reprices_cart_and_applies_current_rules(self):
        self.items[0].update(price="0.01", discount_percentage=100)
        response = self.quote()
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["subtotal"], "150.00")
        self.assertEqual(data["delivery_fee"], "150.00")
        self.assertEqual(data["tax"], "7.50")
        self.assertEqual(data["total"], "307.50")
        self.assertEqual(data["free_delivery_remaining"], "850.00")
        self.assertEqual(data["items"][0]["regular_price"], "100.00")

    def test_delivery_threshold_is_inclusive_and_dynamic(self):
        self.policy.free_delivery_threshold = Decimal("150.00")
        self.policy.save()
        self.assertEqual(self.quote().json()["delivery_fee"], "0.00")
        self.policy.free_delivery_threshold = Decimal("150.01")
        self.policy.save()
        self.assertEqual(self.quote().json()["delivery_fee"], "150.00")

    def test_minimum_city_and_disabled_policy_are_enforced(self):
        payload = self.payload()
        self.policy.minimum_order = 200
        self.policy.save()
        self.assertEqual(self.place(payload).status_code, 409)
        self.assertFalse(Order.objects.exists())
        self.policy.minimum_order = 0
        self.policy.allowed_cities = ["Karachi"]
        self.policy.save()
        self.assertEqual(self.place(payload).status_code, 409)
        self.policy.enabled = False
        self.policy.save()
        self.assertEqual(self.quote().status_code, 400)
        self.assertFalse(Order.objects.exists())

    def test_missing_policy_disables_checkout_without_seeding_defaults(self):
        DeliveryPolicy.objects.all().delete()
        response = self.client.get(reverse("checkout"))
        self.assertContains(response, "until delivery rules are configured")
        self.assertContains(response, "checkout/checkout.css")
        self.assertEqual(self.quote().status_code, 400)
        self.assertFalse(DeliveryPolicy.objects.exists())

    def test_guest_order_snapshots_prices_and_decrements_stock_once(self):
        payload = self.payload()
        first = self.place(payload)
        second = self.place(payload)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json(), second.json())
        self.assertEqual(Order.objects.count(), 1)
        order = Order.objects.get()
        self.assertEqual(order.total, Decimal("307.50"))
        self.assertEqual(order.payment_status, "unpaid")
        self.assertIsNone(order.user_id)
        self.product.refresh_from_db()
        self.assertEqual(self.product.quantity, 3)
        Product.objects.filter(pk=self.product.pk).update(name="Changed name", price=500)
        line = order.items.get()
        self.assertEqual(line.name, "Checkout milk")
        self.assertEqual(line.unit_price, Decimal("75.00"))

    def test_opening_another_checkout_tab_keeps_the_first_checkout_valid(self):
        first = self.payload()
        second = self.payload()
        self.assertNotEqual(
            first["details"]["idempotency_key"], second["details"]["idempotency_key"]
        )
        self.assertEqual(self.place(first).status_code, 200)
        self.assertEqual(self.place(first).status_code, 200)
        self.assertEqual(Order.objects.count(), 1)

    def test_guest_confirmation_is_private_and_idempotency_owner_is_checked(self):
        payload = self.payload()
        response = self.place(payload)
        url = response.json()["confirmation_url"]
        self.assertEqual(self.client.get(url).status_code, 200)
        other = Client()
        self.assertEqual(other.get(url).status_code, 404)
        other.get(reverse("checkout"))
        self.assertEqual(self.place(payload, client=other).status_code, 409)
        self.assertEqual(Order.objects.count(), 1)

    def test_account_order_is_hidden_from_other_accounts_even_in_same_browser(self):
        user = get_user_model().objects.create_user(
            username="checkout-owner", password="Test-only-password1"
        )
        other = get_user_model().objects.create_user(
            username="checkout-other", password="Test-only-password2"
        )
        self.client.force_login(user)
        response = self.place(self.payload())
        order = Order.objects.get()
        self.assertEqual(order.user_id, user.pk)
        self.client.force_login(other)
        self.assertEqual(self.client.get(response.json()["confirmation_url"]).status_code, 404)

    def test_invalid_cart_quantities_hidden_products_and_tampered_quotes_fail(self):
        for quantity in (0, -1, True, 1.5, "2", 2147483648):
            with self.subTest(quantity=quantity):
                self.assertEqual(
                    self.quote(
                        [{"id": f"live-{self.product.pk}", "quantity": quantity}]
                    ).status_code,
                    400,
                )
        self.assertEqual(self.quote([]).status_code, 400)
        self.assertEqual(self.quote([{"id": "not-a-product", "quantity": 1}]).status_code, 400)
        payload = self.payload()
        payload["quote_token"] = "tampered"
        self.assertEqual(self.place(payload).status_code, 409)
        self.product.is_active = False
        self.product.save()
        self.assertEqual(self.quote().status_code, 400)
        self.assertFalse(Order.objects.exists())

    def test_stock_or_price_changes_reject_order_and_roll_back(self):
        payload = self.payload()
        Product.objects.filter(pk=self.product.pk).update(quantity=1)
        self.assertEqual(self.place(payload).status_code, 409)
        self.assertFalse(Order.objects.exists())
        Product.objects.filter(pk=self.product.pk).update(quantity=5, price=200)
        self.assertEqual(self.place(payload).status_code, 409)
        self.assertFalse(Order.objects.exists())
        self.product.refresh_from_db()
        self.assertEqual(self.product.quantity, 5)

    def test_reused_key_with_changed_details_is_not_a_second_order(self):
        payload = self.payload()
        self.assertEqual(self.place(payload).status_code, 200)
        payload["details"]["address"] = "A different address"
        self.assertEqual(self.place(payload).status_code, 409)
        self.assertEqual(Order.objects.count(), 1)

    def test_variant_prices_and_aggregate_product_stock(self):
        variant = ProductVariant.objects.create(
            product=self.product, sku="CHECKOUT-LARGE", price=Decimal("120")
        )
        items = [{"id": f"live-{self.product.pk}:{variant.pk}", "quantity": 2}]
        quote = self.quote(items).json()
        self.assertEqual(quote["subtotal"], "180.00")
        combined = items + [{"id": f"live-{self.product.pk}", "quantity": 1}]
        shared_stock = self.quote(combined).json()["items"]
        self.assertEqual([item["stock"] for item in shared_stock], [4, 3])
        items.append({"id": f"live-{self.product.pk}", "quantity": 4})
        self.assertEqual(self.quote(items).status_code, 400)

    def test_variant_lines_share_one_stock_update_and_one_line_insert(self):
        variant = ProductVariant.objects.create(
            product=self.product, sku="CHECKOUT-LARGE", price=Decimal("120")
        )
        items = self.items + [{"id": f"live-{self.product.pk}:{variant.pk}", "quantity": 1}]
        lines = priced_items(items)
        accepted = quote_snapshot(lines, policy_totals(lines, self.policy, "Lahore"))
        with CaptureQueriesContext(connection) as queries:
            order = place_order(items, details(), AnonymousUser(), uuid.uuid4(), accepted)
        stock_updates = [q for q in queries if q["sql"].startswith('UPDATE "catalog_product"')]
        line_inserts = [
            q for q in queries if q["sql"].startswith('INSERT INTO "checkout_orderitem"')
        ]
        self.assertEqual(len(stock_updates), 1)
        self.assertEqual(len(line_inserts), 1)
        self.product.refresh_from_db()
        self.assertEqual(self.product.quantity, 2)
        self.assertEqual(order.items.count(), 2)
        self.assertEqual(order.subtotal, Decimal("240.00"))

    def test_csrf_and_contact_validation(self):
        strict = Client(enforce_csrf_checks=True)
        strict.get(reverse("checkout"))
        self.assertEqual(
            strict.post(
                reverse("checkout-quote"), data="{}", content_type="application/json"
            ).status_code,
            403,
        )
        payload = self.payload()
        payload["details"]["phone"] = "abc"
        response = self.place(payload)
        self.assertEqual(response.status_code, 400)
        self.assertIn("phone", response.json()["fields"])
        self.assertFalse(Order.objects.exists())

    def test_approved_lahore_rules_and_manual_driving_distance_review(self):
        DeliveryPolicy.objects.filter(pk=1).update(
            delivery_fee=200,
            free_delivery_threshold=5000,
            minimum_order=1500,
            tax_rate=0,
            origin_latitude=Decimal("31.51803832601811"),
            origin_longitude=Decimal("74.3561177711566"),
            delivery_radius_km=10,
            distance_verification="manual",
        )
        Product.objects.filter(pk=self.product.pk).update(
            price=1000, is_on_sale=False, discount_percentage=None, quantity=10
        )
        below = self.quote([{"id": f"live-{self.product.pk}", "quantity": 1}])
        self.assertEqual(below.status_code, 200)
        self.assertFalse(below.json()["can_place_order"])
        self.assertEqual(len(below.json()["items"]), 1)
        self.assertEqual(self.quote().json()["total"], "2200.00")
        free = self.quote([{"id": f"live-{self.product.pk}", "quantity": 5}]).json()
        self.assertEqual(free["delivery_fee"], "0.00")
        self.assertEqual(free["total"], "5000.00")
        response = self.place(self.payload())
        order = Order.objects.get()
        self.assertEqual(order.status, "delivery_review")
        self.assertEqual(order.policy_snapshot["delivery_radius_km"], "10.00")
        self.assertContains(
            self.client.get(response.json()["confirmation_url"]), "pending delivery-distance review"
        )

    def test_order_failure_rolls_back_lines_and_stock(self):
        second = Product.objects.create(
            name="Second milk", category=self.product.category, unit="each", price=10, quantity=5
        )
        items = self.items + [{"id": f"live-{second.pk}", "quantity": 1}]
        lines = priced_items(items)
        accepted = quote_snapshot(lines, policy_totals(lines, self.policy, "Lahore"))

        def fail_insert(*args, **kwargs):
            self.product.refresh_from_db()
            second.refresh_from_db()
            self.assertEqual((self.product.quantity, second.quantity), (3, 4))
            raise RuntimeError("Synthetic line-insert failure")

        with patch("checkout.services.OrderItem.objects.bulk_create", side_effect=fail_insert):
            with self.assertRaises(RuntimeError):
                place_order(items, details(), AnonymousUser(), uuid.uuid4(), accepted)
        self.assertFalse(Order.objects.exists())
        self.assertFalse(OrderItem.objects.exists())
        self.product.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual((self.product.quantity, second.quantity), (5, 5))

    def test_configuration_command_validates_rules_without_partial_updates(self):
        rules = {
            "pickup_enabled": True,
            "pickup_fee": "0.00",
            "pickup_minimum_order": "0.00",
            "enabled": True,
            "cash_on_delivery": True,
            "delivery_fee": "200.00",
            "free_delivery_threshold": "5000.00",
            "minimum_order": "1500.00",
            "tax_rate": "0.00",
            "allowed_cities": ["Lahore"],
            "delivery_radius_km": "10.00",
            "origin_latitude": "31.51803832601811",
            "origin_longitude": "74.3561177711566",
            "distance_verification": "manual",
        }
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "rules.json"
            path.write_text(json.dumps(rules))
            call_command("configure_checkout", str(path), verbosity=0)
            self.policy.refresh_from_db()
            self.assertEqual(self.policy.delivery_fee, Decimal("200.00"))
            rules["delivery_fee"] = "-1.00"
            path.write_text(json.dumps(rules))
            with self.assertRaises(CommandError):
                call_command("configure_checkout", str(path))
            self.policy.refresh_from_db()
            self.assertEqual(self.policy.delivery_fee, Decimal("200.00"))

    def test_below_minimum_still_returns_summary_and_blocks_order(self):
        self.policy.minimum_order = 1500
        self.policy.save()
        quote = self.quote()
        self.assertEqual(quote.status_code, 200)
        data = quote.json()
        self.assertEqual(data["items"][0]["name"], self.product.name)
        self.assertEqual(data["subtotal"], "150.00")
        self.assertFalse(data["can_place_order"])
        self.assertIn("minimum order", data["error"])
        self.assertEqual(self.place(self.payload()).status_code, 409)

    def test_out_of_area_quote_keeps_totals_and_blocks_order(self):
        self.policy.allowed_cities = ["Karachi"]
        self.policy.save()
        data = self.quote().json()
        self.assertEqual(data["total"], "307.50")
        self.assertEqual(len(data["items"]), 1)
        self.assertFalse(data["can_place_order"])
        self.assertEqual(data["error"], "Delivery is not available in this city.")

    def test_pickup_is_free_without_minimum_or_delivery_address(self):
        self.policy.pickup_enabled = True
        self.policy.minimum_order = 1500
        self.policy.save()
        response = self.client.get(reverse("checkout"))
        quote = self.quote(method="pickup").json()
        self.assertTrue(quote["can_place_order"])
        self.assertEqual(quote["delivery_fee"], "0.00")
        self.assertIsNone(quote["free_delivery_remaining"])
        values = details(response.context["form"]["idempotency_key"].value())
        values.update(delivery_method="pickup")
        values.pop("address")
        values.pop("city")
        response = self.place(
            {"items": self.items, "details": values, "quote_token": quote["quote_token"]}
        )
        self.assertEqual(response.status_code, 200)
        order = Order.objects.get()
        self.assertEqual(order.delivery_method, "pickup")
        self.assertEqual(order.address["address"], "")
        self.assertEqual(order.delivery_fee, Decimal("0.00"))
        self.assertEqual(order.status, "placed")
        self.assertContains(
            self.client.get(response.json()["confirmation_url"]), "Payment is due at pickup"
        )

    def test_online_methods_and_unavailable_instant_cannot_place_order(self):
        payload = self.payload()
        for name in ("card", "wallet", "jazzcash", "easypaisa"):
            payload["details"]["payment_method"] = name
            self.assertEqual(self.place(payload).status_code, 400)
        payload["details"].update(payment_method="cod", delivery_method="instant")
        self.assertEqual(self.place(payload).status_code, 400)
        self.assertFalse(Order.objects.exists())

    def test_template_shows_slots_and_noncollecting_online_payment_previews(self):
        self.policy.pickup_enabled = True
        self.policy.save()
        response = self.client.get(reverse("checkout"))
        for text in (
            "Cart Item",
            "Standard",
            "Instant",
            "Store Pickup",
            "Credit / Debit Card",
            "JazzCash / Easypaisa / Raast",
            "Card number",
            "Expiry date",
            "CVV / CVC",
            "Mobile wallet account number",
        ):
            self.assertContains(response, text)
        self.assertContains(response, '<fieldset disabled class="checkout-fields">')
        self.assertNotContains(response, 'name="card_number"')
        self.assertNotContains(response, 'name="cvv"')


class CheckoutConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.product, self.policy = fixture()
        Product.objects.filter(pk=self.product.pk).update(quantity=1)
        self.items = [{"id": f"live-{self.product.pk}", "quantity": 1}]
        lines = priced_items(self.items)
        self.accepted = quote_snapshot(lines, policy_totals(lines, self.policy, "Lahore"))

    def run_order(self, key):
        close_old_connections()
        try:
            return place_order(
                self.items, details(key), AnonymousUser(), uuid.UUID(int=1), self.accepted
            ).pk
        except CheckoutError:
            return None
        finally:
            close_old_connections()

    def test_competing_orders_cannot_oversell_last_item(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(self.run_order, [uuid.uuid4(), uuid.uuid4()]))
        self.assertEqual(sum(value is not None for value in results), 1)
        self.assertEqual(Order.objects.count(), 1)
        self.product.refresh_from_db()
        self.assertEqual(self.product.quantity, 0)

    def test_concurrent_duplicate_submit_returns_one_order(self):
        key = uuid.uuid4()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(self.run_order, [key, key]))
        self.assertIsNotNone(results[0])
        self.assertEqual(results[0], results[1])
        self.assertEqual(Order.objects.count(), 1)
        self.product.refresh_from_db()
        self.assertEqual(self.product.quantity, 0)
