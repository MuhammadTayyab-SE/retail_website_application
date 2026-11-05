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
  instead of backfilling/purging records. Keep 0001-0013 intact. Database operations
  use only the explicitly approved isolated targets below.

## Approved isolated environment

On 2026-11-05 the user approved the concrete local proposal with “Approve this
isolated scope”: PostgreSQL 18.6 on loopback, port 5432; new non-superuser login
retail_cinv03, new empty retail_cinv03_dev, and repeated developer-test
create/migrate/drop of test_cinv03_variants plus its synthetic test media.
Server identity and unused role/database names were rechecked before creation.
The role has CREATEDB for Django tests, no superuser/create-role/replication rights;
its generated credentials are only in ignored local configuration.

The fresh development database was created and the complete retained migration
chain through catalog.0014 applied successfully. It is kept for review, with one
synthetic product, two variants and three synthetic images in
catalog-variants-work/.local/media. No existing database, upload folder or unrelated
record was reset, migrated or copied. Shared pg_retail_dev is excluded. This scoped
approval does not authorize schema changes against any other database.

## Verification planned

Automatic/add-only creation, default switching/removal/concurrency, SKU override/
freeze/history/no-reuse, barcode/unit/package validation, per-variant gallery
multi-upload/primary/reorder/removal/forged IDs, rollback and media cleanup,
existing catalog/checkout/receipt/label routes, schema chain and permissions.
Browser comparison is against the supplied variant cards within existing admin
design. Developer checks are not independent QA; prior QA execution hold remains.

## Current implementation

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

Developer integration found and corrected form constraint validation during
default/primary replacement, the primary-photo demotion save order, stable
attribute-label ordering, the existing failed-upload explanation and remaining
synthetic fixtures using removed Product/photo fields. Homepage galleries are
prefetched once across collections instead of separately for every collection.

## Developer evidence

Implementation commit: 52a2959faa63c573476ee31318c97b9ec53c1b88. These are developer
checks, not independent PM review or QA. Python 3.13.14, Django 5.2.18, PostgreSQL
18.6; commands use this checkout's .venv/Scripts/python.exe and ignored isolated
configuration. Tests create and destroy only test_cinv03_variants.

- `manage.py migrate --noinput`: complete fresh chain passes, including 0014 SQL.
- `manage.py check`: no issues; `manage.py makemigrations --check --dry-run`: no
  changes. `manage.py check_skus` passes on the empty schema and again with the two
  synthetic preview variants/reservations.
- `manage.py test tests.test_variants tests.test_variant_migrations
  tests.test_products tests.test_product_detail --noinput --verbosity 1`: 68 pass.
  Covers generated/add-only creation, permissions, default change/removal and
  competing writes, SKU history, scoped IDs, primary/order/removal in one save,
  double-primary rejection, rollback, schema forward/reverse and populated-target
  rejection. Existing SKU/checkout/order suites also ran in the full regression.
- `manage.py test --noinput --verbosity 1` on the implementation commit: 289 run,
  284 pass, four failures and one error. These match the five baseline failures
  already recorded in docs/catalog-inventory-plan.md; the suite is not green:

  | Existing failure | Current result |
  | --- | --- |
  | Storefront pagination and sale query budgets (two tests) | 15 queries each against a budget of 12; collection batching reduces the pre-fix branch's 21/23 |
  | Storefront discount text | Test expects “50% off”; existing badge renders “-50%” |
  | Orders detail text | Test expects “Customer &amp; contact”; existing page uses another heading |
  | Orders address correction fixture | Multipart encoding rejects existing `pieces=None` before the request reaches the view |

  These assertions were retained; no unrelated Orders behavior or baseline budget
  was rewritten to obtain a green result. Disposition remains CINV-11/#64.
- Scoped Ruff lint and changed Python format checks pass. Python source parsing,
  Node product-script syntax and four product/variant template compilations passed
  during preparation; `git diff --check` passes.
- Loopback HTTP developer smoke: /health/, /admin/login/, /shop/ and
  /shop/product/1/ return 200; product response includes both synthetic variants.

Browser inventory reports “The browser access host is unavailable”. Native Chrome
selection then stopped Computer Use because it could not determine the current URL
confidently enough to enforce policy. No further browser input was attempted.
Authenticated visual comparison, upload/reorder interactions and desktop/tablet/
mobile viewports (1440/768/390) remain unverified; no screenshot evidence is claimed.
The local review server uses 127.0.0.1:8002; synthetic login details are in ignored
.local/review-login.txt. This preview uses no existing customer records or uploads.

Status remains In Development; draft PR #69. Independent QA stays paused as the
user requested. Required next gates: independent PM review, restored browser
verification, authorized exact-SHA QA, baseline-failure disposition in CINV-11/#64,
then My Review. No merge/deployment.
