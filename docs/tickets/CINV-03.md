# CINV-03 — Variant identity, defaults and variant photo ownership

User started #56 on 2026-11-05. Baseline development 4c4d236; isolated branch
feature/cinv-03-variants in catalog-variants-work. Reuse merged Brands and SKU
registry/sequence/history. No CINV-04 pricing or CINV-05/06 ledger changes, and
no complete CINV-09 four-tab rollout.

## Implementation plan

- Extend ProductVariant with default/barcode/inventory-unit/package fields, use
  the existing SKU allocator for automatic default creation, and retain override,
  permanent reservation and order-lock rules. Remove Product.sku/unit and obsolete
  SQL alias coupling. Lock parent products before default/SKU/photo operations.
- Reuse ProductPhoto, require its variant, remove redundant product FK and add a
  per-variant primary flag. Reuse upload/preview/order/removal/commit-safe cleanup.
  Unique plus deferred database guards and scoped formsets protect complete
  defaults/nonempty galleries, including direct/concurrent writes.
- Adapt current Product admin/default creation and a selected variant editor,
  using the supplied products/retail-admin-preview - varients.html variant card
  layout. Keep current shell and gallery controls; no duplicated allocator/gallery
  or unrelated hidden module screens. All related forms save atomically.
- Switch catalog/shop/home/detail/cart/checkout/image consumers, audit attribution
  and test fixtures to variant SKU/unit/images. Stock and pricing authority stay
  at their existing stage until their owning tickets.
- Add forward migrations that reject incompatible populated catalog tables
  instead of backfilling/purging records. Keep 0001-0013 intact. Static validation
  is allowed now; destructive schema/test-runner operations require a separate,
  concrete isolated-target approval before execution.

## Proposed isolated targets — not approved for destructive operations

Ignored feature configuration names retail_cinv03_dev and test_cinv03_variants;
synthetic media is catalog-variants-work/.local/media. No database has been
created/reset/migrated by this setup, and shared pg_retail_dev is not targeted.
Host/server identity and name availability will be checked read-only before any
approval request. No existing uploads are copied, removed or rewritten.

## Verification planned

Automatic/add-only creation, default switching/removal/concurrency, SKU override/
freeze/history/no-reuse, barcode/unit/package validation, per-variant gallery
multi-upload/primary/reorder/removal/forged IDs, rollback and media cleanup,
existing catalog/checkout/receipt/label routes, schema chain and permissions.
Browser comparison is against the supplied variant cards within existing admin
design. Developer checks are not independent QA; prior QA execution hold remains.

## Current implementation and gate

Code and forward migration are prepared. Product creation generates its default
variant/SKU atomically, including add-only staff. Variant metadata and default
switch/removal use parent locks and database default constraints. ProductPhoto has
one required variant, explicit per-variant primary selection and existing file
validation/commit-safe cleanup; the current product gallery and a selected variant
editor reuse the same inline/formsets/script. Catalog, shop, detail, cart, order
image and SKU/unit readers now use selected/default variants. Product pricing,
shared quantity and order deduction remain at their current CINV-04/06 stage.

Approved visual reference: supporting docs/Templated/products/
retail-admin-preview - varients.html, Product variants cards, identity/unit/package
fields and per-variant gallery controls, within the existing admin shell. The full
four-tab composition remains CINV-09. No demo data/JavaScript is executed or copied.

Static developer checks performed: Django system check, scoped Ruff lint, Python
source parsing, Node syntax and four product/variant template compilations pass.
Migration autodetection reports no changes; its applied-history check cannot
connect because the proposed development database intentionally does not exist.
No migration SQL or database tests have been executed. Tests/fixtures have been
updated to the new contracts, with fresh default/gallery/concurrency and migration
guard scenarios, but they remain unverified pending the database gate.

Read-only environment confirmation found PostgreSQL 18.6 on loopback ::1:5432.
The proposed role retail_cinv03 and both database names were unused. The user has
been asked to approve creation of this non-superuser role/development database,
forward migration only there, and repeated test-runner create/migrate/drop for
test_cinv03_variants plus its synthetic test media. The development target is
retained for review. No approval has been received yet; no role/database/media
reset or migration is performed. Shared pg_retail_dev and original uploads remain
outside the scope. Concrete local proposal: .local/database-approval.md (ignored).

Status: In Development, not ready for QA/My Review. Required next evidence after
approval: PostgreSQL migration/constraints/permissions/concurrency/rollback tests,
affected existing suites and actual desktop/tablet/mobile browser comparison.
