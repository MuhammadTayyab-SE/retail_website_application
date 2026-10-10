# Category editor fixes — 2026-10-10

User-requested follow-up to the category-photo editor in the existing isolated
`retail-admin-visual` checkout, branch `feature/admin-visual-system`.

- Add parent category opens a dedicated independent-parent form without a parent
  selector. Submitted parent IDs cannot attach that new entry to another category.
- Add category keeps the parent optional and explains the independent option.
  Both flows use the existing Category model; no new category types or migration.
- Stack editor labels and controls within a responsive two-column layout, with
  clearer headings, navigation and photo actions.
- Render the photo initialization script with the form rather than requiring a
  separate static request. This removes a failure point when local static assets
  are unavailable (especially DEBUG=false). No live-browser reproduction was
  possible; this is the identified dependency and corrective change, not a
  confirmed browser diagnosis.
- Accept supported image extensions when the browser supplies no MIME type;
  server-side Pillow validation remains authoritative. Show image-load failures.

Validation on the working tree:

- `.venv/Scripts/python.exe manage.py check`: passed.
- `.venv/Scripts/python.exe manage.py test --verbosity 1`: 34 passed using the
  configured PostgreSQL test database. Includes both creation flows, optional
  parenting, forged parent submission and embedded preview initialization.
- `.venv/Scripts/python.exe manage.py makemigrations --check --dry-run`: no changes.
- `.venv/Scripts/ruff.exe check .`: passed.
- `.venv/Scripts/ruff.exe format --check .`: 39 files already formatted.
- `git diff --check`: passed (Git reports normal LF/CRLF conversion notices).
- JavaScript VM checks with synthetic DOM elements: selection and preview,
  position, zoom, reset, removal, missing MIME, invalid type, oversized input,
  image-load failure passed. These are logic checks, not a browser render test.

Browser skill setup returned no available browser; discovery returned an empty
list. Desktop/mobile visual review and actual native file-selection checks remain
unverified. No independent QA, merge or deployment is claimed. Changes are local
and uncommitted for review.
