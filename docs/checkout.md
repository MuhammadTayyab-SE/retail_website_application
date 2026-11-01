# Storefront checkout

## Scope and decisions — 2026-11-01

Reference: user-provided `supporting docs/Templated/checkout/zilly_checkout_page.html`,
used as layout inspiration. Existing storefront header, footer, fonts, green
palette, cart images and product prices are reused; no Tailwind CDN or mock order
data from the reference is imported.

The user authorized real order placement, backend/schema changes, guest checkout
and existing signed-in accounts. Online payment integration is deferred until a
provider is selected. The working payment method is cash on delivery.

Approved initial local rules:
- Lahore only, case-insensitive city matching.
- Minimum discounted product subtotal for Standard delivery: PKR 1,500.
- Delivery fee: PKR 200; free delivery at subtotal >= PKR 5,000.
- Added tax: 0 percent.
- Store Pickup is enabled, free, with no minimum or delivery-address requirement.
- Instant is visible but unavailable until its fee/timing are approved.
- Delivery limit: 10 km driving distance from the user-provided store coordinates.
- Routing provider deferred. User explicitly approved accepting Lahore orders
  for manual distance verification. These orders have status `delivery_review`,
  explained before submission and on the private confirmation page. The code does
  not substitute straight-line distance or claim the driving distance is verified.

All values live in the retailer-local DeliveryPolicy record, not templates or
JavaScript. Coordinates and the initial rules file remain in ignored local
configuration. Admin controls and routing/payment integrations are backlog items
in `docs/tickets/CHECKOUT-FOLLOWUPS.md`. No admin screens were changed.

## Behavior and integrity

The floating drawer links to `/checkout/`. The two-column layout becomes a single
column on tablet/mobile. Contact and address fields, delivery, cash-on-delivery
choice, server-quoted order summary, free-delivery progress and confirmation are
implemented. Below-minimum and out-of-area quotes retain the server-priced summary
with an eligibility message while blocking submission. A browser cart preview is
rendered before the quote so a network failure cannot leave a blank summary;
unverified charges are labelled Pending.

The order-summary card follows the supplied Cart Item reference: photo/name,
struck-through original price where discounted, current price, compact quantity
stepper, trash-icon deletion and Clear All. These controls edit the shared cart
and trigger a new authoritative quote. Stock limits account for other variants of
the same product. Extra measuring-unit labels are omitted; catalog product names
and pack sizes are preserved. Eligible delivery and pickup shipping display Free,
and zero tax is hidden. Coupon fields are a disabled visual section until coupon
rules are implemented. View cart opens the shared drawer; Place order submits the
existing checkout form. No security/encryption claims are copied from the reference.

Credit/debit card and JazzCash/Easypaisa/Raast panels expand to show the reference
fields. Fields are disabled and have no submitted names: no card numbers, CVVs or
wallet identifiers are collected. Only cash can place an order.

The browser sends catalog IDs and quantities; client names, prices, discounts and
totals cannot set order amounts. The server validates product/variant visibility,
aggregates stock across variants, applies existing catalog sale prices, and
calculates policy charges using Decimal. A signed 15-minute quote is checked again
against current values at placement. Changed charges require customer review.

Order creation, immutable item/address/price/policy snapshots, and stock allocation
commit atomically. Product rows are locked in deterministic order. A unique
idempotency key and request fingerprint prevent duplicate/replayed submissions.
Cash-on-delivery orders remain unpaid. Successful checkout removes purchased
quantities from the tab cart, retaining items added while the request was pending.

Confirmation URLs use random UUIDs and also enforce account ownership or the
guest's server-side browser session. Other accounts/browsers receive 404.
Endpoints require CSRF protection and private responses are not cacheable.

Placed orders persist in PostgreSQL. Unplaced carts still use browser-tab storage;
durable guest/account carts and registration are separate scope, not claimed here.
Order processing/cancellation/restocking/notifications require the follow-up work.

## Confirmation receipt and PDF download

The updated user-supplied confirmation reference is implemented as a complete
receipt page: order ID/date (Asia/Karachi), customer and address details,
delivery/pickup, actual payment/order status, item names/SKUs/quantities, regular
and discounted unit prices, line totals, original total, item savings, net
subtotal, shipping/pickup, tax and amount payable. It uses saved order snapshots,
so later product edits cannot change the receipt. No email/WhatsApp notification,
paid status, merchant street address or pickup time is invented from demo content.

Download PDF returns an attachment from
`/checkout/orders/<public_id>/receipt.pdf`. The same account/guest ownership check
protects both HTML and PDF, with no-cache headers and 404 for other viewers.
ReportLab generates an actual PDF using the existing local Inter font, wrapped
tables, repeated table headings and numbered pages for long orders. A separate
Print receipt action uses the browser's print dialog and print stylesheet.

ReportLab is a locked runtime dependency; pypdf is a locked test dependency.
Run `uv sync --frozen` when updating an existing environment. No additional schema
migration is needed for receipt export. PDFs are streamed without saving customer
receipt files to the server's public/static directories.

Six PDF/receipt tests verify download headers, contents and totals, immutable
prices, special characters, pagination, manual/pickup status and ownership.
PDF text/structure was checked programmatically. Browser/PDF visual rendering
and screenshots were not performed, following the user's visual-QA hold.

## Local setup

Worktree: `checkout-work`, branch `feature/storefront-checkout`, based on the
cart feature so it includes the shared drawer work. Keep `.env` ignored and set
MEDIA_ROOT to the existing development media directory.

```powershell
.venv\Scripts\python.exe manage.py migrate checkout --noinput
.venv\Scripts\python.exe manage.py configure_checkout .local/checkout-rules.json
.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

The ignored rules JSON must explicitly contain enabled, delivery_fee,
free_delivery_threshold (null disables the promotion), minimum_order, tax_rate,
allowed_cities, cash_on_delivery, origin_latitude, origin_longitude,
delivery_radius_km and distance_verification. The supported interim mode is
`manual`. Configuration is validated before being saved. No production defaults
or enabled rules are seeded by the migration. Missing/disabled policy closes
checkout. The user-approved local policy has been applied to `pg_retail_dev`.
The JSON also requires pickup_enabled, pickup_fee and pickup_minimum_order.
Migration `checkout.0002_deliverypolicy_pickup_enabled_and_more` adds the dynamic
pickup fields and order fulfillment method. It has been applied locally.

## Validation

Tests use synthetic data in disposable PostgreSQL database
`test_checkout_20261101`; the test runner creates and destroys it. No test orders
were placed in the development catalog.

- 32 Django tests: receipts/PDF downloads, authoritative prices, fees/thresholds, minimum/city checks,
  manual review, contact validation, CSRF, account/guest isolation, immutable
  snapshots, changed-price rejection, idempotency and rollback, and two concurrent
  order scenarios (last-item competition and duplicate submission).
- 20 Node checks: cart behavior, checkout submit routing, summary preservation on
  eligibility/network errors, empty-cart recovery and pickup field handling.
- JavaScript syntax, migration drift, Django system and scoped whitespace checks.
- Browser interaction, visual QA and screenshot comparisons were not run, per the
  user's explicit visual-QA instruction. No full application regression signoff.

User-approved local schema/configuration is enabled. No merge or deployment is
performed by this implementation.
