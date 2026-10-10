# Decision register

Statuses: Agreed, Proposed, Unresolved. "Agreed current scope" records a settled local choice; "production deferred" and "cloud deferred" preserve future decisions without blocking local implementation. PM owns this register; record date, user answer and consequences when resolving an entry. Current date: 2026-10-10.

| ID | Status | Decision / question | Impact / blocking tickets |
|---|---|---|---|
| D-001 | Agreed | Adopt Django and PostgreSQL: inspection found no existing application to constrain adoption. Adopted by PM as the technical baseline; no existing code requires migration. | MVP-001 |
| D-002 | Agreed current scope; production deferred | Run and test locally now. Production hosting provider, OS, rollout, retention and recovery objectives are deferred. | Local MVP-002, MVP-014; production follow-up |
| D-003 | Agreed current scope; cloud deferred | Local filesystem media now with configurable storage and distinct retailer/test media roots, gitignored. Cloud storage is deferred. Upload format/size limits remain a technical follow-up requiring explicit implementation review. | MVP-002, MVP-005 |
| D-004 | Agreed scope; technical choice recorded | Only admin role now, no staff role matrix. PM selects Django admin with a single superuser/admin; anonymous, inactive and non-admin users are denied. Custom admin UI is not required unless later requested. | MVP-003 |
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
