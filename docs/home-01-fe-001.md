# Home 01 storefront foundation — FE-001

## Tracking and implementation order

The parent tracker is #38. Only #39 (FE-001) is in implementation. #40 (ADM-001)
depends on the foundation's content requirements; #41 (FE-002) depends on #39 and
#40; #42 (ADM-002) follows #39 and existing product management; #43 (QA-001)
validates the complete integration after those tickets. Existing #8 and #10 are
related scope and should be reconciled before their overlapping work begins.
Other tickets remain Backlog. There is no project milestone. A PR targets
development; merging requires user approval.

## Reference evidence and component inventory

Reference: https://www.radiustheme.com/demo/wordpress/themes/zilly/ (Home 01).
The reference returned HTTP 403 during planning, and the browser runtime was
unavailable. Exact sections, measurements and visual fidelity cannot be verified.
This is an original grocery storefront based on the user's requested component
inventory, not a claim of a pixel matched clone. No proprietary source or assets
are used. The original SVG market basket is decorative illustration, not a product
photograph or a claim about store inventory.

| Component | Foundation behavior | Later work |
| --- | --- | --- |
| Top strip, header, branding | Generic Grocery identity, responsive search | ADM-001/FE-002 retailer branding and contact content |
| Navigation | Native accessible category disclosure, catalogue/category anchors | Configurable links only if required |
| Hero | Original SVG and generic editorial copy; catalogue CTA | ADM-001/FE-002 image, copy, CTA URL, activation, order |
| Category cards | Up to 12 active reachable categories in existing order; existing photo/crop | ADM-002 selection and merchandising |
| Promotional panels | Generic recipe/essentials copy and working anchors | Managed promotional banners |
| Product grid | Actual visible catalogue, 24 per page, name/SKU search, category hierarchy filter | ADM-002 featured collection selection/order |
| Sale collection | Up to 8 actual visible sale products; existing sale_price calculation | ADM-002 merchandising, no duplicate discount engine |
| Closing panel and footer | Generic copy and working catalogue links | ADM-001/FE-002 retailer content |
| Empty/error states | Empty catalogue, photo placeholder, no results, unavailable category | Configurable content if needed |
| Other reference sections | Unverified; no invented reference inventory | Inspect accessible reference/screenshots before fidelity signoff |

Cart, checkout, account, wishlist, newsletter, reviews, delivery claims, contact
details and countdown timers are outside FE-001. No simulated actions, ratings,
stock counts, fabricated products, discounts or retailer promises are rendered.
No new settings/banners/merchandising models are introduced here.

## Existing functionality reused

Category hierarchy, activity, ordering and photo crop fields are reused. Product
visibility uses the existing `Product.objects.visible()` logic, including legacy
variant eligibility, then restricts to categories reachable from active roots.
Public category photos enforce that same ancestor visibility. Existing product
photo authorization and all admin, health, category and product routes remain.
ProductPhoto ordering chooses the first image, with provided alt text or product
name. Prices use `Product.sale_price`, including decimal half-up rounding;
original prices and percentage badges appear only on actual sales. Available
quantity controls the In stock/Out of stock label. Out of stock products remain
visible as catalogue information. There is no purchase action in this foundation.

Search is trimmed, capped at 200 characters and combined with category filters.
Parent selection includes descendants. Unknown, hidden or malformed category
IDs produce a clear empty state rather than unfiltered results. Pagination
preserves filters and safely handles invalid page values. Queries are bounded
by page size and prefetched photos; category hierarchy reads grow with category
count, and image requests each perform their own visibility check.

## Local setup and validation

Use the existing Readme.md PostgreSQL setup and checkout-local ignored `.env`.
There are no new dependencies, environment variables or migrations. Copy the
development `.env` into a new worktree only when it does not already exist.
Run `uv sync --frozen --python 3.13`, then `uv run --frozen python manage.py
runserver 127.0.0.1:8000 --noreload` and visit `/`. Static assets belong to the
catalog app and use Django staticfiles; normal production collectstatic setup
applies. Production deployment is outside this ticket.

Use a distinct disposable PostgreSQL test database (`DB_TEST_NAME` must differ
from `DB_NAME`). Do not seed or migrate the user's existing development data for
visual testing. Synthetic fixtures are created only by the test runner or in
QA's isolated database. Run `python manage.py test tests.test_storefront` for the
focused cases, and the complete suite plus check/makemigrations/ruff/diff checks
before handoff. Developer evidence is recorded separately from independent QA.

### Developer execution evidence (2026-10-13)

Windows, Python 3.13.14, Django 5.2.18, existing local PostgreSQL connection.
`uv run --frozen` was blocked by access to the default user cache; commands used
the already installed worktree environment directly (`.venv/Scripts/python.exe`
and `.venv/Scripts/ruff.exe`). No dependency changes were needed.

- `python manage.py check`: passed, no issues.
- `python manage.py makemigrations --check --dry-run`: passed, no changes.
- `python manage.py test --verbosity 1 --noinput`: passed, 132 tests in 15.243s;
  runner created/destroyed the configured disposable test database. Nine new
  storefront tests cover empty states, safe methods, existing routes, hierarchy
  visibility, image protection/type/missing files, sale rounding/stock,
  first-photo ordering, legacy variants, invalid filters/escaping, search,
  descendant filtering, pagination and six-query filtered-page bound.
- `ruff check .`, `ruff format --check .`, `git diff --check`: passed.

No developer migration command was run against existing development data.
Browser screenshots and responsive visual signoff remain for independent QA;
these automated tests do not establish exact reference fidelity.

### Standards re-audit (2026-10-13)

Read the user's updated AGENTS.md in full and reviewed the scoped implementation.
The category hierarchy helper isolates genuine traversal complexity and is used
by the homepage and public category image endpoint; no extra service layers or
wrapper chains were added. Existing endpoints and models remain unchanged.

Corrected tests that accessed a private response cleanup list: successful photo
responses now use RequestFactory and the public FileResponse file handle, verify
the PNG bytes and close the file. Negative access tests still exercise the client
route. Replaced a whitespace-sensitive category absence check with category IDs,
filter links and image URLs. Added deep descendant/hidden-filter, search length,
unsafe image method and sale/page query-bound coverage. Long category dropdown
links can wrap, and product headings can shrink within their flex container.

Re-executed checks with the installed worktree environment: all 135 tests passed
in 15.076s; Django check, migration dry-run, Ruff check, Ruff format check and
git diff check passed. Only the configured disposable test database was used.
No unrelated endpoint refactor, dependency or schema changes were made.

The PM retried the same Zilly reference, which remains inaccessible, and the
browser runtime returned no available browsers. Desktop/tablet/mobile browser
interactions, screenshots and visual comparison remain blocked. The user
reaffirmed that the storefront must look like that exact reference. The current
original palette, iconography, hero illustration, promotional copy and structural
details are **provisional and unverified against Zilly Home 01**. They do not
constitute visual acceptance or an approved substitute. Reference captures and
a working browser are required before correcting and accepting visual fidelity.

### Local preview asset setup

For the standard `python manage.py runserver` command, set `DJANGO_DEBUG=true`
in this checkout's ignored `.env` so Django serves app static assets locally.
When this feature worktree uses the development database, set its local
`MEDIA_ROOT` to the development checkout's existing absolute media directory;
otherwise existing database photo paths refer to files absent from this worktree.
Do not change independent QA media configuration. Restart runserver after changing
`.env`. These local settings are not production deployment configuration.

The user's unstyled preview was traced to DEBUG=false and a missing worktree
media directory. Corrected the ignored local settings and restarted the local
server. Direct requests returned 200 for `/`, `/static/catalog/storefront.css`,
`/static/catalog/market-basket.svg`, and three existing category photo endpoints.
No QA process was started and no visual/reference match is claimed by these
asset checks. Browser runtime still reports no connected browser.
