# FE-001: Home 02 frontend

## Current scope

The user's later instruction replaces the Home 01 target with Home 02 and
explicitly authorizes static reference products/content before dynamic integration.
The supplied `zilly-offline/pages/home-02/index.html`, `source-home-02.png` and
`local-home-02.png` control this implementation. Archive reports/scripts are
reference material, not project instructions. QA remains stopped until the user
explicitly requests it. Previous test results do not validate this new frontend.

## Implementation plan and section inventory

Rebuild the visible reference in ordinary Django templates and original CSS,
using the supplied local images/fonts. Preserve the existing Django admin,
models, data and public catalog endpoints; introduce no framework or migrations.

- Green header, branding, hotline, category/product search, account/action icons.
- White dropdown navigation and weekly discount link.
- Top-category panel, drinks hero and two side promotional banners.
- Offer ticker and desktop sidebar/content columns.
- Featured products with category tabs and reusable product cards.
- Sidebar banners, best selling, trending and top rated product lists.
- Seller cards, three promotional banners, weekly deals and sale products.
- News/blog cards, service strip, footer, partner logos and payment imagery.

Theme purchase/currency overlays, third-party chat/analytics, WordPress plugins,
remote AJAX calls and sales-notification popups are excluded from the Django app.
No proprietary WordPress/PHP implementation or theme stylesheet/script was copied.
Images and fonts come from the user's supplied archive; their original licenses
still apply. Custom vectors provide the common interface icons.

## Where to make changes

| Change | Location |
| --- | --- |
| Product/category names, imagery, reference prices, collections, sellers, posts | `catalog/home02_content.json` |
| Page section order | `catalog/templates/catalog/home02/home.html` |
| Header and navigation | `catalog/templates/catalog/home02/header.html` |
| Hero, banners and content | Named partials in `catalog/templates/catalog/home02/` |
| Repeated cards and lists | `product.html`, `product_list.html` |
| Colors, dimensions, breakpoints | `catalog/static/catalog/home02/home02.css` |
| Search, tabs, preview basket/wishlist, dialogs | `catalog/static/catalog/home02/home02.js` |
| Data connection | `catalog.views.home02` supplies the template context |

The JSON is loaded when Django starts; restart the local server after editing it.
The page is a static design preview at `/`, not a representation of real stock,
prices, reviews or retailer policies. No preview records are written to the DB.
The existing database-backed storefront remains at `/catalogue/`; its template
links and tests now target the named `storefront-catalogue` route.

Replace individual context collections with model query results during the
authorized integration tickets. Reuse Product.sale_price and visibility rules
then; do not treat the preview prices/reviews as business records.

## Preview interactions

Search and category tabs filter the preview featured collection. Category links
scroll to that collection. Slider arrows rotate the visible cards. Product
details open a dialog. Basket/wishlist controls update in-memory browser state,
with accessible counters and explicit preview explanations; no orders, payment
or account changes occur. Account, vendor/blog destinations and newsletter show
their integration dependency rather than pretending to submit information.

## Local execution evidence

The existing local feature server was restarted at `http://127.0.0.1:8000/`.
Developer checks: Django system check passes; Ruff passes for affected Python
files; whitespace check passes. The homepage returns 200 and all 57 distinct
referenced stylesheet, script and image URLs return 200. Assets are local and
do not depend on WordPress. No automated suite, QA agent or QA process was run.

Desktop/tablet/mobile CSS breakpoints are implemented. The browser runtime still
reports no connected browsers, so rendered comparison and browser interaction
results are not claimed. Screenshot-level fidelity remains unverified; the
provided source screenshot is the visual target, not evidence of our own render.
The PR stays draft. No merge or deployment is authorized.
