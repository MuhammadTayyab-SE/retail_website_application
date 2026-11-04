# Architecture

## Repository evidence and proposed stack
The initial setup found an empty repository and adopted Django/PostgreSQL (D-001).
That finding is historical. At development f0567ea the application contains
catalog models/admin/forms/gallery, a server-rendered storefront with native
JavaScript, transactional checkout, order snapshots/receipts/labels, and role/audit
modules. Existing behavior and stored data now require preservation and migration.

## Shared source and eventual production deployments
The following deployment requirements describe eventual production; the current local development exception is defined below. One repository and versioned release artifact supply every retailer. Each retailer runs its own Django application on its own hosting server, behind HTTPS at its own domain. Each deployment connects only to that retailer's PostgreSQL database using dedicated credentials and to independent image storage using dedicated credentials. Isolation must also cover caches, background jobs, backups and logs if introduced. Do not introduce a shared tenant database or trust a client-supplied retailer ID for isolation.

Retailer environment configuration selects database, allowed hosts, trusted origins, storage, secret keys and service credentials. Retailer branding/content belongs in its database; secrets stay outside source control. Validate required configuration at startup. The precise host, reverse proxy, process manager, storage provider and secret delivery mechanism depend on D-002/D-003.

## Application boundaries
Existing Django apps are catalog, checkout and access; config provides the custom
RetailAdminSite and routes. Reuse them for the catalog/inventory increment rather
than introducing another app, frontend framework or repository. Super Admin and
assigned worker roles enforce module/action permissions; the initial single-admin
proposal was superseded. Separate module routes/templates/assets extend the
existing navy/emerald shell and share useful form/table/gallery components.

Current relationships are Category.parent, Product.category, ProductVariant.product,
and optional variant-specific ProductPhoto. Price/stock authority is still partly
on Product; checkout deducts shared Product.quantity immediately at successful
order placement and keeps snapshots. The approved target is optional Brand ->
Product (outside taxonomy), default/optional variants -> canonical price and
inventory balance -> immutable stock movements. A durable SKU registry plus
independent sequence prevents reuse. Deletion retains archived balances/movement
and order snapshots. Existing category/product/variant IDs and media paths stay
unchanged. See catalog-inventory-plan.md for the expand/backfill/cutover stages.
Never activate a second writable stock/price source; migrate every existing writer
and reader in a controlled cutover. Reservations remain inactive until separately
defined. Server-side authorization, Decimal arithmetic, row locking and idempotency
remain mandatory across checkout and inventory.

## Release and testing
Feature branches and isolated worktrees target development through draft PRs. QA tests the exact candidate SHA in a separate checkout with a disposable PostgreSQL database and synthetic media/data. Tests must never connect to production. Per-retailer release rollout and rollback must be versioned, migrations reviewed, and restore procedures demonstrated before launch. Production deployment requires explicit user approval. CI, monitoring, backups and concrete command support are future tickets, not existing capabilities.

## Local implementation scope

Current implementation and validation run locally. Two retailer instances may share one development machine using distinct ports/local hosts, PostgreSQL databases and users, secret keys, and isolated filesystem media roots. QA uses a separate disposable test database and media root. These local instances demonstrate configuration isolation; they do not claim to satisfy eventual production server isolation. Media roots are configured outside tracked source and gitignored; use a configurable storage backend so cloud storage can be selected later. Upload limits require explicit technical follow-up. Production hosting/OS/rollout/retention/recovery details and cloud storage are deferred; no cloud service is needed for local catalog work. Independent production domains, servers, databases, credentials and image stores remain the eventual deployment requirement.
