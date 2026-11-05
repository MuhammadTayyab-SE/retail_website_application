# Project backlog

## Catalog/inventory MVP strategy - 2026-11-04

Reviewed baseline: development **88c7536**, with planning PR #65 and completed
Brand/SKU PRs #66/#67 merged. See [the current plan](catalog-inventory-plan.md)
for actual implementation/test coverage, schema gaps, four-tab UI, ownership of
remaining work and integration tests. Historical entries below are not current
GitHub status evidence.

Disposable development/test catalog and transaction data need not be preserved.
No legacy backfill/mapping engine is required. This is not permission to delete
data: confirm the isolated target and exact scope and obtain explicit approval
before any destructive DB/schema/data action. Never reset shared/staging/production
databases or remove unrelated data/code/completed functionality. Preserve the
migration chain with forward changes. No feature or QA run starts in this review.

### Current CINV issues and dependencies

| Increment | Issue | State | Dependencies |
|---|---|---|---|
| CINV-01: Brand management and optional product association | [#54](https://github.com/MuhammadTayyab-SE/retail_website_application/issues/54) | Done | development f0567ea; historical #6/#7 closed |
| CINV-02: Durable SKU issuance and pre-order correction history | [#55](https://github.com/MuhammadTayyab-SE/retail_website_application/issues/55) | Done | development f0567ea; historical #6/#7 closed |
| CINV-03: Variant identity, automatic defaults and variant photo ownership | [#56](https://github.com/MuhammadTayyab-SE/retail_website_application/issues/56) | In Development | CINV-01, CINV-02 |
| CINV-04: Canonical variant cost, regular and sale pricing | [#57](https://github.com/MuhammadTayyab-SE/retail_website_application/issues/57) | Backlog | CINV-03 |
| CINV-05: Variant inventory balance and immutable movement foundation | [#58](https://github.com/MuhammadTayyab-SE/retail_website_application/issues/58) | Backlog | CINV-03 |
| CINV-06: New opening stock and single-writer checkout inventory integration | [#59](https://github.com/MuhammadTayyab-SE/retail_website_application/issues/59) | Backlog | CINV-04, CINV-05 |
| CINV-07: Stock overview, recorded adjustments and stock history | [#60](https://github.com/MuhammadTayyab-SE/retail_website_application/issues/60) | Backlog | CINV-06 |
| CINV-08: Exact variant quantities across cart, checkout and order outputs | [#61](https://github.com/MuhammadTayyab-SE/retail_website_application/issues/61) | Backlog | CINV-04, CINV-06 |
| CINV-09: Four-tab product workflow with per-variant galleries | [#62](https://github.com/MuhammadTayyab-SE/retail_website_application/issues/62) | Backlog | CINV-01, CINV-03, CINV-04, CINV-06, CINV-07, CINV-08 |
| CINV-10: Finish Catalog/Inventory navigation and module-scoped rendering | [#63](https://github.com/MuhammadTayyab-SE/retail_website_application/issues/63) | Backlog | CINV-01, CINV-07, CINV-09 |
| CINV-11: Independent clean-install and catalog/inventory integration QA | [#64](https://github.com/MuhammadTayyab-SE/retail_website_application/issues/64) | Backlog | CINV-01, CINV-02, CINV-03, CINV-04, CINV-05, CINV-06, CINV-07, CINV-08, CINV-09, CINV-10 |

Recommended one-ticket order: **03 -> 04 -> 05 -> 06 -> 07 -> 08 -> 09 -> 10 -> 11**.
CINV-03 was started by the user on 2026-11-05; database execution/testing await
explicit isolated-target approval. Future destructive operations still have separate
target/approval gates. CINV-01/02 are Done by merge, with fresh integration QA still
required. Reuse their code and the current gallery/checkout/admin, not new copies.
Exactly four product tabs: **Basic Info, Variants, Photos, Availability**.
Variant-image schema/operations belong to #56; tab composition to #62; pricing to
#57; ledger operations to #58/59 and stock views to #60. No duplicate responsibilities.

GitHub issue links remain in docs/github-issues.json. PM -> Developer -> QA -> My
Review uses one active implementation, isolated branch/draft PR and exact-SHA
evidence. QA execution follows an authorized handoff/environment; prior hold is
not silently lifted. Merge/deployment still require explicit approval.

## SETUP-001 - Establish team and project baseline
- Priority: P0. State: Done (merged PR16). Owner: Developer subagent. Reviewer: PM / Technical Lead. Validator: QA subagent.
- Scope: documentation and repository hygiene only; no application implementation.
- Acceptance: required documents exist; deployment isolation and shared source are explicit; unresolved decisions are recorded; prioritized tickets have acceptance criteria and dependencies; PM and independent QA review are recorded; no secrets or existing work are overwritten.
- Dependencies: none.
- Validation: document and diff review; no application tests exist. PR/merge require verified GitHub access and user merge approval.

## MVP tickets

MVP-001 is merged (PR #19). User removed MVP-002 and authorized MVP-003 then MVP-004 on 2026-10-10. Developer owns both in isolated branch `feature/mvp-003-004-admin-categories`. Implementation exists; both are Blocked for required PostgreSQL validation and GitHub publication. See docs/tickets/MVP-003-004.md. Other tickets remain Backlog. GitHub is not authenticated in this session; these are local statuses, not claims of remote transitions.

### MVP-001 - Django/PostgreSQL foundation (merged PR #19)
- Priority: P0. Dependencies: SETUP-001 merged (Done); D-001 adopted. Current scope is local development/testing; production hosting is deferred.
- Acceptance: Django project and dependency lock exist; development and automated-test configuration uses PostgreSQL; configuration comes from environment; startup fails clearly for missing required settings; example environment contains placeholders only; health endpoint exposes no secrets; clean-install and test commands are documented and actually run; no storefront feature is included.

### MVP-002 - Isolated local retailer configuration (Removed)
- Removed by user on 2026-10-10; retained here for historical traceability only.

### MVP-003 - Super Admin, worker roles, module permissions and audit logs
- Priority: P0. State: In Development. Owner: Developer role. User authorized expanded implementation on 2026-10-11; supersedes D-004's single-admin-only restriction.
- Dependencies: MVP-001; integration with MVP-004; Product attribution integrates when MVP-005 introduces Product persistence.
- Acceptance: Super Admin manages worker accounts and roles; server-enforced module/action permissions apply immediately to existing sessions; workers cannot administer accounts/roles/audit logs; password reset without password disclosure; immutable portal audit history; creator/editor and timestamps on Parent Categories and Categories, with reusable Product foundation. Independent QA required before user review.
- Evidence and remaining scope: docs/tickets/MVP-003-roles-audit.md. GitHub #4 is the authoritative expanded requirement.

### MVP-004 - Dynamic categories
- Priority: P0. Dependencies: MVP-003; category decisions confirmed 2026-10-10. Parent/subcategories; deactivate only, permanent deletion disabled. Remaining D-005 product rules affect MVP-005.
- Acceptance: authorized staff can create, edit, order and deactivate categories; storefront reads active categories from database; duplicate/invalid values receive useful errors; product-associated deletion behavior is defined and tested; empty catalog renders safely.

### MVP-005 - Products, variants and images
- Status: In Development; developer implementation complete, independent QA pending.
- Priority: P0. Dependencies: MVP-004 (merged); product choices confirmed 2026-10-11.
- Agreed: flexible text attributes; required store-wide unique normalized SKUs; permanent confirmed deletion; JPEG/PNG/WebP up to 8 MB. See docs/tickets/MVP-005.md.
- Acceptance: staff manage products and agreed variant attributes/SKUs; products belong to database categories; active/inactive visibility is enforced; validated image uploads use configured storage; invalid uploads fail safely; variant identifiers are unique within the retailer; product and variant edit permissions are tested.

### MVP-006 - Variant prices and stock
- Priority: P0. Dependencies: MVP-005; D-007 country/tax/rounding (currency PKR agreed), D-008 stock rules.
- Acceptance: authorized staff edit decimal prices and agreed stock quantities per variant; invalid/negative inputs are rejected as agreed; customer view uses database prices; unavailable variants cannot be ordered; concurrent purchase tests prevent overselling under agreed reservation rules; price and stock changes have agreed audit evidence.

### MVP-007 - Responsive browse, search and product detail
- Priority: P0. Dependencies: MVP-004-006; D-009 visual direction approved.
- Acceptance: mobile and desktop layouts expose database categories, products, variants, current prices and availability; search/filter behavior is agreed and tested; empty/error states are usable; keyboard navigation and image descriptions work; browser evidence records viewport, browser and commit. Zilly is inspiration only; do not copy licensed assets.

### MVP-008 - Cart and server-side totals
- Priority: P0. Dependencies: MVP-006-007; D-007, D-010 cart/identity.
- Acceptance: customers add/update/remove agreed variants; quantities are validated; totals are calculated server-side using current authoritative prices; stale price and stock changes are explained; cart persistence follows agreed guest/account rules; tampered totals cannot affect order values.

### MVP-009 - Branding and homepage banners
- Priority: P1. Dependencies: MVP-003, MVP-007; D-009.
- Acceptance: staff configure retailer name, logo, agreed colors/contact fields and ordered active banners; configured branding appears responsively; invalid images/links are rejected; inactive banners are hidden; missing configuration has safe defaults.

### MVP-010 - Delivery settings and checkout eligibility
- Priority: P0. Dependencies: MVP-003, MVP-008; D-011 delivery model.
- Acceptance: staff configure agreed zones, charges, minimums and availability; checkout validates address/zone and delivery eligibility server-side; out-of-zone, closed-window and threshold failures are clear; fee boundaries are tested; customers see final delivery cost before submitting.

### MVP-011 - Order placement and payment method
- Priority: P0. Dependencies: MVP-008, MVP-010; D-010, D-012 payment, D-013 order lifecycle.
- Acceptance: agreed checkout fields validate; order stores immutable item/price/address snapshots; stock update and order creation are atomic; repeated submissions cannot create duplicate orders; payment behavior matches the approved MVP method; failures leave consistent stock/order state; confirmation reveals only authorized order data.

### MVP-012 - Admin order processing
- Priority: P0. Dependencies: MVP-003, MVP-011; D-013.
- Acceptance: authorized staff list/filter orders and inspect snapshots; only agreed status transitions are permitted; cancellation/restocking behavior follows the decision; customer information access is restricted; transitions and concurrent edits have tested behavior and agreed audit history.

### MVP-013 - Customer order access and notifications
- Priority: P1. Dependencies: MVP-011-012; D-010, D-014 notifications/privacy.
- Acceptance: customers access only their authorized orders using the agreed mechanism; agreed notifications fire once for relevant events; provider failures do not corrupt orders; messages disclose no unrelated customer data; retention rules are documented.

### MVP-014 - Local release validation and deferred production readiness
- Priority: P0. Dependencies: all approved local MVP scope; D-014 and D-015 local validation needs.
- Acceptance: independent QA runs agreed positive/negative/permission/concurrency and mobile/desktop regression on exact release SHA with synthetic data; local clean-install/startup, configuration and isolated database/media checks are recorded; unavailable local checks and unresolved bugs are explicitly dispositioned by PM/user; production hosting, HTTPS, monitoring, backup retention/recovery and rollout validation are deferred to a future production-readiness ticket; production deployment remains gated on explicit user approval.

## Bug ticket template

ID / linked feature and PR; severity and priority; state; responsible developer role; exact commit SHA; OS/browser/viewport and test database context; prerequisites; numbered reproduction steps; expected result; actual result; evidence; PM routing decision; fix commit; retest and regression evidence. QA reports defects and never silently changes application code.


## GitHub Issues

| Ticket | Issue |
|---|---|
| SETUP-001 | [#1](https://github.com/MuhammadTayyab-SE/retail_website_application/issues/1) |
| MVP-001 | [#2](https://github.com/MuhammadTayyab-SE/retail_website_application/issues/2) |
| MVP-002 | [#3](https://github.com/MuhammadTayyab-SE/retail_website_application/issues/3) |
| MVP-003 | [#4](https://github.com/MuhammadTayyab-SE/retail_website_application/issues/4) |
| MVP-004 | [#5](https://github.com/MuhammadTayyab-SE/retail_website_application/issues/5) |
| MVP-005 | [#6](https://github.com/MuhammadTayyab-SE/retail_website_application/issues/6) |
| MVP-006 | [#7](https://github.com/MuhammadTayyab-SE/retail_website_application/issues/7) |
| MVP-007 | [#8](https://github.com/MuhammadTayyab-SE/retail_website_application/issues/8) |
| MVP-008 | [#9](https://github.com/MuhammadTayyab-SE/retail_website_application/issues/9) |
| MVP-009 | [#10](https://github.com/MuhammadTayyab-SE/retail_website_application/issues/10) |
| MVP-010 | [#11](https://github.com/MuhammadTayyab-SE/retail_website_application/issues/11) |
| MVP-011 | [#12](https://github.com/MuhammadTayyab-SE/retail_website_application/issues/12) |
| MVP-012 | [#13](https://github.com/MuhammadTayyab-SE/retail_website_application/issues/13) |
| MVP-013 | [#14](https://github.com/MuhammadTayyab-SE/retail_website_application/issues/14) |
| MVP-014 | [#15](https://github.com/MuhammadTayyab-SE/retail_website_application/issues/15) |

## ADMIN-UI-001 ? Consistent Zilly-inspired administration

- Issue: [#22](https://github.com/MuhammadTayyab-SE/retail_website_application/issues/22).
- Priority P1. State: In Development; visual revision requested, QA deferred by user.
- Owner: Developer. Reviewer: PM. Validator: independent QA agent.
- User authorized full admin styling after the login-only PR #21. MVP-003/004
  and login PR #21 are merged; earlier blocked-state entries above are historical.
- Scope: dashboard, shared navigation, app overview, categories list/search/filter/
  inline edits, add/edit/history, password change and logout; coherent Zilly-inspired
  green/sage/yellow/white palette, original assets, responsive layout and focus/errors.
- Preserve owner-only access, CSRF, POST logout, category validation/deactivation and
  deletion restrictions. Dashboard counts must come from database; no fake commerce data.
- QA records linked defects, severity, exact SHA, evidence, developer fix and retest;
  desktop/tablet/mobile screenshots are required for visual acceptance. Browser
  unavailability blocks visual signoff, not functional implementation.
- Developer fixed QA-ADMIN-001 shared-shell gap and QA-ADMIN-002 login fallback;
  31 PostgreSQL tests passed. Independent QA results and remaining visual checks are
  recorded in docs/tickets/ADMIN-UI-001.md and the linked PR. Done still requires merge.

- 2026-10-10 visual revision: Developer is refining the existing admin-visual branch/PR #25 in place. Strong green/yellow shell, readable type, dashboard, login, tables and forms are updated first. Prior test evidence covers the earlier candidate only; renewed QA will follow user visual review.

- Latest visual direction: user-supplied `supporting docs/POS-Standalone.html`. Same admin-visual branch/PR #25; navy navigation, emerald actions, mint selection, compact category dashboard and cool-gray workspace replace the grocery promotional treatment. In Development; QA deferred by user.

ADMIN-UI-001 latest revision: exact-token navy/emerald shell in PR #25; explicit sidebar grid and single navigation. Developer 31-test/static checks and independent PM source review passed. Browser screenshots, interaction/console checks and independent QA remain pending; In Development. See docs/tickets/ADMIN-UI-001.md.

CATALOG-UI-002 ? In Development: category photos, adjustment sidebar, local storage, thumbnail list and existing parent/child hierarchy. Same admin-visual PR #25. QA deferred explicitly by user. CATALOG-FLOW-003 ? Backlog: brand/product management follows category work, as confirmed by user.
