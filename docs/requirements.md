# Product requirements

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
All unresolved choices are tracked as D-002 through D-015 in docs/decisions.md, with impact and blocking tickets. PM resolves ordinary implementation questions from agreed requirements and asks the user for material business decisions.

## Current delivery scope

Run and test everything locally. Production hosting, server OS, rollout, backup retention and recovery objectives are deferred. Use local filesystem media with separate retailer and test roots, gitignored; preserve configurable storage for later cloud selection. Upload limits remain an explicit technical follow-up. Only the admin role is in scope now; PM chooses Django admin with a single superuser/admin. Staff role matrices and a custom admin UI are outside current scope unless requested later. The eventual independent production domain, server, database, credentials and image storage requirements remain agreed.
