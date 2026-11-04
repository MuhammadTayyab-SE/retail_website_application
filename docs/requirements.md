# Product requirements

## Current planning increment - 2026-11-04

The existing Django catalog/checkout/admin is implemented; the early setup-only
statements below are historical. The approved next increment is specified in
[catalog-inventory-plan.md](catalog-inventory-plan.md), based on development
f0567ea. This assignment is PM/TL documentation and issue preparation only.
Do not start application implementation as part of this assignment.

Retain Parent Category -> Category -> Product and introduce optional independent
brands. Extend existing variants with automatic defaults, durable generated
SKUs, variant pricing and separate inventory balances/movements. Preserve product
IDs, old codes/prices/stock/media and order snapshots during incremental migration.
Inactive brands do not hide their products. Kg products are priced per kg in
0.1 kg customer steps; count units stay whole. All products track stock initially.
Both deactivation and deletion remain available with retained movement/order/SKU
history. SKU corrections are permitted before the first order, with history,
and are blocked afterward. Module-specific routes/templates/assets reuse the
existing shell; do not render all modules in one hidden-tab HTML page.

Existing immediate deduction on successful order placement is preserved until a
separate reservation lifecycle is agreed. No reservation expiry, refund/restock,
unit-conversion engine, new application or dependency is authorized by this plan.
Detailed migration gates, acceptance criteria and QA expectations are in the plan.

## Agreed scope
Reusable grocery ecommerce for multiple retailers using one shared codebase. Each retailer has an independent domain, hosting server, database, credentials and image storage. Currency is PKR, as confirmed by the user; launch country and payment method remain unresolved. A responsive customer website supports mobile and desktop. A retailer admin panel manages categories, products, variants, prices, stock, orders, branding, banners and delivery settings. Categories and products are dynamic and database-driven.

Zilly (https://www.radiustheme.com/demo/wordpress/themes/zilly/) is visual inspiration. The page could not be inspected in this setup; no visual fidelity claim is made. Confirm a design direction and lawful assets before visual implementation.

## Proposed MVP journey
Browse database catalog -> select variant -> cart -> eligible delivery and checkout -> order confirmation -> staff order processing. Customer identity, payments, tax, delivery and lifecycle semantics remain decisions, not assumed implemented requirements. Branding and banner configuration must be retailer-local. Staff permissions and customer order privacy need explicit validation.

## Quality and operational expectations
Responsive layouts, usable keyboard flows, clear validation/empty/error states, server-side authoritative prices and totals, consistent order/stock updates, access control, synthetic test data, isolated secrets/media, and repeatable deployment/rollback/backup procedures. Concrete performance, accessibility target, traffic and availability budgets remain unresolved (D-015).

## Scope control
No application features are authorized in the first assignment. Tickets in docs/backlog.md describe proposed MVP increments and cannot become Ready while their material dependencies are unresolved. Django/PostgreSQL is adopted as the technical baseline in decisions.md following the empty-code finding. No cross-retailer shared data plane, marketplace or central retailer administration is assumed.

## Business decisions
Agreed choices, deferred production questions, and unresolved business choices are tracked as D-002 through D-015 in docs/decisions.md, with impact and blocking tickets. PM resolves ordinary implementation questions from agreed requirements and asks the user for material business decisions.

## Current delivery scope

Run and test everything locally. Production hosting, server OS, rollout, backup retention and recovery objectives are deferred. Use local filesystem media with separate retailer and test roots, gitignored; preserve configurable storage for later cloud selection. Upload limits remain an explicit technical follow-up. As expanded by the user on 2026-10-11, Super Admin controls worker accounts, roles and module/action permissions through the custom Django admin dashboard. Workers receive only their assigned role access. Portal activity is audited. Parent Categories, Categories and future Products retain creator/editor and timestamps. Employee passwords remain hashed and can be reset by Super Admin; stored passwords are never displayed. The eventual independent production domain, server, database, credentials and image storage requirements remain agreed.
