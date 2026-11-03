import uuid
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Permission
from django.db import close_old_connections
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse

from access.admin import RoleForm
from access.models import AuditEvent, Role, WorkerProfile
from checkout.models import Order
from checkout.services import place_order, policy_totals, priced_items, quote_snapshot
from tests.test_checkout import details, fixture


def order_fixture():
    product, policy = fixture()
    items = [{"id": f"live-{product.pk}", "quantity": 2}]
    lines = priced_items(items)
    order = place_order(
        items,
        details(),
        AnonymousUser(),
        uuid.uuid4(),
        quote_snapshot(lines, policy_totals(lines, policy, "Lahore")),
    )
    return order, product


@override_settings(ALLOWED_HOSTS=["testserver"])
class AdminOrdersTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_superuser(
            "orders-owner", password="Synthetic-Orders-1!"
        )
        self.order, self.product = order_fixture()
        self.url = reverse("admin:orders")
        self.detail = reverse("admin:order-detail", args=[self.order.public_id])
        self.update = reverse("admin:order-status", args=[self.order.public_id])
        self.client.force_login(self.owner)

    def worker(self, name, permissions):
        role = Role.objects.create(name=name)
        role.permissions.set(
            Permission.objects.filter(content_type__app_label="checkout", codename__in=permissions)
        )
        user = get_user_model().objects.create_user(name, is_staff=True)
        WorkerProfile.objects.create(user=user, role=role)
        return user

    def update_status(self, status, expected=None, **extra):
        return self.client.post(
            self.update,
            {
                "status": status,
                "expected_status": expected or self.order.status,
                **extra,
            },
        )

    def test_checkout_order_appears_with_real_counts_and_saved_prices(self):
        response = self.client.get(self.url)
        self.assertContains(response, self.order.number)
        self.assertContains(response, "Test Customer")
        self.assertContains(response, "307.50")
        self.assertEqual(response.context["order_counts"]["total"], 1)
        self.assertEqual(response.context["order_counts"]["new"], 1)
        self.assertEqual(response.context["order_counts"]["paid"], 0)
        self.product.name = "Changed catalog name"
        self.product.price = 500
        self.product.save()
        detail = self.client.get(self.detail + "?panel=1")
        for text in (
            "Checkout milk",
            "Original: PKR 100.00",
            "After deal: PKR 75.00",
            "PKR 150.00",
            "checkout@example.test",
        ):
            self.assertContains(detail, text)
        self.assertNotContains(detail, "Changed catalog name")
        self.assertIn("no-store", detail["Cache-Control"])

    def test_order_search_supports_displayed_reference_full_name_and_phone(self):
        for query in (self.order.number, "Test Customer", "+923001234567", "checkout@example.test"):
            with self.subTest(query=query):
                response = self.client.get(self.url, {"q": query})
                self.assertEqual(response.context["order_counts"]["total"], 1)
        self.assertEqual(
            self.client.get(self.url, {"q": "not-present"}).context["order_counts"]["total"], 0
        )

    def test_dates_use_pakistan_time_and_filters_validate(self):
        from datetime import datetime, timezone

        Order.objects.filter(pk=self.order.pk).update(
            created_at=datetime(2026, 11, 2, 20, 30, tzinfo=timezone.utc)
        )
        response = self.client.get(self.url, {"start": "2026-11-03", "end": "2026-11-03"})
        self.assertEqual(response.context["order_counts"]["total"], 1)
        self.assertEqual(
            self.client.get(self.url, {"end": "2026-11-02"}).context["order_counts"]["total"], 0
        )
        for values in (
            {"start": "bad-date"},
            {"start": "2026-11-04", "end": "2026-11-03"},
            {"status": "injected"},
        ):
            self.assertTrue(self.client.get(self.url, values).context["filters"].errors)
        self.assertEqual(
            self.client.get(self.url, {"fulfillment": "pickup"}).context["order_counts"]["total"], 0
        )
        self.assertEqual(
            self.client.get(self.url, {"payment": "paid"}).context["order_counts"]["paid"], 0
        )

    def test_pagination_preserves_filters_and_handles_invalid_page(self):
        for index in range(26):
            Order.objects.create(
                idempotency_key=uuid.uuid4(),
                request_fingerprint="fixture",
                browser_owner=uuid.uuid4(),
                contact={"first_name": "Page", "last_name": str(index)},
                address={},
            )
        response = self.client.get(self.url, {"status": "placed", "page": "2"})
        self.assertEqual(len(response.context["order_page"]), 2)
        self.assertContains(response, "status=placed")
        self.assertEqual(
            self.client.get(self.url, {"page": "invalid"}).context["order_page"].number, 1
        )

    def test_permissions_hide_navigation_and_protect_all_order_endpoints(self):
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code, 302)
        customer = get_user_model().objects.create_user("ordinary-customer")
        self.client.force_login(customer)
        self.assertEqual(self.client.get(self.detail).status_code, 302)
        unrelated = self.worker("unrelated", [])
        self.client.force_login(unrelated)
        for url in (self.url, self.detail, self.detail + "?panel=1"):
            self.assertEqual(self.client.get(url).status_code, 403)
        self.assertNotContains(self.client.get(reverse("admin:index")), f'href="{self.url}"')
        reader = self.worker("order-reader", ["view_order"])
        self.client.force_login(reader)
        self.assertContains(self.client.get(reverse("admin:index")), f'href="{self.url}"')
        self.assertEqual(self.client.get(self.detail).status_code, 200)
        self.assertNotContains(self.client.get(self.detail), "Update status")
        self.assertEqual(self.update_status("processing").status_code, 403)
        editor = self.worker("order-editor", ["change_order"])
        self.client.force_login(editor)
        self.assertEqual(self.update_status("processing").status_code, 302)

    def test_role_editor_exposes_only_view_and_change_order_permissions(self):
        codes = set(
            RoleForm()
            .fields["permissions"]
            .queryset.filter(content_type__app_label="checkout")
            .values_list("codename", flat=True)
        )
        self.assertEqual(codes, {"view_order", "change_order"})

    def test_delivery_moves_forward_and_keeps_payment_stock_and_prices(self):
        for status in ("processing", "shipped", "delivered", "complete"):
            response = self.update_status(status)
            self.assertEqual(response.status_code, 302)
            self.order.refresh_from_db()
            self.assertEqual(self.order.status, status)
        self.assertEqual(self.order.payment_status, "unpaid")
        self.product.refresh_from_db()
        self.assertEqual(self.product.quantity, 3)
        self.assertEqual(str(self.order.total), "307.50")
        self.assertEqual(
            AuditEvent.objects.filter(action="status_change", module="checkout.order").count(), 4
        )
        self.assertEqual(self.update_status("processing").status_code, 400)

    def test_pickup_uses_pickup_stages_and_rejects_shipping(self):
        self.order.delivery_method = "pickup"
        self.order.save(update_fields=["delivery_method"])
        self.assertEqual(self.update_status("processing").status_code, 302)
        self.order.refresh_from_db()
        self.assertEqual(self.update_status("shipped").status_code, 400)
        for status in ("ready_for_pickup", "collected", "complete"):
            self.assertEqual(self.update_status(status).status_code, 302)
            self.order.refresh_from_db()
            self.assertEqual(self.order.status, status)

    def test_distance_review_requires_explicit_verification(self):
        self.order.status = "delivery_review"
        self.order.save(update_fields=["status"])
        self.assertEqual(self.update_status("processing").status_code, 400)
        self.assertEqual(self.update_status("processing", distance_verified="on").status_code, 302)
        event = AuditEvent.objects.get(action="status_change")
        self.assertEqual(
            event.details,
            {"from": "delivery_review", "to": "processing", "distance_verified": True},
        )

    def test_skips_cancellation_returns_and_stale_changes_are_rejected(self):
        for status in ("shipped", "delivered", "complete", "cancelled", "returned", "unknown"):
            self.assertEqual(self.update_status(status).status_code, 400)
        self.assertEqual(self.update_status("processing").status_code, 302)
        self.assertEqual(self.update_status("shipped", expected="placed").status_code, 409)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, "processing")
        self.assertEqual(AuditEvent.objects.filter(action="status_change").count(), 1)

    def test_csrf_method_guards_and_unknown_orders(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.owner)
        self.assertEqual(csrf_client.post(self.update, {"status": "processing"}).status_code, 403)
        self.assertEqual(self.client.get(self.update).status_code, 405)
        self.assertEqual(self.client.post(self.url).status_code, 405)
        self.assertEqual(
            self.client.get(reverse("admin:order-detail", args=[uuid.uuid4()])).status_code, 404
        )

    def test_audit_failure_rolls_back_status_and_customer_html_is_escaped(self):
        with patch(
            "checkout.admin_views.record", side_effect=RuntimeError("Synthetic audit failure")
        ):
            with self.assertRaises(RuntimeError):
                self.update_status("processing")
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, "placed")
        self.order.contact["first_name"] = '<script>alert("customer")</script>'
        self.order.save(update_fields=["contact"])
        response = self.client.get(self.detail + "?panel=1")
        self.assertContains(response, "&lt;script&gt;")
        self.assertNotContains(response, '<script>alert("customer")</script>')


@override_settings(ALLOWED_HOSTS=["testserver"])
class AdminOrderConcurrencyTests(TransactionTestCase):
    def test_two_admins_cannot_apply_the_same_stale_transition(self):
        owner = get_user_model().objects.create_superuser("concurrent-orders-owner")
        order, _ = order_fixture()
        url = reverse("admin:order-status", args=[order.public_id])

        def submit(_):
            close_old_connections()
            try:
                client = Client()
                client.force_login(owner)
                return client.post(
                    url, {"expected_status": "placed", "status": "processing"}
                ).status_code
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses = sorted(pool.map(submit, range(2)))
        self.assertEqual(statuses, [302, 409])
        self.assertEqual(AuditEvent.objects.filter(action="status_change").count(), 1)
