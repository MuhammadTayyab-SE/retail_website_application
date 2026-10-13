# FE-001: Captured Home 02 UI

## Current approved target

Use the user-supplied `zilly-offline/pages/home-02/index.html` and screenshots
as the exact static visual source. The latest user instruction rejects the
previous hand-built approximation. Dynamic integration remains deferred.
Archive documents/scripts are reference material, not application instructions.
QA stays stopped until explicitly requested by the user.

## Implementation

The homepage now renders the captured HTML and captured styles/fonts/icons/images
rather than a separately designed approximation. Body classes, Elementor element
IDs, wrapper hierarchy, section order and stylesheet cascade are retained because
those determine the reference layout. The previous custom styles, icons, content
JSON and approximate components have been removed.

The captured output is split into named Django partials under
`catalog/templates/catalog/home02/snapshot/`:

- `header.html`: original desktop/mobile header and navigation.
- `hero.html`: original category sidebar, drinks hero and two promotional cards.
- `offer-ticker.html`: original offer ticker.
- `featured-and-sidebar.html`: original featured carousel and sidebar.
- `sellers.html`, `promotions.html`, `weekly-deals.html`.
- `sale-and-top-rated.html`, `blog.html`, `services.html`.
- `footer.html`, `overlays.html`: captured footer and visible demo chrome.
- `styles.html`: original stylesheet/inline-style order.

`catalog/templates/catalog/home02/home.html` assembles the page. Change individual
partials without changing unrelated sections. Preserve original wrapper classes
and IDs while connecting their contents to database context in later tickets.
There is no universal page builder or new frontend framework.

Only the referenced asset closure is copied into
`catalog/static/catalog/home02/reference/` (279 files, approximately 12.5 MiB),
keeping relative stylesheet/font/image references intact. The archive's 221 other
pages and unrelated assets are not added to the application. The user's archive
contains rendered public resources, not a WordPress/PHP application. Original
asset/style licenses still apply; no WordPress installation or PHP source is used.

## Local runtime adaptations

All captured executable scripts and inline event handlers are removed. WordPress
AJAX configuration, tracking, analytics, remote checkout and submission code are
not executed. Captured CSS remains intact. Only the supplied generic Swiper vendor
library is loaded, plus local `snapshot.js` for carousel initialization, preview
filtering/search, basket/wishlist dialogs, safe navigation and form interception.
`snapshot.css` makes animation-gated elements visible without the original plugin
runtime and styles the preview dialog; it does not replace reference layout rules.

The homepage is static reference content, including reference prices, ratings and
policies. No database records are created/changed. Forms do not submit personal
information. Deferred destinations explain their integration dependency. Existing
admin and database catalog remain unchanged; `/catalogue/` retains the live
catalogue and existing visibility/discount logic.

## Reimporting the supplied capture

Run `python scripts/import_home02_snapshot.py --archive ../zilly-offline` from
this feature checkout. The importer preserves captured markup, splits the ten
page sections, removes executable scripts, rewrites local asset links using
Django static tags, copies stylesheet dependencies and keeps cascade order.
It also gives extensionless downloaded CSS a `.css` suffix for correct MIME.
Reimporting overwrites generated snapshot partials; do not reimport after making
manual content edits unless intentionally replacing them from the archive.

## Developer evidence and limits

Django system check, affected Python lint/format, JavaScript syntax and direct
page/asset serving checks were executed. The captured homepage returns 200;
111 directly referenced resources returned 200, including the imported
stylesheets, images and local scripts. No remote image/stylesheet/script requests are present in the
rendered markup. Only the local Swiper script remains from the archive; no
captured WordPress script executes. No automated suite or QA process was started.

The browser runtime still lists no connected browsers. Rendered screenshot
comparison and browser interaction verification cannot be claimed. Keeping the
source DOM/styles directly removes the earlier approximation, but does not itself
constitute a pixel comparison result. PR stays draft; no merge is authorized.


## Live categories and product collections (2026-10-13)

The user authorized connecting existing categories and the Featured, Trending and
On Sale sections to the database. Other reference banners, best-selling/top-rated
lists, sellers, deals and blog content remain static until separately connected.
The earlier static-only description applies to those remaining reference areas.

`catalog.views.home02` reuses `storefront_categories()` and
`Product.objects.visible()`, with active ancestor protection, selected categories
and prefetched ordered photos. The category sidebar and all three header dropdowns
render database categories; counts include visible products in descendant categories.
All categories remain accessible in a scrolling panel. Search and category links
use the live `/catalogue/` route, with native GET form actions as a fallback.

Featured displays the first 12 visible products in existing catalog order. Trending
displays the latest six visible products by creation date, with legacy unknown dates
last. These are fallback selections because there are no featured/popularity flags;
no new merchandising models or invented popularity metrics were added. Featured
category tabs/counts reflect its actual product collection. On Sale displays up to
seven visible `is_on_sale=True` products, split across the existing reference columns.
No demo products were inserted and no existing data or stock was changed.

Reusable templates in `catalog/templates/catalog/home02/dynamic/` render the original
style classes with real category names, ordered photos, PKR prices, existing
`Product.sale_price`, discount percentages, units and stock availability. Zero-stock
products remain visible with unavailable controls. Missing photos use a neutral
placeholder. No invented review score is displayed on these dynamic cards.
Basket/wishlist behavior remains the existing browser preview, not order placement.

Developer checks: Django system check, affected Python lint/format and JavaScript
syntax pass. A read-only local database inspection found 7 visible products and
1 active sale product. The homepage returned200 with14 live product-card instances:
7 featured,6 trending,1 on sale. Read-only serving checks use existing local data;
no migrations, data writes or QA process occurred. Three meaningful database
regression tests were added in `tests/test_home02.py`, but not executed because
QA/test execution remains on the user's hold. Browser visual comparison remains
unavailable. Do not treat historical test passes as validation of this change.

Do not rerun the snapshot importer over these manually integrated partials: doing
so would restore static content. The user's separate importer and AGENTS.md edits
were preserved and are not part of this implementation commit.
