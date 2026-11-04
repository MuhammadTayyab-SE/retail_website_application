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
- BrandAdmin reuses native Django search/status filtering/pagination and the existing
  navy/emerald admin shell. Its separate list/form templates load brands.css;
  only Add/Edit loads the small brands.js photo preview. No new dependencies.
  The existing catalog navigation now
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
- The initial implementation passed 12 focused brand checks. The following UI
  revision expands that coverage; the wider 142-test result above predates it.

## Reference-driven UI revision (2026-11-04)

Approved source: `supporting docs/Templated/products/retail-admin-preview - varients.html`,
Brands section, plus the user's explicit request to keep creation on Add brand.
The reference's name/logo row, full-width description, active control, white card
and emerald action inform the form; demo data and demo JavaScript are not used.

- Main Brands page contains only the list and Add brand link. Search and status
  move to a labeled top toolbar, with a submit button and conditional Clear filters
  link. Native Django filtering and 25-row pagination remain in use. The default
  right filter sidebar and its forced 400px minimum height are removed for Brands.
- Logo and name sit together, with aligned status badges, linked product counts
  and Edit (or View for read-only staff). A fallback initial handles missing logos.
  The table can scroll horizontally on narrow screens; toolbar/form fields stack
  at 760px/560px. Styling stays scoped to Brands and loads after the admin shell;
  CSS URL v3 avoids stale cached assets. No global styling changes.
- Separate Add/Edit pages share brand_editor and brand_field partials. Saved logos
  are shown using the authenticated endpoint. Selected photos preview immediately;
  replacing/removing a selection revokes its object URL. File persistence,
  validation, CSRF, attribution and permissions still use the existing BrandForm
  and ModelAdmin. Read-only staff see the saved image without editing controls.
- Developer checks: all 15 `tests.test_brands` checks pass, including combined
  search/status retention, separate list/add routes, existing/read-only photos,
  duplicate errors and submitted text. `node --test tests/test_brand_photo_ui.cjs`
  passes 2 selected/replaced/cleared-photo checks. Scoped Ruff lint/format and
  `git diff --check` pass. The later CSS-only logo flex sizing adjustment does not
  change tested logic.
- Restarted only this feature's own `--noreload` preview on port 8001. The final
  `brands.css?v=3` returns HTTP 200 with the new toolbar styles. Port 8000 was not
  restarted. Browser connection reported "The browser access host is unavailable";
  authenticated visual comparison, responsive screenshots and manual interaction
  checks are therefore unverified. Independent QA remains paused as requested.
  No visual signoff or workflow advance is claimed.
