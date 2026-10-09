# Decision register

Statuses: Agreed, Proposed, Unresolved. PM owns this register; record date, user answer and consequences when resolving an entry. Current date: 2026-10-09.

| ID | Status | Decision / question | Impact / blocking tickets |
|---|---|---|---|
| D-001 | Agreed | Adopt Django and PostgreSQL: inspection found no existing application to constrain adoption. Adopted by PM as the technical baseline; no existing code requires migration. | MVP-001 |
| D-002 | Unresolved | Which hosting provider/server OS, environments, rollout process, backup retention and recovery objectives? | MVP-002, MVP-014 |
| D-003 | Unresolved | Which independent image storage provider/bucket/account strategy, quotas and upload limits? | MVP-002, MVP-005 |
| D-004 | Unresolved | Which staff roles and permissions? Is Django admin acceptable for initial retailer management or is a custom interface needed? | MVP-003 |
| D-005 | Unresolved | Category hierarchy, SKU rules, units/weights, variant attributes, product deletion/archive and catalog import needs? | MVP-004-005 |
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

No unresolved business requirement is silently treated as an approved default. PM should prioritize launch country/currency/payment, staff admin approach and delivery model before making dependent tickets Ready. Infrastructure research can continue without production changes.



