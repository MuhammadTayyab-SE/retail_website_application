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
- Minimum discounted product subtotal: PKR 1,500.
- Delivery fee: PKR 200; free delivery at subtotal >= PKR 5,000.
- Added tax: 0 percent.
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
implemented. Quote errors prevent submission and provide a recovery message.

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

## Validation

Tests use synthetic data in disposable PostgreSQL database
`test_checkout_20261101`; the test runner creates and destroys it. No test orders
were placed in the development catalog.

- 22 Django tests: authoritative prices, fees/thresholds, minimum/city checks,
  manual review, contact validation, CSRF, account/guest isolation, immutable
  snapshots, changed-price rejection, idempotency and rollback, and two concurrent
  order scenarios (last-item competition and duplicate submission).
- 13 Node handler checks: cart behavior and bypass of demo-form interception for
  the real checkout form.
- JavaScript syntax, migration drift, Django system and scoped whitespace checks.
- Browser interaction, visual QA and screenshot comparisons were not run, per the
  user's explicit visual-QA instruction. No full application regression signoff.

User-approved local schema/configuration is enabled. No merge or deployment is
performed by this implementation.
