# QA follow-up for 124ba83

Source report: workspace `qa-retail-124ba83/report.md` and its local tickets
QA-RETAIL-001 and QA-RETAIL-002. Fixes stay on `feature/fe-001-home-01` for PR #44.

## QA-RETAIL-001: unsupported floating basket amount

Removed the hardcoded zero-dollar total from the homepage floating basket.
The existing item counter is retained. The basket remains an in-memory preview;
this fix does not introduce totals, persistent carts, or checkout.

## QA-RETAIL-002: missing search destination

Added the missing `products` anchor to the Featured Products widget containing
the results summary, recovery link, product carousel, and empty-result message.
Existing header search URLs ending in `#products` now resolve without changing
the shared search script or Shop/product templates. The existing
`rtsb-container-138192095` anchor remains supported. Both targets use the same
180px desktop and 100px mobile/tablet sticky-header scroll margins.
The homepage stylesheet version was bumped to invalidate cached styles.

## Verification

- PASS: `python manage.py test tests.test_home02.Home02QARegressionTests --verbosity 2`
  (two tests; no database setup). Covers count-only basket markup and results
  anchor rendering for the initial and unmatched-search states.
- PASS: scoped `git diff --check`.
- Django system checks passed during the focused test run.

Both tickets are implemented, awaiting independent QA retest. The original QA
report is preserved. No new browser interactions, screenshots, visual checks,
or full database regression suite were run. Retest the floating basket after
adding an item and matching/unmatched header searches from Home, Shop, and
product pages at desktop and mobile widths. No admin/model/schema changes,
merge, or production deployment are part of these fixes.
