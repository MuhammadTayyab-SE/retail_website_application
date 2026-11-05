# Decision register

## Current MVP strategy revision - 2026-11-04

Reviewed against development 88c7536 and issues #54-#64. The user's latest strategy
supersedes earlier disposable-data preservation/backfill instructions below;
completed application functionality and unrelated data remain protected.

| ID | Status | Decision | Consequence |
|---|---|---|---|
| CINV-D8 | Agreed user instruction | Development/test catalog, identifiers, stock and test transactions may be recreated; clean architecture takes priority over compatibility with disposable records | Remove future legacy mapping, price/stock backfills and old-cart bridges from #56-#64. This is not permission to perform a destructive operation. |
| CINV-D9 | Mandatory user approval gate | Confirm environment and exact scope before any destructive DB/schema/data action; obtain separate explicit approval. Never reset shared/staging/production DBs or remove unrelated development data | No target is approved by this planning pass. Keep migration history coherent; no automatic purge/reset hooks, sequence rewind or broad flush. Test-runner destruction needs approved isolated scope too. |
| CINV-D10 | Agreed user instruction | Reuse merged Brand and SKU implementations; retain four product tabs: Basic Info, Variants, Photos, Availability | #56 integrates default creation/variant ownership using existing foundations; #62 composes the four-tab UI rather than recreate models/services. |
| CINV-D11 | Agreed user instruction; technical constraint chosen by PM | Every photo belongs to one variant, with multiple images, ordering and a selected primary per variant | Reuse ProductPhoto/upload/gallery code; required variant FK, no redundant product owner, per-variant primary uniqueness and locked validation. Schema/operations #56; UI #62. |

Normal-operation no-reuse SKU and immutable stock/order/audit rules stay in force.
Any disposable reset including issued-history/sequence requires explicit scope.
The plan/tickets document completion evidence and boundaries; they do not claim
fresh independent QA. This review starts no additional application implementation.

## Catalog/inventory decisions - 2026-11-04

These current user decisions supersede the earlier single-unit/product-owned-SKU
restriction for this new increment; historical entries remain below. Planning
and migration detail: [catalog-inventory-plan.md](catalog-inventory-plan.md).

| ID | Status | Decision | Consequence |
|---|---|---|---|
| CINV-D1 | Agreed | Extend existing variants; simple products get automatic defaults; Brand is independent and optional | No replacement application or taxonomy level; preserve current IDs/data |
| CINV-D2 | Agreed user reply | Inactive brands leave products sellable but cannot be newly selected | No product visibility cascade; retain current associations on edit |
| CINV-D3 | Agreed user reply | Kg price is per kg; customers buy in 0.1 kg (100 gram) steps | Decimal change must reach cart/order/receipts/labels and stock together |
| CINV-D4 | Agreed user reply | Keep untracked-inventory option unavailable initially | All stock is tracked; no unused unlimited-sales mode |
| CINV-D5 | Agreed user reply plus required history preservation | Keep both deactivate and delete options | Retain archived balances, movement/order snapshots and issued SKU identifiers after deletion; no silent stock write-off |
| CINV-D6 | Agreed user reply | Lock SKU only after first accepted order; earlier corrections retain history | Opening stock alone does not freeze a SKU; retired codes remain unavailable |
| CINV-D7 | Agreed later user instruction | Only load selected module HTML/assets; reuse useful components and logic | Dedicated routes/templates, no monolithic hidden module page or new framework |

Immediate stock deduction at placement is existing behavior to preserve, not an
approval for reservation, expiry, cancellation, refund or restocking semantics.
The earlier historical-cost/SKU/shared-stock preservation strategy is superseded
for disposable MVP records by D8-D11 above. Never manufacture operational stock
or perform an unapproved destructive reset. Previously committed migrations and
the completed Brand/SKU functionality are retained.

Statuses: Agreed, Proposed, Unresolved. "Agreed current scope" records a settled local choice; "production deferred" and "cloud deferred" preserve future decisions without blocking local implementation. PM owns this register; record date, user answer and consequences when resolving an entry. Current date: 2026-10-10.

| ID | Status | Decision / question | Impact / blocking tickets |
|---|---|---|---|
| D-001 | Agreed | Adopt Django and PostgreSQL: inspection found no existing application to constrain adoption. Adopted by PM as the technical baseline; no existing code requires migration. | MVP-001 |
| D-002 | Agreed current scope; production deferred | Run and test locally now. Production hosting provider, OS, rollout, retention and recovery objectives are deferred. | Local MVP-002, MVP-014; production follow-up |
| D-003 | Agreed current scope; cloud deferred | Local filesystem media now with configurable storage and distinct retailer/test media roots, gitignored. Cloud storage is deferred. Upload format/size limits remain a technical follow-up requiring explicit implementation review. | MVP-002, MVP-005 |
| D-004 | Superseded by user 2026-10-11 | Super Admin manages worker accounts, one role per worker, and module/action permissions. Workers have only role access. Activity is audited; categories/products retain authorship. Passwords remain hashed; Super Admin resets rather than views them. See docs/tickets/MVP-003-roles-audit.md. | MVP-003; MVP-004; MVP-005 |
| D-005 | Categories agreed; product rules unresolved | User confirmed parent/subcategories and deactivate-only categories on 2026-10-10. Names globally unique ignoring case/outer whitespace; nonnegative sibling ordering; inactive ancestors hide descendants. SKU rules, units/weights, variants, product deletion/archive and imports remain unresolved. | MVP-004 category scope; MVP-005 product rules |
| D-006 | Unresolved | Who supplies product photos/content and what image formats, size limits and rights apply? | MVP-005 |
| D-007 | Unresolved | Currency PKR agreed by user. Launch country, tax-inclusive/exclusive pricing, rounding and invoice requirements remain unresolved. | MVP-006, MVP-008 |
| D-008 | Unresolved | Stock units, reservations, backorders, substitutions, overselling, expiry and audit expectations? | MVP-006 |
| D-009 | Unresolved | Approved Zilly-inspired direction, branding assets, languages/RTL and responsive/accessibility target? | MVP-007, MVP-009 |
| D-010 | Unresolved | Guest checkout, customer accounts, cart persistence and authorized order lookup mechanism? | MVP-008, MVP-011, MVP-013 |
| D-011 | Unresolved | Delivery zones/address validation, pickup, fees, minimums, slots, cutoffs and capacity? | MVP-010 |
| D-012 | Unresolved | MVP payment methods: cash on delivery, online provider, or both? Refund/payment-failure behavior? | MVP-011 |
| D-013 | Unresolved | Order statuses, cancellation window, refunds, restocking, fulfillment and customer changes? | MVP-011-012 |
| D-014 | Unresolved | Email/SMS channels and providers, privacy/retention/consent requirements and notification scope? | MVP-013-014 |
| D-015 | Unresolved | First retailer and launch scope/date, expected catalog/traffic, performance/availability budgets and optional-feature priorities? | MVP-014 and sequencing |
| D-016 | Agreed | One shared source with independent retailer domain/server/database/credentials/image storage. | All architecture |
| D-017 | Agreed | User approval required for merge, production deploy and branch-protection changes; no direct protected-base pushes. | All workflow |

No unresolved business requirement is silently treated as an approved default. PM should prioritize launch country/currency/payment, delivery model before making dependent tickets Ready. Infrastructure research can continue without production changes.

On 2026-10-10 the user removed MVP-002 and authorized MVP-003 and MVP-004 implementation in dependency order. The two-instance local configuration demonstration is removed; eventual independent deployment requirements remain. No merge is authorized by this implementation request.

## MVP-005 implementation decisions - 2026-10-11

Later user instruction supersedes flexible variant administration: one unit per
product (kg, litre, ml, each), product-owned SKU, no separate variants page.
Product forms, lists and dashboards use this simpler workflow. Previous option
records and audit history remain preserved; see the current scope update in
docs/tickets/MVP-005.md for conversion behavior.

User confirmed flexible variants with required store-wide unique SKUs and permanent
product deletion. SKUs normalize case and outer whitespace; attributes are named
text values such as size, weight and color. Each new product requires a variant.
User confirmed JPEG/PNG/WebP images up to 8 MB each, matching category uploads.
Photos are supplied through staff uploads; no external assets were introduced.
These resolve D-005/D-006 choices needed for this implementation. Import pipelines
and broader content sourcing remain outside this ticket. Category deletion is
protected while products reference it. Product deletion cascades variants/photos
only after confirmation and permission checks. Prices/stock remain MVP-006.
