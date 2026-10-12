# Admin login design

User requested a redesigned `/admin/` login inspired by the Zilly grocery theme:
https://www.radiustheme.com/demo/wordpress/themes/zilly/

Implementation is isolated in `retail-admin-login`, branch `feature/admin-login-design`,
rebased onto merged development commit `f279dde`. Only the login design, focused
regression test and these notes are included; local launcher changes are excluded.
This directly authorized follow-up is limited to the login page. No merge or deployment.

The live demo returned HTTP 403. Zilly's public theme previews informed the green,
yellow and white grocery palette. The layout and SVG grocery illustration are original;
no theme assets or third-party fonts are required. The responsive split layout collapses
to a compact welcome banner and login form on mobile. CSS is included server-side so
the login page remains styled when local Django static serving is unavailable.

Django's authentication form, owner-only policy, CSRF, field/non-field errors,
escaped username values and hidden next target remain in use. Password visibility
is an optional progressive enhancement. Password reset appears only when its actual
URL is configured. No signup, remember-me or unsupported backend features were added.

## Run locally

This checkout has its own installed `.venv` and an ignored, configured `.env`.
An existing configured `.env` is preserved. Future feature worktrees should receive
an ignored copy of development's `.env` when created, per the user's instruction.

GitHub development does not yet contain the separate automatic `.env` loading fix.
Use uv's environment-file support without adding a separate Python launcher:

```powershell
Set-Location 'D:\Projects\Retail Website\retail-admin-login'
uv run --frozen --env-file .env python manage.py migrate --noinput
uv run --frozen --env-file .env python manage.py runserver 127.0.0.1:8010 --noreload
```

Open http://127.0.0.1:8010/admin/ . Stop any existing preview before starting
runserver on the same port. Login styling is embedded and needs no static server.

## Verification

- Frozen offline dependency install with Python 3.13.14: passed.
- Django system check: passed using explicit synthetic local configuration.
- Four AdminPolicyTests, including custom template errors, escaping, CSRF and next
  target: passed; no database used by these tests.
- Ruff lint and formatting: passed.
- `git diff --check`: passed.
- Live HTTP smoke check: `/admin/` redirected to the custom login and returned 200;
  `/admin/login/?next=/admin/` returned 200. Embedded styles, password and CSRF
  fields were present, with no external stylesheet dependency.
- Migration dry-run: no changes; PostgreSQL history check warned that the synthetic
  preview user could not authenticate.
- Refreshed checks after rebasing onto development: Django check, four login policy
  tests, migration dry-run, Ruff lint/format and diff checks passed using configured
  local `.env` via uv.
- Full PostgreSQL regression suite on a newly named disposable database: 23 of 24
  tests passed; the database was destroyed afterward. Existing test
  `AdminAccessTests.test_owner_login_and_post_logout` fails because a POST without
  `next` redirects to `/accounts/profile/` (404). The same failure was observed on
  development before this login PR. This PR does not change authentication redirects.
- Browser runtime connected-browser list is empty. Desktop/mobile screenshots and
  JavaScript interaction checks were not run.

No remote issue transition, draft PR or independent QA is claimed.
