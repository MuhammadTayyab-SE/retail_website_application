# Product page

Home 02 and Shop product images, names and view controls open
`/shop/product/<product-id>/`. The supplied `zilly-offline/index.html` redirects
to Home 02; the page reuses that captured header, footer, fonts, icons and colours.
The product layout follows the supplied archive's gallery and summary arrangement.

The gallery has ordered thumbnails, previous/next buttons, keyboard arrows and
an enlarged image dialog. Viewing a variant updates its price, description, SKU
and photos in the same viewer. Checkboxes independently select several variants,
each with its own quantity, for one basket action. Quantity limits use the existing
shared product stock; variant inventory is not independently tracked.

## Variant data

The admin dashboard and photo forms retain their original interface; the added
variant editor and photo assignment controls were reverted at the user's request.
The storefront can display existing variant data. Blank variant prices/descriptions
inherit the product values. Product sale discounts also apply to variant prices,
using the existing rounding rule. Unassigned photos are shared; assigned photos
appear first when viewing that variant. Inactive variants and their photos are
omitted from the page payload. Existing products without variants still work.

Migration 0011 adds nullable variant prices, descriptions and photo assignments
and a nonnegative price constraint. It was applied locally without changing
existing business records. Product visibility and category ancestor restrictions
remain enforced by `Product.objects.visible()`.

## Developer verification

- Six focused tests in `tests/test_product_detail.py` pass in a disposable
  PostgreSQL test database. Coverage includes variant pricing/rounding, fallback
  details, inactive variants/photos, invalid photo assignments, unavailable products,
  hidden categories and links from Home 02 and Shop.
- Django system check, migration drift check, affected Python lint/format,
  both JavaScript syntax checks and whitespace checks on changed application files pass.
- Browser checks on a real product verified image navigation, enlarged viewer,
  Escape dismissal and basket count updates. Product GET returned 200, missing
  product returned 404 and POST returned 405.
- An isolated rendered fixture exercised two variants without inserting catalog
  records: price/description/SKU/image switching, multiple selections, quantities,
  total, empty selection and shared stock limit. Three selected units produced
  PKR 1,150.00 and a basket count of 3.
- Screenshots and bounding-box checks were captured at 1440, 768 and 390 pixels
  in `../product-page-evidence/`. The product content fits those viewports.
- The image viewer stays white on hover, focus and active states; browser computed
  styles confirmed white in all four states and the enlarged viewer still opens
  and closes. The product stylesheet URL is versioned to refresh cached styles.

Basket behavior remains the existing in-memory preview; checkout and persistent
cart storage are not implemented. No production deployment or merge was
performed. The broader QA workflow was not started. Pre-existing edits to
`AGENTS.md` and `scripts/import_home02_snapshot.py` were preserved; the latter
has an unrelated trailing whitespace warning in a whole-repository diff check.
