# Catalog and inventory MVP plan

PM review and backlog revision, 2026-11-04 (Asia/Karachi). Reviewed development
**88c7536**, including merged planning PR #65, Brand PR #66 and SKU PR #67.
This revision supersedes the earlier requirement to preserve disposable catalog
and transaction data. It changes documentation/tickets only, not application
code, migrations, files in media storage or database contents.

## 1. What is implemented and integrated

Both GitHub issues and their original acceptance criteria were read, then compared
with the actual merged code and tests. Closed issues alone were not taken as proof.

| Completed scope | Actual evidence in development | Assessment / remaining boundary |
|---|---|---|
| CINV-01 / #54: independent Brand | `catalog/models.py` Brand and optional Product.brand; migration 0012; `brand_admin.py`, BrandForm, separate list/add/edit templates and scoped CSS/preview JS | Name constraints, inactive-selection rules, linked products, uploads/cleanup, permissions, CSRF and audit are implemented. Retain them; no new Brand model/page is needed. |
| CINV-02 / #55: durable SKU issuance | SkuIdentifier, `catalog/skus.py`, migration 0013 and `_sku_registry_sql.py`, `check_skus`, ProductAdmin locking and override permission | Registry, independent sequence, reservation/history/deletion rules, concurrency, overrides and first-order freeze are implemented. Retain them; variant-only ownership and automatic creation integration remain #56's work. |
| Existing variants | ProductVariant with required normalized SKU, optional price/description, attributes and activity | Extend this model. It has no default marker, barcode or explicit inventory unit/package fields yet; prices still inherit Product promotion. |
| Existing gallery | ProductPhoto, upload validation/storage/cleanup, picker/previews, individual removal, position controls and Make showcase | Reuse the implementation. Variant FK is optional; Product FK owns the admin inline; the first image is the product-wide showcase. PhotoInline does not expose variant assignment. This is not complete per-variant gallery management. |
| Existing checkout/admin | Product/variant row locks, quote validation, atomic placement and shared Product.quantity deduction; order snapshots, receipts/PDFs, labels, fulfillment, cash collection/notes and roles/audit | Preserve functionality, routes and access rules while updating its data sources. Do not rebuild checkout or Orders. |

### Acceptance coverage for completed tickets

- **CINV-01:** all five original acceptance areas have implementation: normalized
  name constraints; optional/inactive associations; validated logos and commit-safe
  cleanup; independent taxonomy and authorization; dedicated route/templates/nav.
  `tests/test_brands.py` has 15 tests spanning those rules, permission/CSRF,
  concurrency, linked lists and migration. Two Node photo-preview checks also exist.
- **CINV-02:** all six original areas have implementation: independent formatted
  sequence; recoverable-code reservation/conflict preflight; permanent issued
  history; permissioned actor/time corrections and order lock; no renumbering;
  retained owners/history after deletion. `tests/test_skus.py` has 20 checks,
  including real competing admin POSTs and order/correction contention.
- **Important integration boundary:** Product.sku and ProductVariant.sku still
  coexist behind alias-sync guards; `assign_sku` currently accepts saved records.
  ProductForm still requires a manual SKU. Automatic default creation and an
  add-only worker's generated SKU flow are not delivered by #55. #56 must extend
  the existing allocation path and retire the Product SKU authority/alias bridge.
- These are source/merge findings, not fresh test or independent QA results. Prior
  developer evidence reports 15 Brand and 20 SKU passes. The prior full run had
  five baseline failures (two storefront query budgets, two old UI strings and
  an Orders multipart `pieces=None` fixture). #64 must disposition them on its
  actual candidate, not call that suite green or automatically rewrite assertions.

## 2. What remains incomplete

1. Atomic default-variant creation, barcode and explicit unit/package metadata;
   one canonical variant SKU source using the completed registry.
2. Required variant-owned photos with independent primary selection per variant;
   remove/reorder/upload operations scoped and authorized to that variant.
3. Explicit variant cost/regular/sale prices and all public/admin price readers.
4. Variant inventory balances, immutable movements, create-only opening stock,
   adjustments, low-stock status and one checkout deduction path.
5. Exact 0.1 kg cart/order/output quantities; whole counts for packaged units.
6. The required four-tab Add/Edit workflow. The current template is a details
   fieldset plus product-wide uploader, not these four tabs. The user instruction
   is authoritative over the older five-section ticket description.
7. Stock overview/history screens and final sidebar grouping; do not duplicate
   completed Brand navigation, shell, themed scrolling or Orders placement.

## 3. Approved MVP data policy and safety gate

- Existing development/test products, variants, identifiers, inventory and test
  transactions may be discarded and recreated **after separate explicit approval**.
  This statement is not approval to execute a reset, purge, truncate, flush,
  sequence restart, destructive schema migration or automated cleanup now.
- Do not reset shared, staging or production databases. The previously used local
  `pg_retail_dev` is shared by worktrees and is **not an approved reset target**.
  No target environment is selected/confirmed by this planning review.
- Prefer a dedicated, confirmed isolated development/test environment. Before any
  destructive action, present its environment, host/port, DB name, ownership/use,
  exact tables/rows/schema/media/sequence scope, dependencies, expected counts,
  preserved records and recovery plan; obtain explicit approval for that action.
  Test-runner create/drop/flush operations must be covered by that scoped approval.
- Preserve application code and completed functionality. Exclude unrelated users,
  roles, categories, Brands, retailer/delivery settings, audit records and unrelated
  uploads unless separately identified as disposable and explicitly approved.
  Do not treat "other disposable records" as blanket permission to remove them.
- No reset command, automatic data purge or database operation is implemented here.
  If new constraints encounter incompatible data, stop and request the scoped
  operation; do not hide destructive cleanup inside a migration or post_migrate.
- Keep committed migration history reproducible. Leave 0001-0013 intact; use forward
  schema/guard migrations. Fresh install must run the whole chain. No migration
  fake/reset, deletion of migration records or unreviewed squash is planned.
- Remove future legacy backfills, alias mapping files, shared-stock apportionment
  and old-cart compatibility as acceptance requirements. New synthetic fixtures
  express the new model directly. This does not authorize breaking completed
  routes or leaving two writable SKU/price/stock authorities in the running app.
- CINV-02's normal lifecycle rule still reserves issued codes after correction or
  deletion. Any disposable-environment reinitialization that includes the registry
  or counter needs its own explicit scope/approval; never rewind them incidentally.

## 4. Clean target schema and responsibilities

Reuse catalog/checkout/access and existing services; no new app/framework or
generic repository, migration engine, wizard engine or conversion service.

| Model | Required change / owning ticket |
|---|---|
| Brand / Product.brand | Already implemented; retain and regression-test (#54). |
| Product | Product identity/category/optional Brand/description/activity plus featured flag. Retire product-level SKU/unit (#56), price/promotion authority (#57) and quantity authority (#59), with all callers switched in their owning release. |
| ProductVariant | Extend existing model with `is_default`, optional barcode, inventory unit and separate package-content label (#56); canonical SKU uses #55. Partial unique default constraint plus an atomic creation/save path ensures one default on creation and prevents losing it. No second variant table. |
| ProductVariant pricing | Explicit nonnegative regular price; nullable cost (unknown is not zero); nullable sale price and sale-active flag with valid lower active sale price (#57). Rename/extend the existing variant price field rather than add parallel writable price columns. |
| ProductPhoto | Reuse this table/file pipeline. Require variant FK, use variant-owned deletion/cleanup, retire redundant product FK, retain alt text/position and add `is_primary` (#56). DB allows at most one primary per variant; locked save operations ensure one if photos exist. No cross-variant attachment/reorder/primary changes. Images remain optional. |
| SkuIdentifier / sequence | Already implemented (#55). Keep reservations/sequence/audit and refactor only obsolete Product-column/alias dependencies through forward migrations (#56). Do not replace the registry or introduce a second allocator. |
| InventoryBalance | New one-to-one live variant balance, decimal on_hand/reserved and configurable threshold; available is derived; nonnegative and reserved <= on_hand; identity/unit snapshots and archived retention (#58). |
| StockMovement | New immutable opening/adjustment/order movement with signed amount, reason, actor/time, before/after values, variant/SKU/unit snapshots and unique operation key (#58). No generic editable ledger admin. |
| OrderItem | Continue snapshots and authorized lookup. New writes use the selected variant; decimal quantity and consistent serializers/formatting land in #61. Test records may be recreated after approval; no historical quantity-conversion/backfill engine. |

Default uniqueness alone is not proof every Product has a default. The atomic
creation path and validation must cover create, edit/default change, removal and
concurrent submissions. Generated creation must honor add_product permission
without requiring a manual override/change grant; manual overrides retain #55 rules.

### Application integration ownership

- **#56 identity/photos:** update existing model/form/admin save paths, SKU display
  and image readers, ProductPhoto formsets and CINV-02 SQL helpers/guards when
  dropping Product.sku/ProductPhoto.product. Bind images to the real default or
  selected variant in the same atomic save. Reuse the current gallery components;
  do not leave completed product creation broken until the four-tab visual pass.
- **#57 prices:** move homepage/shop SQL sorting/filtering, product detail, cart,
  quotes/place, admin, receipts and labels to the same variant pricing rules.
  Cost is private. Card presentation must have a defined default/selected variant.
- **#58/#59 stock:** stage the ledger foundation then switch every writer together:
  new-variant opening, edit restrictions, existing +Stock, adjustments and checkout.
  Multiple variants require explicit selection; never duplicate shared stock or
  aggregate unrelated variants into a writable Product quantity. Opening records
  reflect newly entered stock, not fabricated legacy sales/migration history.
- Preserve immediate, once-only deduction at successful placement. Fulfillment
  and cash collection do not deduct again. Reserved remains zero; cancellations,
  returns, refunds, expiry and reservation lifecycles are not added by this plan.
- **#61 quantities:** canonical variant line identity and bounded decimal protocol.
  Disposable legacy carts can be clearly invalidated/versioned; reject stale IDs
  with a useful message rather than infer old product/variant mappings. Current
  cart ownership, server pricing, idempotency and privacy remain required.

## 5. Product UI: exactly four tabs

| Tab | Responsibility |
|---|---|
| Basic Info | Product name, description, independent optional Brand, parent selector/category validation. |
| Variants | Default variant without extra setup; optional additional variants; generated/authorized SKU, barcode, unit/package and cost/regular/sale fields. |
| Photos | Selected variant's multi-image gallery; upload, preview, remove individual images, reorder and choose its primary image. A single-default product opens its gallery directly. |
| Availability | Product/variant active state and featured flag; checked/disabled stock tracking, per-variant opening stock on create, thresholds and links to authorized adjustments on edit. |

Use four reusable partials and existing Django form/formset/gallery code. Load a
tab's additional markup/assets when selected, retain unsaved input across switches
and submit one server-validated atomic operation. Do not create persisted draft
orders/products or a generic wizard solely to implement tabs. Errors must identify
and open the affected tab. Preserve keyboard/focus and read-only roles. Dedicated
Brands/Products/Stock/Orders pages remain separate modules; no hidden unrelated
module screens. #62 owns UI composition, not duplicate schema/stock/SKU logic.

## 6. Updated existing tickets, overlaps and order

| Ticket | State | Dependencies | Revised ownership / removed duplication |
|---|---|---|---|
| CINV-01 / #54 | Done (merged #66) | Baseline | Keep Brand model/pages/permissions/uploads; later tasks only integrate them. |
| CINV-02 / #55 | Done (merged #67) | Baseline | Keep allocator/registry/sequence/history; #56 replaces only legacy Product alias coupling. |
| CINV-03 / #56 | In Development (user started 2026-11-05) | #54, #55 | Variant identity/defaults, variant-specific photo schema/operations and necessary current-route integration. Remove legacy mapping/backfill/cart bridge scope. |
| CINV-04 / #57 | Backlog | #56 | Variant price authority and all readers/writers; remove old-price parity/backfill requirements. |
| CINV-05 / #58 | Backlog | #56 | Balance/movement foundation and validated operations; no copied disposable stock. |
| CINV-06 / #59 | Backlog | #57, #58 | New opening stock and single-writer checkout/admin integration; remove legacy shared-stock allocation/reconciliation. |
| CINV-07 / #60 | Backlog | #59 | Stock screens use #58/59 operations and existing shell; no second +Stock writer. |
| CINV-08 / #61 | Backlog | #57, #59 | Decimal quantity protocol and outputs; replace old-cart/history preservation with clear stale-cart handling and fresh fixtures. |
| CINV-09 / #62 | Backlog | #54, #56, #57, #59, #60, #61 | Four-tab composition; reuse Brand/SKU/gallery/ledger operations, replacing the old five-section scope. |
| CINV-10 / #63 | Backlog | #54, #60, #62 | Finish navigation/asset isolation; do not recreate Brand links, sidebar scroll or module views. |
| CINV-11 / #64 | Backlog | #54-#63 | Fresh-install/forward-migration/integration QA and regression; replace legacy data-parity testing with approved target/scope isolation and synthetic fixtures. |

Recommended single-ticket order: **03 -> 04 -> 05 -> 06 -> 07 -> 08 -> 09 -> 10 -> 11**.
04/05 share dependency 03; 07/08 follow stock integration. This is an ordering,
not permission to claim multiple tasks or start implementation in this review.
No extra feature ticket is needed merely to repeat completed Brand/SKU work.

## 7. Integration tests required

| Area | Required evidence on the new candidate |
|---|---|
| Existing foundations | Brand optional/inactive/permissions/logo/audit regressions; SKU allocation, no reuse, override/revocation, history and first-order lock after variant-only refactor. |
| Schema/install | Entire migration chain on an approved fresh disposable PostgreSQL target; forward removal of old trigger/column dependencies; DB constraints and seed fixtures; no hidden destructive hooks, registry rewind or unrelated-table/media deletion. |
| Product creation | Simple product atomically creates its one default and SKU; multiple variants/default switching; add-only worker auto-generation; duplicate submission, invalid fields, rollback and concurrent default/SKU changes. |
| Variant photos | Multiple uploads per variant, isolated ordering and primary selection, at most one DB primary and a selected primary when nonempty, primary removal/reselection, empty gallery, cross-product/variant forged IDs, role/CSRF, replacement rollback and commit-safe cleanup; card/detail/cart image matches selected/default variant. |
| Pricing | Decimal Python/SQL parity, filters/sort, invalid sales, rounding, promotion presentation and no cost leakage in any public HTML/JSON/receipt. |
| Stock/order | Exactly one opening/deduction per operation; adjustment reason/permissions; rollback; checkout versus adjustment/receipt/correction; competing last item, retry/idempotency and fulfillment/payment without second deduction. |
| Quantities | 0.1/0.3/1.2 kg; reject 0.05 kg, fractional counts, bool/NaN/infinity, overflow; correct line rounding, stock bounds and HTML/PDF receipt/label/admin quantities. |
| UI/modules | Four tabs, state/error navigation and simple-default experience; per-variant gallery; keyboard/read-only roles; roughly 1440/768/390px; module/tab assets and existing Orders/Settings/Catalog/navigation regression. |

Existing tests also encode superseded contracts: Product creation currently
asserts no variants, gallery showcase is position zero for the whole product,
SKU tests exercise a Product/Variant alias, and Checkout tests aggregate variant
lines against one Product quantity. Their owning tickets must replace those
assertions with automatic defaults, per-variant galleries, canonical variant SKU
and independent variant balances, while retaining permissions/atomicity coverage.
Historical migration tests should use the historical model state; they must not
force current models to keep retired fields. Do not delete entire suites or
silently weaken unaffected assertions to obtain a green result.

No application/QA test execution or database connection was needed for this
documentation review. Test counts above are prior developer evidence/source
coverage, not rerun results. QA resumes through an approved handoff/environment;
this review does not silently lift the previous execution hold.

## 8. PM -> Developer -> QA -> My Review

PM establishes this updated backlog and makes #56 Ready, without a developer claim.
The next Developer claims only that Ready ticket, prepares concrete forward schema
changes and any required target-specific destructive proposal, then implements on
an isolated branch and opens a draft PR. PM reviews the actual candidate and QA
plans/executes authorized checks against that exact SHA in an approved isolated
environment. Defects return to the same ticket; every new commit renews affected
checks/review. My Review follows evidence and disclosed limitations; merge and
deployment still require explicit approval. This assignment stops at the updated
plan/tickets. **No additional application feature or destructive operation starts.**

Implementation progress 2026-11-05: the user started #56. It is In Development on feature/cinv-03-variants; database/migration/test execution awaits scoped approval. No other CINV increment was started. See docs/tickets/CINV-03.md.
