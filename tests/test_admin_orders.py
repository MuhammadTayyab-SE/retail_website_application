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
from checkout.models import DeliveryPolicy, Order
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
        self.assertEqual(str(response.context["order_counts"]["amount"]), "307.50")
        self.assertEqual(response.context["order_counts"]["awaiting"], 1)
        self.assertEqual(response.context["order_counts"]["paid"], 0)
        self.product.name = "Changed catalog name"
        self.product.price = 500
        self.product.save()
        detail = self.client.get(self.detail + "?panel=1")
        for text in (
            "Checkout milk",
            "Original price",
            "PKR 100.00",
            "After deal",
            "PKR 75.00",
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
        for index in range(20):
            Order.objects.create(
                idempotency_key=uuid.uuid4(),
                request_fingerprint="fixture",
                browser_owner=uuid.uuid4(),
                contact={"first_name": "Page", "last_name": str(index)},
                address={},
            )
        response = self.client.get(self.url, {"status": "placed", "page": "2"})
        self.assertEqual(response.context["order_page"].paginator.per_page, 20)
        self.assertEqual(len(response.context["order_page"]), 1)
        self.assertContains(response, "status=placed")
        self.assertEqual(
            self.client.get(self.url, {"page": "invalid"}).context["order_page"].number, 1
        )

    def test_overview_recent_orders_only_include_today_in_pakistan(self):
        from datetime import datetime, timedelta, timezone
        from zoneinfo import ZoneInfo

        midnight = datetime(2026, 11, 4, tzinfo=ZoneInfo("Asia/Karachi"))
        Order.objects.filter(pk=self.order.pk).update(created_at=midnight)
        others = []
        for created_at in (
            midnight - timedelta(microseconds=1),
            midnight + timedelta(days=1) - timedelta(microseconds=1),
            midnight + timedelta(days=1),
        ):
            order = Order.objects.create(
                idempotency_key=uuid.uuid4(),
                request_fingerprint="fixture",
                browser_owner=uuid.uuid4(),
                contact={},
                address={},
            )
            Order.objects.filter(pk=order.pk).update(created_at=created_at)
            others.append(order)

        overview = reverse("admin:order-workspace", args=["overview"])
        with patch(
            "checkout.admin_views.timezone.now",
            return_value=datetime(2026, 11, 4, tzinfo=timezone.utc),
        ):
            response = self.client.get(overview)
            self.assertEqual(
                {order.pk for order in response.context["order_page"]},
                {self.order.pk, others[1].pk},
            )
            self.assertEqual(response.context["order_page"].paginator.per_page, 5)
            self.assertEqual(response.context["order_counts"]["total"], 4)
            self.assertEqual(sum(day["total"] for day in response.context["activity"]), 3)
            self.assertEqual(self.client.get(self.url).context["order_page"].paginator.count, 4)

        with patch(
            "checkout.admin_views.timezone.now",
            return_value=datetime(2026, 11, 6, tzinfo=timezone.utc),
        ):
            self.assertEqual(self.client.get(overview).context["order_page"].paginator.count, 0)

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
            .queryset.filter(content_type__app_label="checkout", content_type__model="order")
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

    def test_workspace_sections_use_real_orders_and_full_page_details(self):
        for section in (
            "overview",
            "all",
            "fulfillment",
            "delivery",
            "payments",
            "attention",
            "reports",
        ):
            response = self.client.get(reverse("admin:order-workspace", args=[section]))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.context["order_counts"]["total"], 1)
        self.assertEqual(
            self.client.get(reverse("admin:order-workspace", args=["unknown"])).status_code, 404
        )
        detail = self.client.get(self.detail)
        self.assertContains(detail, "Customer &amp; contact")
        self.assertContains(detail, "Order information")
        self.assertNotContains(detail, 'id="orders-drawer"')

    def test_specific_date_and_paid_payment_queue(self):
        from zoneinfo import ZoneInfo

        day = self.order.created_at.astimezone(ZoneInfo("Asia/Karachi")).date()
        response = self.client.get(self.url, {"date_mode": "single", "on": str(day)})
        self.assertEqual(response.context["order_counts"]["total"], 1)
        self.assertTrue(
            self.client.get(self.url, {"date_mode": "single"}).context["filters"].errors
        )
        Order.objects.filter(pk=self.order.pk).update(payment_status="paid")
        payments = reverse("admin:order-workspace", args=["payments"])
        self.assertEqual(len(self.client.get(payments).context["order_page"]), 0)
        self.assertEqual(
            len(self.client.get(payments, {"payment": "paid"}).context["order_page"]), 1
        )

    def test_cash_collection_is_confirmed_audited_and_separate_from_fulfillment(self):
        url = reverse("admin:order-payment", args=[self.order.public_id])
        data = {"expected_payment_status": "unpaid"}
        self.assertEqual(self.client.post(url, data).status_code, 400)
        data["confirmed"] = "on"
        self.assertEqual(self.client.post(url, data).status_code, 302)
        self.order.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual(
            (self.order.payment_status, self.order.status, self.product.quantity),
            ("paid", "placed", 3),
        )
        event = AuditEvent.objects.get(action="cash_collected")
        self.assertEqual(event.details["amount"], "307.50")
        self.assertEqual(self.client.post(url, data).status_code, 409)
        self.assertEqual(AuditEvent.objects.filter(action="cash_collected").count(), 1)
        from checkout.receipts import receipt_details

        self.assertIn("Payment received", receipt_details(self.order)["message"])

    def test_cash_collection_permissions_and_audit_rollback(self):
        url = reverse("admin:order-payment", args=[self.order.public_id])
        data = {"expected_payment_status": "unpaid", "confirmed": "on"}
        self.client.force_login(self.worker("payment-reader", ["view_order"]))
        self.assertEqual(self.client.post(url, data).status_code, 403)
        self.client.force_login(self.owner)
        with patch(
            "checkout.admin_views.record", side_effect=RuntimeError("Synthetic audit failure")
        ):
            with self.assertRaises(RuntimeError):
                self.client.post(url, data)
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, "unpaid")
        Order.objects.filter(pk=self.order.pk).update(payment_method="card")
        self.assertEqual(self.client.post(url, data).status_code, 400)

    def test_private_notes_append_without_overwriting_customer_instructions(self):
        url = reverse("admin:order-note", args=[self.order.public_id])
        self.order.address["notes"] = "Customer delivery instructions"
        self.order.save(update_fields=["address"])
        for note in ("First internal note", '<script>alert("private")</script>'):
            self.assertEqual(self.client.post(url, {"note": note}).status_code, 302)
        self.assertEqual(AuditEvent.objects.filter(action="internal_note").count(), 2)
        self.order.refresh_from_db()
        self.assertEqual(self.order.address["notes"], "Customer delivery instructions")
        response = self.client.get(self.detail)
        self.assertContains(response, "First internal note")
        self.assertContains(response, "&lt;script&gt;")
        guest = Client()
        session = guest.session
        session["checkout_owner"] = str(self.order.browser_owner)
        session.save()
        self.assertNotContains(
            guest.get(reverse("checkout-confirmation", args=[self.order.public_id])),
            "First internal note",
        )

    def test_export_uses_filtered_orders_and_neutralizes_spreadsheet_formulas(self):
        import csv
        from io import StringIO

        self.order.contact["first_name"] = "=FORMULA()"
        self.order.save(update_fields=["contact"])
        response = self.client.get(reverse("admin:orders-export"), {"q": self.order.number})
        rows = list(csv.reader(StringIO(b"".join(response.streaming_content).decode())))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1][0], self.order.number)
        self.assertTrue(rows[1][1].startswith("'="))
        self.assertIn("no-store", response["Cache-Control"])

    def test_staff_receipt_and_label_downloads_are_protected(self):
        receipt = reverse("admin:order-receipt", args=[self.order.public_id])
        label = reverse("admin:order-label", args=[self.order.public_id])
        response = self.client.get(receipt)
        self.assertTrue(b"".join(response.streaming_content).startswith(b"%PDF-"))
        pdf = self.client.get(label, {"download": "1"})
        self.assertEqual(pdf["Content-Type"], "application/pdf")
        self.assertTrue(b"".join(pdf.streaming_content).startswith(b"%PDF-"))
        self.assertIn("attachment", pdf["Content-Disposition"])
        preview = self.client.get(label, {"preview": "1"})
        self.assertIn("inline", preview["Content-Disposition"])
        self.assertEqual(preview["X-Frame-Options"], "SAMEORIGIN")
        self.assertIn("no-store", preview["Cache-Control"])
        self.client.logout()
        self.assertEqual(self.client.get(receipt).status_code, 302)
        self.assertEqual(self.client.get(label).status_code, 302)

    def test_label_saves_shipping_and_snapshots_return_address_without_changing_order(self):
        url = reverse("admin:order-label", args=[self.order.public_id])
        settings = self.settings_data()
        settings["return_address"] = "Synthetic warehouse, Lahore"
        self.client.post(reverse("admin:order-settings"), settings)
        response = self.client.get(url)
        data = dict(response.context["label_form"].initial)
        self.assertEqual(data["return_address"], settings["return_address"])
        self.assertEqual(self.order.shipping_details, {})
        data.update(
            action="save",
            courier="Test courier",
            tracking="ABC-123",
            weight_kg="1.250",
            pieces="2",
            total="0.01",
            contact="tampered",
        )
        self.assertEqual(self.client.post(url, data).status_code, 302)
        self.order.refresh_from_db()
        self.assertEqual(self.order.shipping_details["weight_kg"], "1.250")
        self.assertEqual(self.order.shipping_details["pieces"], 2)
        self.assertEqual(self.order.shipping_details["tracking"], "ABC-123")
        self.assertEqual(str(self.order.total), "307.50")
        self.assertEqual(self.order.contact["first_name"], "Test")
        self.assertEqual(AuditEvent.objects.filter(action="shipping_details_change").count(), 1)
        self.assertEqual(self.client.post(url, data).status_code, 409)
        DeliveryPolicy.objects.filter(pk=1).update(return_address="Different warehouse")
        self.assertEqual(
            self.client.get(url).context["label_form"].initial["return_address"],
            "Synthetic warehouse, Lahore",
        )

    def test_label_validation_permissions_and_audit_failure_preserve_saved_details(self):
        url = reverse("admin:order-label", args=[self.order.public_id])
        data = dict(self.client.get(url).context["label_form"].initial, action="save")
        for invalid in (
            {"tracking": "ABC<script>"},
            {"weight_kg": "-1"},
            {"pieces": "0"},
            {"format": "unknown"},
        ):
            with self.subTest(invalid=invalid):
                self.assertEqual(self.client.post(url, {**data, **invalid}).status_code, 400)
        self.order.refresh_from_db()
        self.assertEqual(self.order.shipping_details, {})
        with patch("checkout.admin_views.record", side_effect=RuntimeError("audit unavailable")):
            with self.assertRaises(RuntimeError):
                self.client.post(url, data)
        self.order.refresh_from_db()
        self.assertEqual(self.order.shipping_details, {})
        self.assertIsNone(self.order.shipping_updated_at)
        self.client.force_login(self.worker("label-reader", ["view_order"]))
        self.assertNotContains(self.client.get(url), "Save &amp; preview")
        self.assertEqual(self.client.post(url, data).status_code, 403)
        self.client.force_login(self.worker("no-label-access", []))
        for params in ({}, {"preview": "1"}, {"download": "1"}):
            self.assertEqual(self.client.get(url, params).status_code, 403)

    def test_label_assets_are_only_loaded_in_studio_and_download_uses_saved_options(self):
        url = reverse("admin:order-label", args=[self.order.public_id])
        self.assertNotContains(self.client.get(self.url), "catalog/admin/labels.css")
        response = self.client.get(url)
        self.assertContains(response, "catalog/admin/labels.css")
        self.assertContains(response, 'id="label-settings-form"')
        self.assertContains(response, 'form="label-settings-form"')
        self.assertContains(response, 'name="format"')
        self.assertContains(response, 'name="palette"')
        self.assertContains(response, "Line items &amp; SKUs")
        data = dict(response.context["label_form"].initial, action="download", format="a4")
        self.assertRedirects(
            self.client.post(url, data), url + "?download=1", fetch_redirect_response=False
        )
        self.order.refresh_from_db()
        self.assertEqual(self.order.shipping_details["format"], "a4")

    def test_label_pdf_formats_contents_and_cash_due_use_order_snapshots(self):
        from pypdf import PdfReader

        from checkout.labels import LABEL_FORMATS, LabelForm, label_pdf

        options = LabelForm(order=self.order).initial
        self.product.name = "Changed catalog name"
        self.product.save()
        for format, size in LABEL_FORMATS.items():
            for palette in ("branded", "thermal"):
                with self.subTest(format=format, palette=palette):
                    reader = PdfReader(
                        label_pdf(self.order, {**options, "format": format, "palette": palette})
                    )
                    page = reader.pages[0]
                    self.assertAlmostEqual(float(page.mediabox.width), size[0], places=3)
                    self.assertAlmostEqual(float(page.mediabox.height), size[1], places=3)
                    text = "\n".join(page.extract_text() for page in reader.pages)
                    self.assertIn("CASH TO COLLECT: PKR 307.50", text)
                    self.assertIn("Checkout milk", text)
                    self.assertNotIn("Changed catalog name", text)
        self.order.payment_status = "paid"
        pdf = label_pdf(self.order, {**options, "contents": "hidden"})
        text = "\n".join(page.extract_text() for page in PdfReader(pdf).pages)
        self.assertIn("PAID - DO NOT COLLECT", text)
        self.assertNotIn("CASH TO COLLECT", text)
        self.assertNotIn("Checkout milk", text)
        self.order.payment_status = "unpaid"
        self.order.payment_method = "card"
        reader = PdfReader(label_pdf(self.order, {**options, "contents": "summary"}))
        text = "\n".join(page.extract_text() for page in reader.pages)
        self.assertIn("PAYMENT NOT VERIFIED", text)
        self.assertNotIn("CASH TO COLLECT", text)
        self.assertIn("PACKAGE CONTENTS / 2 items", text)
        self.assertNotIn("Checkout milk", text)

    def test_long_labels_continue_without_losing_items_or_repeating_cash_collection(self):
        from pypdf import PdfReader

        from checkout.labels import LabelForm, label_pdf

        source = self.order.items.get()
        for index in range(15):
            self.order.items.create(
                product=self.product,
                name=f"Parcel item {index:02d} " + "long name " * 30,
                sku="SYNTHETIC",
                description="",
                quantity=1,
                regular_price=source.regular_price,
                unit_price=source.unit_price,
                line_total=source.unit_price,
            )
        options = {
            **LabelForm(order=self.order).initial,
            "format": "4x4",
            "show_prices": True,
            "return_address": "Synthetic warehouse " * 40,
        }
        reader = PdfReader(label_pdf(self.order, options))
        text = "\n".join(page.extract_text() for page in reader.pages)
        self.assertGreater(len(reader.pages), 1)
        self.assertIn("Parcel item 14", text)
        self.assertEqual(text.count("CASH TO COLLECT"), 1)
        self.assertIn("CONTINUATION - SAME PARCEL", text)

    def test_prototype_label_layouts_include_real_order_qr_and_detachable_a4_label(self):
        from pypdf import PdfReader
        from reportlab.graphics.barcode import createBarcodeDrawing

        from checkout.labels import LabelForm, label_pdf

        options = {**LabelForm(order=self.order).initial, "tracking": "SYNTHETIC-AWB-123"}
        for format in ("4x6", "4x4", "a4"):
            with self.subTest(format=format):
                with patch(
                    "checkout.labels.createBarcodeDrawing", wraps=createBarcodeDrawing
                ) as codes:
                    reader = PdfReader(label_pdf(self.order, {**options, "format": format}))
                text = "\n".join(page.extract_text() for page in reader.pages)
                qr = [call for call in codes.call_args_list if call.args[0] == "QR"]
                self.assertEqual(len(qr), 1)
                self.assertEqual(qr[0].kwargs["value"], self.order.number)
                barcode = [call for call in codes.call_args_list if call.args[0] == "Code128"]
                self.assertEqual(barcode[0].kwargs["value"], "SYNTHETIC-AWB-123")
                self.assertIn("SHIP TO / CONSIGNEE", text)
                self.assertIn("AWB / TRACKING NUMBER", text)
                if format == "a4":
                    self.assertIn("PACKING SLIP & DISPATCH MANIFEST", text)
                    self.assertIn("DETACH ALONG DOTTED LINE", text)
                    self.assertIn("PACKER CHECK", text)
                else:
                    self.assertNotIn("PACKING SLIP & DISPATCH MANIFEST", text)
                if format == "4x6":
                    self.assertIn("DESTINATION CITY", text)

    def settings_data(self):
        policy = DeliveryPolicy.objects.get(pk=1)
        values = {
            name: str(getattr(policy, name)) if getattr(policy, name) is not None else ""
            for name in (
                "minimum_order",
                "delivery_fee",
                "free_delivery_threshold",
                "tax_rate",
                "pickup_fee",
                "pickup_minimum_order",
                "origin_latitude",
                "origin_longitude",
                "delivery_radius_km",
                "return_address",
            )
        }
        values.update(
            enabled="on",
            cash_on_delivery="on",
            allowed_cities="Lahore",
            expected_revision=policy.updated_at.isoformat(),
        )
        return values

    def test_settings_live_under_settings_and_preserve_existing_order_totals(self):
        url = reverse("admin:order-settings")
        self.assertContains(self.client.get(reverse("admin:settings")), f'href="{url}"')
        data = self.settings_data()
        data.update(delivery_fee="225.00", free_delivery_threshold="5000.00")
        self.assertEqual(self.client.post(url, data).status_code, 302)
        policy = DeliveryPolicy.objects.get(pk=1)
        self.assertEqual(str(policy.delivery_fee), "225.00")
        self.assertEqual(policy.allowed_cities, ["Lahore"])
        self.order.refresh_from_db()
        self.assertEqual(str(self.order.total), "307.50")
        self.assertEqual(AuditEvent.objects.filter(action="order_settings_change").count(), 1)
        self.assertEqual(self.client.post(url, data).status_code, 409)

    def test_settings_require_separate_permissions_and_reject_negative_fees(self):
        url = reverse("admin:order-settings")
        data = self.settings_data()
        data["delivery_fee"] = "-1.00"
        self.assertEqual(self.client.post(url, data).status_code, 400)
        self.client.force_login(self.worker("settings-reader", ["view_deliverypolicy"]))
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(self.client.post(url, self.settings_data()).status_code, 403)
        self.client.force_login(self.worker("orders-editor-only", ["change_order"]))
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_super_admin_can_assign_settings_permissions_through_existing_role_form(self):
        permission = Permission.objects.get(
            content_type__app_label="checkout", codename="change_deliverypolicy"
        )
        response = self.client.post(
            reverse("admin:access_role_add"),
            {"name": "Order settings manager", "permissions": [permission.pk], "_save": "Save"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            Role.objects.get(name="Order settings manager")
            .permissions.filter(pk=permission.pk)
            .exists()
        )


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
