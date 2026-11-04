# CINV-02 — Durable SKU issuance and correction history

Issue #55, explicitly started by the user on 2026-11-04. Developer worktree
`catalog-sku-work`, branch `feature/cinv-02-sku`, baseline development f628e93
(merged CINV-01). Independent QA remains paused. No new product-creation UI,
default variants, inventory ledger, pricing or fractional quantity changes.

## Implementation plan

- Reuse Product/ProductVariant and immutable AuditEvent. Add a retained
  SkuIdentifier registry and an independent non-cycling PostgreSQL sequence.
- Preflight current products/variants, order snapshots and recoverable audit
  identifiers. Accept unambiguous same-product aliases; stop on cross-product or
  ambiguous ownership. Preserve original catalog/order values; reserve unknown
  deleted history without making it assignable. Seed above recovered numeric SKUs.
- Centralize database reservation and alias synchronization so both legacy
  columns use one namespace, including bulk writes. Reuse existing order locks;
  reject corrections once ordered (including product-only legacy lines).
- Add one Python assignment API and explicit override permission. Existing admin
  forms continue to work through the model save/validation path; no new UI rollout.
  Retain actor/time/old/new history and reservations after correction/deletion.
- Check allocation/rollback/concurrency, overrides/revocation, alias correction,
  post-order rejection, retained/deleted codes, migration conflicts, seed/overflow,
  and affected product/brand/checkout/audit behavior in a disposable PostgreSQL DB.

## Operational boundary

Catalog writes must pause for the migration. Previously deleted codes
without surviving order/audit evidence cannot be recovered. Never reset the
retailer database or rewind the issuance sequence during recovery.

## Implemented behavior

- `SkuIdentifier` stores normalized lowercase reservation keys, original owner
  snapshots, nullable live owners, actor/time/source and first-order use. Existing
  Product/Variant/order SKU strings are not renumbered. Owner deletion clears only
  live links; issued rows cannot be edited/deleted through the model API.
- `assign_sku(item, actor=..., code=None)` generates `SKU-000001`-style values
  from a separate bigint PostgreSQL sequence. Six digits are a minimum width;
  numbers are not truncated at 999999. Gaps after rollbacks are expected and never
  reclaimed. Existing and recovered numeric codes seed the counter; manual codes
  reserved later are skipped when the generator reaches them. Overflow fails
  without cycling. No identifier is derived from a product PK/name.
- The assignment API requires active staff product-edit permission. A manual code
  also requires `catalog.override_sku`, exposed through existing Roles. Existing
  admin forms enforce this permission too, including manual initial codes. Initial
  trusted non-HTTP ORM imports remain supported without an actor; corrections
  require one. ORM/raw SQL access is privileged application/operator access,
  not an alternative public API or a substitute for role authorization.
- PostgreSQL guards reserve both legacy SKU columns in one namespace, reject
  cross-product/deleted/retired codes and synchronize a matching same-product
  Product/Variant alias. Product-only order lines freeze every existing variant;
  specific variant orders freeze that variant and the product's SKU alias, leaving
  unrelated unordered siblings correctable. Permanent `ordered_at` evidence
  survives order deletion where an issued identifier exists.
- Corrections append immutable `AuditEvent` entries with old/new values and actor
  snapshots/time, including programmatic assignment and alias synchronization.
  Product admin locks validation/save together so competing overrides return a
  normal form error. Checkout keeps its existing prices, quantities, idempotency
  and single stock deduction; its product locks serialize accepted orders with
  SKU changes. No new UI or dependency was introduced.
- Migration 0013 reserves current Product/Variant codes, retained order snapshots
  and recoverable audit changes. Cross-product, conflicting variant and unknown
  deleted-history collisions stop migration. Unknown codes are reserved without a
  fabricated owner. Original values/IDs/photos/order amounts remain intact.
  The read-only `check_skus` command shares the preflight and numeric-seed checks.

## Setup and recovery

Use the feature checkout/environment. Pause all old/new catalog and checkout
writers, take a PostgreSQL backup, then run:

```powershell
.venv\Scripts\python.exe manage.py check_skus
.venv\Scripts\python.exe manage.py migrate catalog 0013 --noinput
.venv\Scripts\python.exe manage.py check
```

Run only updated application writers against the migrated database. Older
checkouts do not supply SKU correction attribution and must not edit SKUs against
this schema. Keep optional automatic-creation UI/default variants in CINV-03.
Current manual-creation staff need the explicit override grant; ordinary updates
that retain a SKU do not. No blanket role grants are added by the migration.

Migration locks catalog/order/audit writes during reconciliation. Its reverse
guard rejects a downgrade if reservations exist. Recover forward while retaining
registry/sequence; never delete issued rows, rewind a counter or reset the DB.
An approved full backup restore must account for orders/codes issued afterward.
Pre-evidence deleted identifiers cannot be reconstructed. The shared application
database account remains trusted, as with existing immutable audit history.

## Developer evidence (2026-11-04)

- Final focused `manage.py test tests.test_skus --noinput --verbosity 1`: all
  **20 pass**, including allocation/manual collisions, sequence rollback/overflow,
  role revocation and forged admin posts, alias synchronization/history, deletion,
  legacy order locking, simultaneous overrides (including real admin POSTs),
  accepted-order/correction contention, partial saves and migration failures/retry.
- Affected run covering SKU, Products, Brands, Checkout, roles/audit, Categories
  and receipts: **140 pass**. Later final change only rejects whitespace-only
  variant SKUs in bulk writes; the focused SKU suite passed after that change.
- Full developer run: **268 tests, 263 pass, 4 failures + 1 error**. All five
  reproduce on unchanged development f628e93 in a temporary detached checkout and
  distinct `test_cinv02_baseline`: two existing storefront query budgets
  (17/18 versus 12), old `50% off` text, old `Customer & contact` text and an Orders
  test passing `pieces=None` as multipart data. No unrelated repair is included.
  Temporary baseline checkout removed. Primary developer DB: test_cinv02_sku.
- System check, migration drift, scoped catalog/access/config/new-and-affected-test
  Ruff lint, nine changed Python-file format checks and `git diff --check` pass.
- Read-only real-local preflight found 10 recoverable codes with no ownership
  conflicts. On inspection, migration 0013 was already applied locally at
  2026-11-04 13:43:58 Asia/Karachi (not applied by this setup command). The locally
  applied SQL guard predated final corrections. A private ignored PostgreSQL 18
  backup was taken, then only that function was replaced to match final source.
  Hashes verify Product/Variant/Photo/OrderItem/registry rows and sequence state
  unchanged by synchronization. No SKU or stock was assigned in real dev data.
- User reported missing photos on the running catalog-sku-work port 8000. The
  new worktree's ignored `.env` now points MEDIA_ROOT at the development checkout's
  existing uploads, with no DB/image copying or record changes. All 17 product,
  15 category and 1 brand files exist. The local server reloaded, and public
  visible-product image URLs were checked separately. README/.env.example explain
  worktree media setup and restarting an inherited environment.

Developer checks are not independent review/QA. Independent QA remains paused;
no browser/visual signoff, merge or deployment is claimed. Issue stays In Development.
