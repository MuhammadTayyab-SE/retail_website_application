# Checkout configuration and payment backlog

Date: 2026-11-01. User authorized real checkout, guests and existing signed-in
accounts, cash on delivery now, and online payments later. Delivery charges,
free-delivery unlock, eligibility, minimums and tax rules must be dynamic.
Their management UI is explicitly deferred to these backlog items.

## CHECKOUT-ADMIN-001 — Retailer delivery and tax settings

State: Backlog. Owner: Admin developer role. Initial local rules approved on 2026-11-01.
Tracker: https://github.com/MuhammadTayyab-SE/retail_website_application/issues/47

- Permission-controlled admin management for the retailer-local DeliveryPolicy.
- Configure enable/disable, delivery fee, nullable free-delivery threshold,
  minimum order, allowed cities, tax rate and cash-on-delivery availability.
- Validate nonnegative monetary rules, 0–100 percent tax, valid city lists and
  blank threshold as no free-delivery promotion. No invented defaults.
- Preview checkout effects before saving; audit changes and validate permissions.
- Checkout quotes, free-delivery progress and order snapshots use the saved rules.
- Revalidate final charges and eligibility at order placement; concurrent setting
  changes cannot silently change a customer-accepted quote.
- Current change provides a validated management command for explicitly supplied
  JSON rules. No admin screens, permissions or staff dashboards are modified yet.

## CHECKOUT-PAY-001 — Online payment provider integration

State: Backlog. Blocked on provider selection and its merchant onboarding.
Tracker: https://github.com/MuhammadTayyab-SE/retail_website_application/issues/48

- User will select a provider; use its official hosted checkout or tokenization.
- Keep API keys in environment configuration; never store raw card details.
- Verify signed server-to-server payment notifications and merchant/amount/currency.
- Define pending/paid/failed/refunded transitions, retry/idempotency behavior,
  stock reservation/expiry and refunds before implementation.
- Redirects alone must never mark an order paid. Test sandbox success, failure,
  cancellation, duplicate callbacks, expired sessions and tampered amounts.

## CHECKOUT-ADMIN-002 — Order processing

State: Backlog. Depends on approved fulfillment/cancellation rules.

- Authorized staff can view order snapshots and payment status.
- Define processing/dispatch/completion/cancellation transitions and restocking.
- Enforce module/action permissions and audit access to customer information.
- No notification or delivery-time promises until those services are configured.

## CART-PERSIST-001 — Durable guest/account carts

State: Backlog. Separate from the current browser-tab cart and placed-order storage.

- Database carts for accounts and anonymous persistent browser tokens.
- Guest/account merge, logout separation, expiry and deletion rules require approval.
- Test user isolation, returning users, multiple tabs/devices and concurrent updates.

## CHECKOUT-MAPS-001 — Driving-distance eligibility

State: Backlog. Blocked on selecting a routing/map provider.
Tracker: https://github.com/MuhammadTayyab-SE/retail_website_application/issues/49

- Compute actual driving distance from the configured store origin to a customer
  delivery pin. The user chose driving distance, not a straight-line radius.
- Enforce the configured 10 km limit server-side; test boundary, unsupported
  routes, location errors, provider timeouts and changed routes.
- Add an accessible delivery-location picker and route preview. Avoid collecting
  location automatically; customers explicitly select their delivery location.
- Protect provider credentials and define rate limits, caching, cost and outage
  behavior. Never silently fall back to a straight-line calculation.
- Interim behavior explicitly approved by the user: accept Lahore orders for
  manual driving-distance verification, with `delivery_review` status and clear
  checkout/confirmation notices. Staff confirmation and rejection/restocking flows
  belong to CHECKOUT-ADMIN-002.
