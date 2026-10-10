# ADMIN-UI-001 — Administration visual consistency

User authorized the complete admin visual update and independent QA/developer issue
workflow. Backlog: https://github.com/MuhammadTayyab-SE/retail_website_application/issues/22 .
State: In Development. User requested a further visual revision first; QA is deferred.
Branch: `feature/admin-visual-system`, checkout: `retail-admin-visual`, baseline `9038b9f`.

## Scope and implementation

The login-only customization was followed by stock Django authenticated screens.
The shared `admin/base_site.html` now applies the retail brand, navigation, footer
and embedded style tokens to dashboard, app overview, category lists/filters/search,
add/edit forms, validation/messages, history, password change and logout.
The dashboard has actual category aggregates, latest categories, real admin activity,
empty states and working category links. No sales/order/product features are invented.

Native Django forms, formsets, scripts, related-object popups and sidebar filter/toggle
remain in use. The sidebar is supplemented with mobile-accessible header navigation.
The shared theme is intentionally light, matching the reference and custom login.
Original grocery artwork is reused; no licensed theme assets are copied.

`LOGIN_REDIRECT_URL` now resolves to the admin index, fixing the previously failing
owner login POST without `next` while Django continues validating explicit targets.

## Run locally

The worktree has its own installed `.venv` and an ignored local copy of development's
`.env`. No `manage_local.py` exists or is needed. Existing databases are preserved.

```powershell
Set-Location 'D:\Projects\Retail Website\retail-admin-visual'
.venv\Scripts\python.exe manage.py check
.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8011 --noreload --insecure
```

Open http://127.0.0.1:8011/admin/ and use your existing local owner account.
`--insecure` serves Django's existing widgets/scripts for local DEBUG=false review
only. The shared theme CSS is embedded, but native Django scripts/static assets
must still be served normally in deployment. No production deployment is performed.

## Historical developer validation (before the latest visual revision)

- Frozen offline dependency install with Python 3.13.14: passed.
- Django system check: passed.
- Full PostgreSQL suite: 31 tests passed with a uniquely named disposable test
  database; Django destroyed that database afterward. Existing test databases were
  not overwritten. Includes login/logout/CSRF/permissions, category rules and new
  integration checks across dashboard/list/add/edit/history/password/logout.
- Dashboard integration verifies real aggregates and HTML escaping; invalid category
  submission retains error feedback and does not write an invalid category.
- Migration dry-run: no changes detected.
- Ruff lint/format and diff checks: passed.

## QA defects and acceptance

- QA-ADMIN-001: source-confirmed stock authenticated theme after custom login.
  Developer fix: shared shell, navigation, dashboard and management/account styling.
  Visual retest remains pending browser screenshots.
- QA-ADMIN-002: owner login without next redirects to `/accounts/profile/` (404).
  Developer fix: explicit admin fallback. Existing regression now passes.
- QA-ADMIN-003: no browser connected. Independent QA confirmed the runtime returns
  no browser; desktop/mobile screenshots, focus/navigation interaction and password
  toggle visual checks cannot be claimed passed.

Independent QA must use the exact candidate commit in a separate checkout, with
its own disposable PostgreSQL role/database and synthetic data/media. QA findings,
fix references and actual retest results will be attached to Issue #22 and the draft
PR. No visual acceptance, independent PM signoff, merge or deployment is claimed.

## Visual revision ? 2026-10-10

Continues in the same retail-admin-visual checkout, feature/admin-visual-system branch and PR #25. The developer strengthened the grocery green/yellow identity, redesigned the dark green navigation and dashboard banner, enlarged reading/control sizes, and refined list search/actions/filters, forms, account screens and login. Native Django behavior is retained.

QA is deferred at the user's request. Earlier 31-test/44-HTTP results apply to the previous candidate only and do not validate this revision. Developer syntax/system checks will be recorded separately; no screenshots or visual acceptance are claimed.

Latest revision developer checks: `manage.py check` passed (0 issues); six shared/login/dashboard templates compiled via `manage.py shell`; `git diff --check` passed. No regression suite, browser session, screenshot checks or independent QA were run for this revision.

Developer checks for this revision: Django system check passed with zero issues; six affected templates compiled successfully through manage.py; git diff --check passed. No QA/regression suite or browser visual checks were run for this revision.
