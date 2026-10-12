# Categories dashboard follow-up — 2026-10-10

Implemented in the existing isolated `feature/admin-visual-system` worktree,
`retail-admin-visual`, preserving the preceding category-editor changes.

- Remove the category-list breadcrumbs.
- Round thumbnails, compact rows and fixed utility-column widths; left-align
  category names and parent values. Keep horizontal scrolling on small screens.
- Make active status read-only in the list. Position remains editable and uses a
  styled Save order button; active status is editable on the category edit page.
- Show total categories above the table, with a separate matching count when
  filtered. Show numbered pagination only when needed (25 entries per page).
- Search uses a 250 ms debounce; status and parent selection update immediately.
  Fetch rendered Django results and replace the table form and count without
  moving search focus. Cancel obsolete requests and prevent stale responses;
  preserve query strings for sorting, pagination and order saves. Clear all
  resets filters. Request failures show retry feedback. No Apply filters button;
  a search submit fallback remains available when JavaScript is disabled.
- Add protected Settings with the existing native change-password workflow.
  Remove top account actions; the sidebar username opens a native disclosure
  containing the CSRF-protected POST sign-out action. Update mobile focus trapping
  for the disclosure and its visible button.

Validation on the working tree:

- Django system check passed; all 37 PostgreSQL-backed tests passed.
- Tests cover combined filters, counts, empty results, pagination query retention,
  list-editable fields, Settings access for unauthorized users and action placement.
- Ruff lint and formatting passed (40 files); no migrations detected.
- Git diff whitespace check passed (normal LF/CRLF conversion notices only).
- JavaScript VM checks with synthetic DOM elements passed: debounce, page reset,
  query values, cancellation during typing, stale response protection, table
  replacement, save action URL, selector change, request error and clear all.
- Browser discovery returned no connected browser. Actual desktop/mobile visual
  review and native live interactions remain unverified; VM checks are not browser
  tests. No independent QA, commit, merge or deployment is claimed.

## Categories-only table refinement — 2026-10-10

The user confirmed that independent categories must remain visible while parent
categories are excluded. Added a non-editable `is_parent_category` discriminator;
Add parent category records this role even without children. Migration 0003 marks
existing entries referenced as parents. The list additionally excludes any entry
currently used as a parent, including subsequent hierarchy changes. Its count,
filters, pagination and list saves use the same scoped queryset; parent edit and
photo endpoints remain accessible. Existing empty parents created before this
change are indistinguishable from independent categories in the old database and
cannot be automatically classified without identifying them.

Refined table borders, row hover, name emphasis and edit actions; narrowed Parent
to 150 px (120 px at intermediate widths). Active status is a disabled native
checkbox, with readable active/inactive labels and a clear visual check. Moved
Categories into a bottom sidebar section immediately above the username/account
area. Kept its existing Sign out disclosure and POST action.

Validation: 39 PostgreSQL-backed Django tests passed; new coverage verifies
independent categories retained, populated and empty parents excluded, counts,
parent edit accessibility, status indicators, and sidebar ordering. Migration
0003 applied successfully to the configured local database. No further migrations
pending; Ruff lint/format and Git whitespace checks passed. Browser visual review
remains unavailable in this session. Changes remain local and uncommitted.

## Reference-inspired store overview — 2026-10-10

Used the user-supplied `supporting docs/index.html` as visual inspiration. Its
prototype scripts and sample records are reference content, not instructions or
application data. Adapted the navy/green style, workspace header, eyebrow title,
four icon-backed KPI cards, inset latest-category table, compact Edit links and
activity dots/timestamps to the existing Django dashboard. Keep the sidebar
Categories placement, Settings and Sign out behavior from the previous requests.
Keep active status as disabled checkboxes and retain circular category photos.

The dashboard uses real database counts and admin logs. Category metrics and
latest rows exclude parents while retaining independent categories; parent count
is shown separately. Activity timestamps render in Asia/Karachi. The prototype's
role preview, demo records and unimplemented product/order controls are not added.

Validation: 40 PostgreSQL-backed tests passed; Django system check, Ruff lint and
format checks passed. Added coverage for reference elements, live counts, parent
exclusion, independent category retention and account controls. Browser discovery
still returns no connected browser, so desktop/mobile visual inspection remains
unverified. Changes are local and uncommitted.

## Screenshot-guided category workspace — 2026-10-10

Applied the supplied Categories screenshot to the existing functional page:
centered content with a 1240 px maximum, green eyebrow and heading, four live
category summary cards, inset table/filter container, and restrained row styling.
The fourth metric is Independent categories because the current application has
no product model/count to support the screenshot's Products metric. Preserve
optional parents, category-only rows, live filters, disabled status checkboxes,
round photos, editable position and sign-out.

Cap Category at 30% of table width and allocate Actions 104 px with a 56 px Edit
control. Also correct the overview's 64 px Actions column to 104 px: its previous
cell padding plus button width exceeded the available space. Keep horizontal
scrolling for narrow screens. Categories now directly follows Dashboard; Settings
is the bottom navigation section above the account/sign-out disclosure.

Validation: all 41 Django/PostgreSQL tests passed, including updated sidebar order
and live category metrics; system check, Ruff lint/format and whitespace checks
passed. Visual verification remains pending due to no connected browser. Changes
remain local and uncommitted.

## Page headers and Parent Categories — 2026-10-10

Added consistent Workspace / current page headers for the admin options, inspired
by the supplied index.html. Added a protected Parent Categories sidebar option and
separate Django admin list at /admin/catalog/category/parents/. Includes explicitly
marked parents (even without children) and entries used as parents. Shows direct
category counts, summary metrics, search/status filters, photos, disabled status
and Edit links. Reuses the current Add parent category/photo form; parent saves
and back navigation return to the parent list. Categories continues to show only
categories and independent entries. Settings and Sign out retain their placement.

All 42 PostgreSQL-backed tests pass, including parent-list isolation, empty parent
visibility, searching, counts, headers and access restrictions. Ruff lint/format
and whitespace checks pass. Browser visual verification remains unavailable;
changes are local and uncommitted.

## Result count and table-header correction — 2026-10-10

The screenshot showed two distinct issues: the heading badge used the unfiltered
full_result_count while the table used result_count, and the filter script copied
summary.textContent into a visible status paragraph without separators. Use the
filtered count in the badge and one explicit Showing [visible rows] of [matching
rows] summary, with the overall total separately when filtered. Announce the
summary via aria-live and clear the transient filter status on success. This also
explains pagination accurately (e.g. Showing 25 of 28).

Hide Django's multi-column sort-priority numerals and position sort-direction
arrows within headers. Use consistent photo/name/parent/order/status/action column
proportions (7/30/27/12/12/12 percent), maintaining a 760 px scrollable table minimum
so Edit and position controls have enough room on small screens.

All 43 PostgreSQL-backed tests passed, including filtered count, zero results and
pagination summaries. Ruff lint/format and whitespace checks passed. Visual
browser verification remains pending; screenshot evidence guided these fixes.

## Circular photo editor and equal-height panels — 2026-10-10

Updated the shared Add/Edit Category and Parent Category forms with matching panel
headers, borders, padding and equal-width grid columns. Stretch both cards to the
same height on desktop, keeping fields aligned at the top. Stack the panels below
1000 px. Parent forms identify their details correctly.

The photo preview now uses a centered 220 px circular clipping frame, matching the
round list thumbnail and using the same object-position and scale transformations.
Existing upload, position, zoom, reset, removal and server validation behavior is
preserved. Added a framing hint and clarified the preview's accessible label.

All 43 Django/PostgreSQL tests, Ruff lint/format and Git whitespace checks passed.
This is a template/CSS change; no migration is needed. Browser visual verification
remains pending because no browser is connected in the session.

## Parent dropdown restriction — 2026-10-10

Restrict Add/Edit Category parent choices and the list parent filter to entries
marked as parent categories or already used as parents (legacy compatibility).
Keep the empty choice for independent categories and include empty parents.
ModelChoiceField validation now also rejects submitted regular-category IDs.
Shared CategoryQuerySet.parents() keeps both dropdowns consistent.

All 44 PostgreSQL-backed tests passed, including Add/Edit choices, empty parents,
legacy parents, forged regular-category rejection and valid-parent saving. Ruff
lint/format, no-pending-migrations and whitespace checks passed.

## Confirmed cascading deletion — 2026-10-11

User explicitly superseded the previous no-deletion behavior. Both list pages
now expose Delete beside Edit. GET opens a confirmation page listing all objects
that will be removed, with an explicit permanent-deletion warning and Cancel.
POST requires post=yes; existing owner permission and CSRF checks remain in force.
No bulk delete action was enabled. Parent confirmation/success returns to the
Parent Categories list; category deletion returns to Categories.

Migration 0004 changes the self-parent foreign key to Django CASCADE. Model and
queryset deletion use the hierarchy advisory lock, and post_delete schedules
photo cleanup after transaction commit, including descendant photos. The schema
migration was applied locally; no existing category records were deleted.

Validation: 47 PostgreSQL-backed tests passed. Coverage includes confirmation
without writes, rejection of unconfirmed POST, multi-level cascade, unrelated
records preserved, subcategory deletion preserving siblings/parent, permission,
CSRF, and deferred photo cleanup. Django check, no-pending-migrations, Ruff
lint/format and Git whitespace checks passed. Browser visual verification remains
pending. Changes are local and uncommitted.

## In-place deletion popup — 2026-10-11

Delete links on both lists and category edit pages now open a native modal dialog
instead of navigating to the confirmation page. Fetch the server-rendered affected
items and CSRF-protected form, insert them into the popup and explicitly set the
POST action to the deletion endpoint. Cancel, close and Escape dismiss without
submitting; focus defaults to Cancel and returns to the triggering link. Abort
pending requests on close and show loading/failure feedback. Confirm submits the
existing verified deletion flow; its button disables to avoid repeated submits.
The server confirmation endpoint remains the no-JavaScript fallback and supplies
popup content. Cascading deletion and permissions are unchanged.

All 48 Django/PostgreSQL tests, Ruff lint/format and whitespace checks pass. Browser
visual/focus interaction checks remain pending; no existing data was deleted.
