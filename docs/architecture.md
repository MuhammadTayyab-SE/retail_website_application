# Architecture

## Repository evidence and proposed stack
The inspected repository has only an empty Readme.md and a .gitignore that ignored docs/. There is no existing application, framework, dependency manifest, schema, test suite or CI to preserve or migrate. Django and PostgreSQL are therefore a reasonable adopted foundation (D-001). No runtime architecture has been implemented or validated.

## Shared source, isolated deployments
One repository and versioned release artifact supply every retailer. Each retailer runs its own Django application on its own hosting server, behind HTTPS at its own domain. Each deployment connects only to that retailer's PostgreSQL database using dedicated credentials and to independent image storage using dedicated credentials. Isolation must also cover caches, background jobs, backups and logs if introduced. Do not introduce a shared tenant database or trust a client-supplied retailer ID for isolation.

Retailer environment configuration selects database, allowed hosts, trusted origins, storage, secret keys and service credentials. Retailer branding/content belongs in its database; secrets stay outside source control. Validate required configuration at startup. The precise host, reverse proxy, process manager, storage provider and secret delivery mechanism depend on D-002/D-003.

## Application boundaries
Proposed Django modules: catalog (categories/products/variants), inventory/pricing, carts/checkout, orders, retailer settings/branding/delivery and staff access. Choose the smallest necessary boundaries during scoped tickets. Django admin may provide initial management if agreed workflows and permission coverage support it; a custom admin UI is not yet decided. Customer rendering approach is unresolved; prefer a simple server-rendered responsive frontend unless an agreed requirement justifies more infrastructure.

Proposed data relationships: category -> products -> variants; variant -> price/stock; cart -> items; order -> immutable line, price and delivery snapshots. Exact category hierarchy, variant units, money/tax, stock reservation, delivery rules and lifecycle are blocked on decisions. Use database constraints and transactional order/stock writes once semantics are agreed. Validate authorization and totals on the server.

## Release and testing
Feature branches and isolated worktrees target development through draft PRs. QA tests the exact candidate SHA in a separate checkout with a disposable PostgreSQL database and synthetic media/data. Tests must never connect to production. Per-retailer release rollout and rollback must be versioned, migrations reviewed, and restore procedures demonstrated before launch. Production deployment requires explicit user approval. CI, monitoring, backups and concrete command support are future tickets, not existing capabilities.
