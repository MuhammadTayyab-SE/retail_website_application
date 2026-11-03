# Admin Orders panel

Implements the user-authorized Orders dashboard from issue #52, related to #13.
Visual inspiration: `supporting docs/Templated/Admin - Orders/admin_dashboard.html`.
Only its Orders dashboard and details panel are in scope. Its sample orders,
unrelated modules, demo percentages and third-party scripts are not used.

## Usage and implementation

Run the app from `admin-orders-work` and open `/admin/orders/`. The existing
admin navigation contains an Orders link for authorized users. Checkout orders
appear on page load or Refresh orders; no separate import or order copy exists.
This feature is on `feature/admin-orders`, not development until its PR merges.

The page reuses the existing admin shell and Order/OrderItem tables. It provides
six database-backed summary cards, search by displayed reference/customer/phone/
email, inclusive PKT date filters, status/fulfillment/payment filters, 25-order
pagination, and a right-side details panel. Links also work as standalone detail
pages without JavaScript. Saved item/contact/address/price snapshots are used;
catalog edits do not change recorded order names or totals. Available catalog
photos accompany items; deleted products retain the saved text and prices.

Summary cards reflect the current filters. Payment cleared counts only orders
explicitly stored as paid; completing fulfillment never marks an order paid.
The browser loads only the selected order's details. Related item/photo data is
prefetched rather than fetched separately for every item.

## Approved fulfillment workflow

The user approved these forward-only transitions:

- Delivery: New → Processing → Shipped → Delivered → Complete.
- Pickup: New → Processing → Ready for pickup → Collected → Complete.
- Distance review → Processing requires the admin to explicitly confirm that
  the address is inside the allowed driving distance. This is manual review,
  not a routing-provider distance calculation.

Only the next step is offered and accepted by the server. Unknown statuses,
skips, backward transitions, cancellation and returns are rejected. Stock,
prices, payment status and order snapshots remain unchanged by fulfillment.
Cancellation/restocking/refunds and payment reconciliation need separate rules.

Status writes lock the order row and compare the submitted expected status with
the current status. A stale update receives HTTP 409 and does not overwrite the
other administrator's change. The order write and existing AuditEvent write
share one transaction; an audit-write failure rolls back the status change.
Events capture actor, time, old/new status and the distance-verification flag.

## Permissions and setup

Active Super Admins can access Orders. Other workers require an assigned role
with `checkout.view_order` or `checkout.change_order`; changes specifically
require `checkout.change_order`. These two existing Django permissions are now
available in the existing Roles editor. No order-add/delete grants are exposed.
Navigation visibility and server endpoint checks use the same permissions.
Requests retain the existing admin login gate, CSRF protection and private
no-cache responses. Customer-facing receipt ownership checks are unchanged.

No new dependency, model, migration or live configuration change is required.

## Developer validation and QA hold

Before the user's request to pause QA:

- PASS: 106 Django tests covering Orders, existing admin pages, management,
  roles/audit, checkout and receipts in `test_admin_orders_20261103`.
- The 13 Orders tests exercise actual saved orders, immutable snapshots,
  PKT dates, filtering/search/pagination, role permissions, delivery/pickup
  transitions, manual distance review, stale and concurrent updates, CSRF,
  escaping and rollback when the audit write fails.
- PASS: JavaScript syntax, scoped Python lint and migration drift checks.
- Browser automation could not complete: browser API access was unavailable,
  and native Computer Use stopped because it could not verify the current
  Chrome URL confidently enough. No responsive or interaction pass is claimed.

QA is paused at the user's request. Desktop/tablet/mobile screenshots, reference
comparison, drawer/keyboard/network interaction checks, independent PM review
and QA signoff remain pending. The isolated synthetic preview database and
ignored fixture/media files are available for resuming; its temporary server
has been stopped. No live order was created or updated by these checks.

Pending viewports: 1440px desktop, 768px tablet and 390px mobile. No merge or
deployment is performed by this implementation.
