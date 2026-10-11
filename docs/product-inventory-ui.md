# Products inventory interface

User-requested update on `feature/mvp-005-products`, based on the Inventory view
and product form in `supporting docs/index.html`. Base commit: `99b8c0a`.
The changes are local and uncommitted; the base SHA is not a tested revision of
this update. GitHub authentication was unavailable, so no issue or draft PR was
created. No merge or deployment was performed.

## Behavior

- Inventory uses the reference's table: showcase thumbnail, product, SKU,
  category, price, available quantity, stock badge, Details and + Stock. Its
  toolbar contains the reference's product/SKU search and category filter.
  Pagination, detail-page deletion and permissions remain available.
- The product editor uses a compact card with category/SKU and price/quantity
  pairs, selling unit, description and active state. Its photo gallery has one
  multi-file picker, client-side previews, showcase selection, ordering controls,
  alt text, and per-photo deletion. The first saved position is the showcase photo.
  It remains a dedicated page, preserving server validation and read-only access.
- Price is stored as a nonnegative decimal in PKR. Quantity is a nonnegative
  whole number. Migration `0008_product_price_quantity` initializes existing
  records to zero; the retailer must enter actual prices and stock.
- Stock status is Out of stock at zero, Low stock from 1 through 10, and In stock
  above 10. Inactive products display Inactive.
- Receive inventory requires product change permission, accepts positive whole
  quantities, locks the product during increment, rejects overflow and records
  the update in the audit log with user attribution.
- Earlier header and non-clickable sidebar role changes are included here so
  they are available alongside the Products update.

## Developer verification

Executed using this checkout's Python environment and disposable PostgreSQL
test databases with synthetic data:

- `python manage.py test --noinput --verbosity 0`: 104 tests passed.
- `python -m ruff check .`: passed.
- `python -m ruff format --check .`: passed.
- `python manage.py makemigrations --check --dry-run`: no changes detected.
- `git diff --check`: passed.

The browser runtime returned no available browsers, so viewport screenshots and
interactive browser verification were not performed. These results are developer
checks, not independent QA or PM review. Renew independent review and affected QA
against the eventual exact commit before recommending completion.
