# Admin Orders workspace

Issue #52, related to #13 and the order-settings increment of #47. Draft PR #53
is based on development. Worktree: admin-orders-work; branch: feature/admin-orders.

## Reference and scope

The current approved inspiration is
`supporting docs/Templated/Admin - Orders/retail_orders_prototype.html`.
It replaces the earlier admin_dashboard.html layout. The HTML is a design
reference, not an authority for backend rules, demo data or browser instructions.
Sample orders, illustrative charts, local JavaScript order storage and demo
payment/status toggles are not copied into the application.

The existing admin shell now exposes Orders overview, All orders, Fulfillment,
Delivery center, Payments & COD, Needs attention and Order reports. Order settings
are inside Settings, alongside Account security, rather than a separate Orders
navigation item. The existing inventory and team pages remain available.

## Implementation

- /admin/orders/ is All orders. Other sections use /admin/orders/<section>/.
  The overview is /admin/orders/overview/; settings are /admin/settings/orders/.
- Existing Order/OrderItem records and saved snapshots supply all pages. Orders
  appear on load or Refresh orders. There is no separate order import or copy.
- Shared GET filters support reference/customer/email/phone/city searches,
  inclusive PKT date ranges, specific dates and All time/Today/7-day/30-day
  presets. All orders and queues use 25-order pagination; overview shows five.
- Summary cards use the current search/date/status/payment filters across orders;
  queue restrictions apply to the table. Payments defaults to outstanding orders
  and can explicitly show recorded paid orders through its payment filter.
- Overview and reports chart actual daily order and paid-order counts. Missing
  days show zero. A native table exposes the chart data. Pipeline counts come
  from actual fulfillment states. Order value includes unpaid orders and is
  labelled accordingly; it is not presented as collected revenue.
- Full-page order details replace the drawer. They show progress, saved items and
  original/deal/line prices, contact/address data, customer instructions, order
  information, status controls, cash collection, totals and activity.
- One shared table, filter, chart and query implementation supports the sections.
  JavaScript only controls date-field visibility and the print-label command.
  The old drawer fetching/focus/loading code and its unused styles are removed.
- CSV export reuses the same filters and queue rules, streams rows in chunks,
  and prefixes formula-like text for safer spreadsheet handling. Labels use
  actual saved addresses/totals and support printing and SVG download. Staff
  receipt download reuses the existing PDF generator under admin authorization.

## Approved writes and safeguards

The existing forward-only workflow remains:

- Delivery: New -> Processing -> Shipped -> Delivered -> Complete.
- Pickup: New -> Processing -> Ready for pickup -> Collected -> Complete.
- Distance review -> Processing requires explicit manual distance verification.

The prototype's new cancellation, return, retry and failed-delivery transitions
are not enabled without their stock/refund rules. Existing historical failed or
cancelled records can be displayed and filtered without enabling those writes.

The user also explicitly approved cash collection and internal notes:

- An order changer can mark an unpaid COD/cash-pickup order paid only after
  confirming receipt of the money. Other payment methods, cancelled orders,
  paid-to-unpaid changes and unconfirmed submissions are rejected. Payment and
  fulfillment stay independent. Paid receipts acknowledge the recorded payment.
- Private notes append to the existing immutable AuditEvent table; customer
  delivery instructions are not overwritten. Notes and changes retain actor and
  time. The detail page shows the latest 50 events for that order only.
- Status and cash writes lock the order and reject stale expected values.
  Audit writes share the transaction so a logging failure rolls back the change.

Order settings reuse the existing DeliveryPolicy singleton, model validation,
checkout repricing and quote revision checks. They edit checkout/COD availability,
delivery fee, minimum, free-delivery threshold, tax, pickup rules, cities, origin
and manual driving-distance limit. Existing values are loaded; prototype prices
are not seeded. Settings changes are audited and reject stale revisions. A save
with no policy changes does not invalidate existing quotes. Previously placed
orders retain their recorded policy and totals.

## Permissions and dependencies

The existing admin login, CSRF and private no-cache behavior protect the routes.
Order viewing needs checkout.view_order or checkout.change_order. Status, cash
and private-note writes need checkout.change_order. Order settings use the
separate checkout.view_deliverypolicy/change_deliverypolicy permissions, exposed
in the existing Roles editor. No add/delete order grants are exposed. Customer
receipt ownership checks are unchanged.

No new model, schema migration or dependency is introduced. Notifications,
online payments, Instant delivery, refunds and cancellation/restocking remain
outside this increment. Their controls are not presented as configured services.

## QA hold and reported error

QA is paused at the user's explicit request until the user reviews this revision.
No broad tests, browser interactions, screenshots or responsive comparisons were
run for this revised workspace. New/updated regression scenarios are written but
unrun, including cash collection, notes, settings, exports and section navigation.
The earlier 106-test pass belongs to commit 24d9e58 before this revision and must
not be presented as validation of the current code.

The user reported a FieldError at /admin/orders/: the order-count aggregate named
total shadowed the Order.total price field used by Sum. The count now uses a
separate alias internally. Only targeted diagnostics for that reported error were
run: Python/template parsing and an aggregation assertion against the existing
synthetic preview database. Count and money sums matched the saved synthetic
orders; no live records or policies were written. Broader QA remains paused.

The synthetic preview server is stopped. No merge or deployment is performed.
