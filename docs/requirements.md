# Product requirements

## Current MVP strategy - 2026-11-04

The existing Django catalog/checkout/admin is implemented; the early setup-only
statements below are historical. The approved next increment is specified in
[catalog-inventory-plan.md](catalog-inventory-plan.md), based on development
88c7536, with CINV-01/02 merged and reviewed in source. This assignment is PM/TL
documentation and backlog revision only.
Do not start application implementation as part of this assignment.

Retain Parent Category -> Category -> Product and introduce optional independent
brands (already implemented). Reuse the implemented SKU registry/sequence/history.
Extend existing variants with automatic defaults, variant-owned SKU/pricing/unit
and required variant-specific photo ownership, plus inventory balances/movements.
Disposable development/test catalog and transaction data need not be preserved.
Do not add legacy backfills/mapping or duplicate writable authorities for those
records. Preserve application code/functionality and unrelated data. No shared,
staging or production reset is permitted; any destructive database/schema/data
operation requires a confirmed isolated target and separate explicit approval.
This planning update authorizes no destructive operation. Keep the existing
migration chain coherent and add forward migrations, not a database/migration reset.
Inactive brands do not hide their products. Kg products are priced per kg in
0.1 kg customer steps; count units stay whole. All products track stock initially.
Both deactivation and deletion remain available with retained movement/order/SKU
history. SKU corrections are permitted before the first order, with history,
and are blocked afterward. Module-specific routes/templates/assets reuse the
existing shell; do not render all modules in one hidden-tab HTML page. Product
creation/editing retains exactly Basic Info, Variants, Photos and Availability.
Each variant supports multiple images, individual removal, ordering and its own
primary image. A single default variant must remain a simple creation flow.

Existing immediate deduction on successful order placement is preserved until a
separate reservation lifecycle is agreed. No reservation expiry, refund/restock,
unit-conversion engine, new application or dependency is authorized by this plan.
Detailed schema ownership, updated dependencies, destructive-operation gates and
integration test requirements are in the plan. Completed #54/#55 are reused;
#56 is the next Ready ticket, unclaimed. No further feature starts in this review.

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
