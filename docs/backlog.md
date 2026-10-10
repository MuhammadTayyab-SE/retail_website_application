# Project backlog

GitHub authenticated REST access is verified; CLI is absent. PM created the 15 GitHub Issues listed below; docs/github-issues.json records returned links. Ownership identifies roles through labels/comments, not invented GitHub accounts.

Workflow: Backlog -> Ready -> In Development -> In QA -> Awaiting My Review -> Done. Use Changes Required or Blocked with a reason and next action. Done requires merge. Only one implementation ticket may be active initially.

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

### MVP-003 - Retailer staff authentication and access control
- Priority: P0. Dependencies: MVP-001; D-004 admin-only scope agreed; Django admin selected by PM.
- Acceptance: single admin/superuser can log in/out through Django admin; anonymous, inactive and non-admin users cannot access admin operations; tests cover direct URL access and permission failures; no staff role matrix, custom admin UI or public registration is included.

### MVP-004 - Dynamic categories
- Priority: P0. Dependencies: MVP-003; category decisions confirmed 2026-10-10. Parent/subcategories; deactivate only, permanent deletion disabled. Remaining D-005 product rules affect MVP-005.
- Acceptance: authorized staff can create, edit, order and deactivate categories; storefront reads active categories from database; duplicate/invalid values receive useful errors; product-associated deletion behavior is defined and tested; empty catalog renders safely.

### MVP-005 - Products, variants and images
- Priority: P0. Dependencies: MVP-004; D-005, D-006.
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
- Priority P1. State: In QA; visual acceptance pending browser availability.
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
