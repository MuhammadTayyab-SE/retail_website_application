# CINV-01 - Brand management and product association

Issue [#54](https://github.com/MuhammadTayyab-SE/retail_website_application/issues/54).
Baseline development f0567ea; implementation branch feature/cinv-01-brands in
catalog-brands-work. User explicitly started this issue on 2026-11-04.
Planning reference: draft PR #65 and decisions CINV-D1/D2/D7. In Development;
developer implementation exists, independent review/browser QA remain pending.
No other CINV increment is included and no merge/deployment is performed.

## Scope and structure

- Brand extends AttributedModel with name, optional logo, description and active
  state. Trim/case validation and a normalized PostgreSQL unique constraint
  prevent duplicate names, including concurrent inserts.
- Product.brand is nullable with PROTECT. Existing products remain unbranded;
  existing product/category/variant IDs, prices, stock and photos are unchanged.
  Active brands are selectable; an inactive brand can remain on its current
  product but cannot be newly assigned, including through model validation.
  Brand deactivation does not cascade product visibility or activity.
- BrandAdmin reuses native Django search/status filter/pagination and the existing
  navy/emerald admin shell. Its separate list/form templates load only brands.css,
  with no new JavaScript or dependencies. The existing catalog navigation now
  includes Brands and a Catalog Management heading. Full stock-navigation
  restructuring remains CINV-10.
- Associated product counts are annotated in the list. Users with product view
  permission receive a link to the existing filtered, paginated Products list;
  others see counts. The product form gains the optional brand field and its
  existing toolbar gains a brand filter, retaining current URLs/gallery behavior.
- Shared upload validation replaces the duplicated category/product checks:
  JPEG/PNG/WebP up to 8 MB, canonical extension and UUID storage paths. Brand
  logos use the configured MEDIA_ROOT under brands/. An authenticated, safe-method
  logo endpoint checks brand access and uses nosniff/private no-cache responses.
- Existing roles expose view/add/change brand permissions. Brand deletion is not
  part of this issue; use deactivation. No worker/auth management powers are added.
  Brand fields and product associations reuse immutable audit and attribution.
- Brand update requests lock the current row before binding file fields so
  concurrent HTTP edits cannot write back a deleted stale logo reference. Old
  logos are deleted only after successful commit when replaced/cleared. As with
  existing file uploads, an outer transaction rollback can leave an unreferenced
  new upload; no orphan-media sweeper is introduced here.

## Schema, setup and recovery

Migration catalog.0012_brand_management adds only Brand, Product.brand and the
brand constraints. No backfill or alteration of existing business values.

```powershell
.venv\Scripts\python.exe manage.py migrate catalog --noinput
.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8001 --noreload
```

The feature worktree has its installed locked environment and ignored local .env.
MEDIA_ROOT points to the development checkout's existing media, so previous
product/category images remain available. Developer checks use a distinct
test_cinv01_brands database and temporary synthetic media, not the dev data.

At setup the local development database already recorded 0012 as applied; no
pending migration was executed. Reconciliation hashes before/after the setup
check matched for 10 products, 17 photos and 35 order lines (no customer data
exported). Feature preview is on port 8001; the original checkout remains on
development. A migration test exercises forward and reverse operations against
legacy fixtures in the disposable database, preserving product IDs/SKU/price/
quantity and image paths. Reversing removes NEW brand data/associations, so export
and back up any entered brands/logos before a rollback; never reset the database.

## Developer verification and remaining gates

- Brand regression sources cover normalized/concurrent duplicates, optional and
  inactive associations, logo formats/size/clear/replacement/rollback, attribution,
  permissions/CSRF, status/search/product filters, pagination, assets and migration.
- Affected Django run: 142 tests, 139 passed and three storefront failures.
  The same three failures were reproduced on unchanged development f0567ea using
  separate test_cinv01_baseline: two old homepage query budgets (17/18 queries
  versus 12) and an old expected "50% off" string. No unrelated storefront fix
  is included. Detailed commands: tests.test_brands, test_products, test_categories,
  test_roles_audit, test_checkout, test_storefront, test_shop, test_product_detail,
  test_receipts via manage.py test --noinput --verbosity 1.
- Django system check and migration drift check pass. Ruff lint passes for catalog,
  access, config and the new tests; changed Python files pass formatting; diff
  whitespace check passes. The existing untouched catalog migration 0011 fails
  the wider format check; it is intentionally not reformatted in this issue.
- Preview setup HTTP checks reached health, the login-protected brand route and
  brand CSS. Redirect-following login HTTP 200 is not a claim that an authenticated
  brand screen has been visually checked.
- Developer tests are not independent QA. Browser interactions, desktop/tablet/
  mobile screenshots, visual comparison and independent PM review remain pending.
  Do not advance to Awaiting My Review or Done based on these checks alone.
- Final focused command `manage.py test tests.test_brands --noinput --verbosity 1`
  passes all 12 brand checks after the last change. No application changes were
  made after that pass other than documentation.
