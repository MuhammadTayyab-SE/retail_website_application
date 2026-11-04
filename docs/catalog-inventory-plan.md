# Catalog and inventory enhancement plan

PM/TL planning only, 2026-11-04 (Asia/Karachi). Baseline: development f0567ea,
including merged Orders PR #53. No application code, schema, stock or orders
changed in this assignment. Existing implementation is extended incrementally;
this is not a new application. GitHub links are listed under Implementation issues.

## Confirmed requirements and decisions

- Parent Category -> Category -> Product remains the taxonomy. Brand is an
  optional independent Product relationship, never a category level.
- Inactive brands disappear from new selections; their existing products remain
  sellable. Editing an existing association must not silently remove it.
- Simple products automatically receive a default sellable variant. Additional
  variants stay optional and collapsed until needed.
- Prices for weighed kg products are per kg; customer increments are 0.1 kg.
  Packaged items retain whole-unit quantities. Existing money is PKR with two
  decimal places and ROUND_HALF_UP; no unit-conversion engine is introduced.
- All products track stock initially. Show the tracking control checked and
  disabled with an explanation; do not add an unused untracked-sales mode.
- Both deactivate and delete remain available. Deletion retains order snapshots,
  stock movement history, archived balances and permanently reserved SKU codes.
- Authorized SKU corrections are allowed before the first order, even after
  opening stock. Retain the old identifier and change history. Once ordered,
  freeze the SKU; legacy product-only order lines count as transactional use.
- Each selected module gets its own route/template and page assets. Do not build
  one HTML page containing every module behind hidden tabs. Shared shell,
  repeated form sections and Python validation/stock operations are reused.
- This assignment stops at documentation and prepared issues. No development,
  merge or deployment is authorized by completion of this plan. Prior QA hold
  remains in effect; future QA scenarios below are requirements, not results.

## Current implementation and gap analysis

| Area | Existing evidence | Required increment |
|---|---|---|
| Categories | Category self-FK, parent flag, cycle protection, effective active visibility, normalized names; Product.category PROTECT | Retain hierarchy; add optional parent selector to filter child category choices, with server validation |
| Brands | No Brand model, permission, form or navigation | Brand name/logo/description/active state, optional Product.brand, associated-products view |
| Variants | Existing ProductVariant has unique normalized SKU, active flag, attributes JSON, optional price and description; photos may target a variant | Extend this model; add default marker, barcode, explicit inventory unit/package content and variant-owned prices; do not create another variant model |
| SKU | Product.sku and ProductVariant.sku each have normalized DB uniqueness; only application checks cross the two namespaces | Durable issuance registry, independent PostgreSQL sequence, overrides with permission/history, no reuse, transactional-use freeze |
| Pricing | Product.price plus percent discount; variants optionally override regular price and inherit product promotion; SQL selling-price annotation used for shop filters/sorting | Nullable historical cost, explicit regular/sale prices and sale active flag per variant; update Python and SQL readers together |
| Stock | Product.quantity is PositiveIntegerField; Add/Edit Product can replace it; +Stock locks and increments it, with stock_received audit but no balance/movement ledger | Variant inventory balance, opening/adjustment/order movements, reserved/available quantities, configurable low-stock threshold |
| Orders | place_order locks products/variants, checks shared Product stock, immediately deducts it once inside the order transaction, and snapshots order lines | Preserve this lifecycle while moving its single deduction into the ledger; never add a second fulfillment deduction |
| Quantities | Cart validation, browser cart state and OrderItem.quantity require integers, including kg products | Coordinated decimal protocol, UI, stock validation, order quantities and receipt/label formatting for 0.1 kg |
| Photos | Multiple uploads, first-position showcase, ordering, removal, format/size validation, configured storage and variant-specific photos already exist | Reuse these components and paths; extend controls to the improved form, not a replacement gallery |
| Admin UI | Existing navy/emerald shell, product form/list, +Stock form, roles and immutable audit history | Separate Brands/Products/Stock Overview/Adjustments/History pages; conditional variants UI; preserve Dashboard, View Catalog, Orders, Team and Settings |
| Featured | Homepage collections exist but Product has no persistent featured flag | Add flag; keep current collections working until their existing merchandising ticket defines how to consume it |

Inspected: catalog models/forms/product_admin/views/product_views/shop_views/shop_forms,
catalog migrations 0001-0011, product/editor/gallery/cart scripts and templates,
checkout services/models/forms/receipts/labels/admin status actions, role permission
choices/audit, and product/shop/storefront/checkout/receipt/order regression sources.
Existing tests cover normalized SKUs, gallery behavior, price sorting, stock
locking, duplicate submissions and overselling; they do not establish the new
inventory/fractional requirements. No test pass is claimed for this planning work.

### Read-only local data evidence

An aggregate-only query in a PostgreSQL READ ONLY transaction found 10 Products,
0 ProductVariants, 17 ProductPhotos, 9 products with positive stock, 7 each-unit
and 3 kg-unit products, 4 active sales and no blank product SKUs. There are 35
OrderItem rows, all without variant references and all retaining live product
references. No customer information or individual product values were exported.
These counts describe this local database only, not other retailer deployments.

Migration 0007 copied an existing variant SKU onto Product, so same-product
Product/Variant aliases can be legitimate in other databases. Migration 0011
already added variant prices/descriptions/photos. Checkout deliberately aggregates
different variant lines against one Product.quantity balance today.

## Proposed database changes

Keep these in catalog and checkout; no new Django app or dependency is needed.
Use one inventory location per independent retailer deployment. No warehouse,
transfer or universal conversion models are needed for this increment.

| Model | Change and invariant |
|---|---|
| Brand (new) | Attributed name, logo, description, active state; normalized unique name using the existing trim/case convention; validated local image upload |
| Product | Nullable Brand FK; featured flag; retain PK/category/legacy SKU/unit/price/quantity columns during expansion and compatibility transition |
| ProductVariant (existing) | is_default with at most one default per product at DB level; required canonical SKU; optional barcode; package-content text (e.g. 500 ml) separate from inventory unit; nonnegative regular price, nullable historical cost/sale price, sale flag; creation service ensures a default exists |
| SkuIdentifier (new) | Permanently unique normalized issued code, issuance metadata and nullable variant owner; retained on variant deletion and code correction; independent non-cycling PostgreSQL numeric sequence, not variant PK |
| InventoryBalance (new) | One current balance per live variant; decimal on_hand/reserved, low-stock threshold, unit/name/SKU snapshots; available is on_hand minus reserved; nonnegative values and reserved <= on_hand; retain an archived row when its variant is deleted |
| StockMovement (new) | Immutable balance reference, signed quantity, type, reason, timestamp, administrator attribution, before/after balances and item/SKU/unit snapshots; nullable order reference plus retained order identifier; unique opening/order/adjustment operation keys |
| OrderItem (existing, later) | Decimal quantity at fractional cutover; preserve integer historical values numerically and existing item/SKU/pricing snapshots; do not rewrite old order amounts or guess variant FKs |

Quantity precision proposed: one decimal place, supporting 0.1 kg; reject
fractions for count units and preserve existing bounds. Package content remains
a simple explicit label, not automatic conversion into stock units. Barcode
uniqueness is not assumed because only optional barcode support was requested.
Costs stay NULL where unknown; zero is a real cost, not a migration placeholder.
Historical sale prices are backfilled using existing rounded effective prices.
Preflight zero-price/active-sale and other constraint exceptions instead of
silently changing prices or promotion state.

SKU allocation uses nextval, never MAX(id)+1. Sequence gaps after rollback are
expected and must not be reclaimed. Seed above existing SKU-number identifiers
and reserve recoverable current, order-snapshot and audit-history codes. Resolve
same-product aliases once; cross-product collisions block migration instead of
renumbering records. A new manual code retires the previous code permanently.
Historical codes deleted before any retained evidence cannot be reconstructed;
that limitation must be disclosed, not replaced by a claim of complete history.

Delete behavior must preserve history without inventing refunds/write-offs:
OrderItem's current SET_NULL relationships remain. Balance.variant becomes null
on deletion, identifying an archived balance retained in inventory history;
movements retain their balance and snapshots, and SKU identifiers remain issued.
Do not silently erase positive stock, create stock adjustments or restore stock
when a product is deleted. Explain retained stock/history on confirmation.

## Safe migration and compatibility strategy

1. Prepare backups of PostgreSQL plus media; record/rehearse restore in a
   disposable database. Capture counts, IDs, SKU ownership, price/stock sums,
   gallery ordering/paths and order relationships before changing anything.
   Reconcile stock by SKU/unit; do not sum kilograms and pieces as one balance.
2. Expand schema first. Preserve old columns and APIs; reuse existing variant
   records and photo IDs. SKU/default backfill needs a short catalog-write pause
   so product creation or SKU edits cannot race the migration.
3. Create default variants for simple products using existing SKUs. Reuse an
   unambiguous matching variant in legacy data. Generate only genuinely missing
   identifiers. Keep existing variant PKs and explicit prices/attributes/photos.
   Ambiguous mappings require a reviewed mapping file, never first-row guesses.
4. Backfill variant pricing with exact effective-price parity and retain unknown
   costs. Switch price readers AND current admin save paths together so there
   is one authoritative price, including SQL sorting/filtering and promotions.
5. Add inventory schema/operations without exposing stale shadow balances. Do
   not copy current stock early while old checkout continues writing Product.
6. In one controlled cutover release, pause checkout/product/stock writes,
   backfill opening balances/movements from current balances, reconcile, then
   switch ALL writers: new-product opening stock, legacy +Stock, product editing
   restrictions and checkout placement. Inventory becomes the single source.
   Read adapters may preserve Product.quantity contracts; never keep two writable
   stock authorities or calculate it by summing unrelated sellable alternatives.
7. For simple products allocate stock once to their default variant. Other
   retailer databases with multiple variants and shared positive stock require
   actual per-variant counts before cutover. Do not duplicate shared stock onto
   each variant or assume all stock belongs to the first variant. This local
   database has no such ambiguous variants, but the migration must detect them.
8. Preserve immediate deduction at successful order placement. Record one sale
   movement in that transaction, keyed to prevent retries/duplicate deductions.
   Reserved starts at zero; do not activate reservation/expiry semantics. Status
   advancement and cash collection continue without additional stock effects.
9. Enable fractional sales only after cart identity/serialization, stock bounds,
   order quantity, receipt, label and all related readers are changed together.
   Accept existing integer cart entries and live-product/live-product:variant
   identities; legacy simple IDs resolve to defaults. Do not clear saved carts.
10. Verify migration idempotency, reconciliation, image presence, old order
    receipts and negative/concurrent scenarios before tightening constraints.
    Retire legacy writable columns only in a separate later reviewed ticket.

Recovery before cutover can revert additive application changes while retaining
new tables/issued identifiers. After ledger writes begin, do not blindly reverse
migrations or rewind the SKU sequence. Pause writes, take a current backup,
reconcile forward or restore DB+media together with an explicit treatment of any
orders accepted since the backup. A versioned migration marker prevents replaying
opening-stock movements. Never reset the retailer database.

## Implementation issues and dependency order

Each implementation gets its own scoped feature branch/worktree and PR targeting
development. Only one starts at a time. Ready is not permission to bypass user
review or the current planning-only assignment. Completed historical #6/#7 are
not reopened; new increments link them. Existing merchandising #42/#45 and
order #12/#13/#52 are referenced without duplicating or claiming their status.

| ID | Increment | Dependency / readiness |
|---|---|---|
| [CINV-01 / #54](https://github.com/MuhammadTayyab-SE/retail_website_application/issues/54) | Brand model, management and optional product association | Ready; brand behavior resolved |
| [CINV-02 / #55](https://github.com/MuhammadTayyab-SE/retail_website_application/issues/55) | Durable SKU issuance and pre-order correction rules | Backlog; foundational, no form rollout until CINV-03 |
| [CINV-03 / #56](https://github.com/MuhammadTayyab-SE/retail_website_application/issues/56) | Extend ProductVariant; default mapping/data migration and legacy cart identity bridge | [CINV-02 / #55](https://github.com/MuhammadTayyab-SE/retail_website_application/issues/55) |
| [CINV-04 / #57](https://github.com/MuhammadTayyab-SE/retail_website_application/issues/57) | Variant-owned cost/regular/sale pricing and compatibility readers/writers | CINV-03; coordinate existing merchandising issues |
| [CINV-05 / #58](https://github.com/MuhammadTayyab-SE/retail_website_application/issues/58) | Inventory balances, movement schema and validated stock operations | CINV-03; staged only, balances not exposed before CINV-06 |
| [CINV-06 / #59](https://github.com/MuhammadTayyab-SE/retail_website_application/issues/59) | Opening-stock migration and single-writer order/stock cutover | CINV-04/05; all stock writers switch together; migration rehearsal required |
| [CINV-07 / #60](https://github.com/MuhammadTayyab-SE/retail_website_application/issues/60) | Stock overview, adjustments and history in admin | [CINV-06 / #59](https://github.com/MuhammadTayyab-SE/retail_website_application/issues/59) |
| [CINV-08 / #61](https://github.com/MuhammadTayyab-SE/retail_website_application/issues/61) | 0.1 kg quantity support across cart, order, receipts and labels | CINV-04/06; no lifecycle/reservation change |
| [CINV-09 / #62](https://github.com/MuhammadTayyab-SE/retail_website_application/issues/62) | Modular Add/Edit Product form, variants, parent filter, existing gallery | CINV-01/04/06/07/08; initial stock only on create |
| [CINV-10 / #63](https://github.com/MuhammadTayyab-SE/retail_website_application/issues/63) | Catalog/Inventory navigation and module-only assets/templates | CINV-01/07/09; preserve existing routes and Orders placement |
| [CINV-11 / #64](https://github.com/MuhammadTayyab-SE/retail_website_application/issues/64) | Independent integration, concurrency, migration/recovery and responsive regression | All above; QA execution awaits authorization |

Reservations, expiry, cancellations/refunds/restocking and supplier/purchase
accounting are excluded. Their lifecycle rules require separate user decisions.
Migration failures/collisions/shared-stock exceptions are operational preflight
gates, not permission to invent stock allocations or rewrite history.

## Acceptance and QA expectations

- Brand names normalize consistently; duplicate/racing creates cannot persist;
  inactive associations do not remove products; unbranded products still work.
- Default variants and SKU issuance survive retries/concurrent creates without
  duplicate IDs/codes; codes are never derived from mutable names or reused after
  deletion/correction. Editing after the first order is rejected server-side.
- Price cutover preserves Python/SQL effective prices and money rounding;
  invalid/negative prices and non-lower active sale prices fail clearly. Cost
  data never enters public product/cart/receipt responses.
- Opening stock occurs once; adjustments require reasons/permissions; checkout,
  receive-stock and adjustments contend safely under locks; insufficient stock,
  failures and duplicate submissions leave consistent balances and movements.
- Customer weight steps 0.1/0.3/1.2 kg price correctly; 0.05 kg, fractional count
  units, booleans, NaN/infinity, excess precision and overflow fail without writes.
  Existing whole-number saved carts and orders still work.
- Product deletion retains immutable orders/stock/SKU history and archived
  balances; deactivation stops sales without erasing data; deleting/replacing
  images still follows successful-commit cleanup and storage validation.
- Admin tests cover role grants/revocation, direct URLs, CSRF, double submission,
  stale state, read-only controls and concurrent mutations, not just HTTP 200.
- Each module request renders its own templates and assets, with no hidden
  unrelated module panels. Desktop/tablet/mobile widths around 1440/768/390 px
  require keyboard/error/empty/gallery/filter checks and screenshots when QA is
  resumed. Existing navy/emerald components are the visual reference.
- Rehearse migrations on disposable legacy fixtures and a sanitized schema/data
  copy; compare IDs, amounts, quantity totals, SKU aliases, media paths and order
  snapshots before/after. Test ambiguous legacy cases and failed/repeated runs.
- PM review and independent QA use the exact candidate SHA; developer checks do
  not replace either. No test or visual verification is claimed by this plan.
