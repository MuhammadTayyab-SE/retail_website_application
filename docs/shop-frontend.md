# Shop frontend

## Scope and visual source

User authorized the Shop page reached from the supplied Home 02 inspiration.
Reference: `zilly-offline/pages/shop/index.html`. Preserve that page's actual
header-style-2/topbar, breadcrumb, Elementor column/widget structure, product-card
classes and footer-style-1. Its styles and required local assets are retained under
the existing `catalog/home02/reference/` static asset directory. No WordPress/PHP,
tracking or original remote AJAX scripts run in the Django application.

The homepage remains Home 02. Its Shop navigation and Shop Now banners open
`/shop/`. Existing homepage category navigation remains on the homepage, as
previously requested. Captured header/footer links use local routes where supported.

## Files and responsibilities

- `catalog/shop_views.py`: read-only filtering, root-category counts, sort and pagination.
- `catalog/shop_forms.py`: validated input and combined filter choices.
- `catalog/templates/catalog/shop/`: captured styles/header/footer/outer layout,
  reusable filter panel, toolbar/catalogue and database product card partials.
- `catalog/static/catalog/shop/shop.css`: local controls, mobile filter panel and list mode.
- `catalog/static/catalog/shop/shop.js`: sort/page-size submission and mobile filter toggle.
- `Product.objects.with_selling_price()`: PostgreSQL rounded sale-price annotation,
  sharing discount multiplier arithmetic with the existing display-price property.

The separate user edits to AGENTS.md and the Home 02 importer were not changed.

## Available filters

Filters use native GET forms, so URLs are bookmarkable and pagination preserves
all selected values. Categories combine with OR and include descendant products;
the other criteria combine with AND:

- Search by name/SKU.
- Multiple top-level categories, with visible-product counts.
- Minimum/maximum current price in PKR, inclusive of discounts.
- Multiple selling units (kg/litre/ml/each).
- On sale/regular price.
- In stock/out of stock.
- Default/name order, newest, current price ascending/descending.
- 16/32/48 products per page, grid/list display.

The reference's color, arbitrary size/weight, rating and popularity filters are
not exposed: the existing product schema has no authoritative records for them.
Selling units replace unsupported attribute filters without creating another
product-management system. Root-category and inactive-ancestor protection reuse
the existing catalog logic. Photos are prefetched. SQL prices use numeric casting
to avoid PostgreSQL integer division and half-up rounding consistent with the
existing Python calculation. No client-supplied price is treated as authoritative.

Invalid choices, unsafe/oversized IDs, invalid decimals and inverted price bounds
produce clear errors and empty results. No products are fabricated. Empty filters
show all visible products. Zero-stock products have unavailable purchase controls.
Wishlist/basket/product dialogs retain the existing browser preview behavior;
checkout is not implemented by this ticket.

## Developer evidence and QA hold

- Django system check passed; migration consistency check reports no changes.
- Affected Python lint/format and JavaScript syntax checks passed.
- Actual local `/shop/` returns 200 with 7 live product cards.
- Combined sale/stock/sort returns 1 matching product; price range and list view
  return expected rendered collections. Invalid price/category values display
  errors and zero cards. No database writes were made.
- Read-only parity check confirms all 7 visible products' annotated PostgreSQL
  prices match `Product.sale_price`.
- All 54 directly referenced Shop image/style/script resources return 200.
- Regression tests added in `tests/test_shop.py` cover combined criteria, monetary
  parity/rounding, sorting, descendants, invalid inputs, visibility, pagination,
  empty results, links and safe methods. They are **not run** under the user's hold.

No QA agent/process or automated test suite started. The browser runtime remains
unavailable, so rendered screenshot/viewport/interaction comparison is not claimed.
No new dependencies, schema migrations, data changes or production deployment.
PR remains draft; merging requires explicit user approval.
