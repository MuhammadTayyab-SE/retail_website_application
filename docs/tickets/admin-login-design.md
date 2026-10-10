# Admin login design

User requested a redesigned `/admin/` login inspired by the Zilly grocery theme:
https://www.radiustheme.com/demo/wordpress/themes/zilly/

Implementation is isolated in `retail-admin-login`, branch `feature/admin-login-design`,
based on `8684815`. The original checkout and its modified AGENTS.md are preserved.
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

This checkout has its own installed `.venv` and an ignored copy of the original `.env`.
The original DB settings contain placeholders. Configure this checkout's local
PostgreSQL credentials, then run in PowerShell:

```powershell
Set-Location 'D:\Projects\Retail Website\retail-admin-login'
.venv\Scripts\python.exe manage_local.py migrate --noinput
.venv\Scripts\python.exe manage_local.py runserver 127.0.0.1:8010 --noreload
```

For an immediate visual review, an ignored local helper serves the real Django WSGI
application without the development server's startup migration probe:

```powershell
.venv\Scripts\python.exe .local\preview_admin.py
```

Open http://127.0.0.1:8010/admin/ . The helper supplies synthetic preview values only
for placeholder DB settings; it does not create a database, bypass authentication,
or enable successful sign-in without valid PostgreSQL credentials. Stop the preview
before starting runserver on the same port.

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
- Full PostgreSQL authentication tests and migrations remain blocked by placeholder
  local database configuration. No successful sign-in is claimed.
- Browser runtime connected-browser list is empty. Desktop/mobile screenshots and
  JavaScript interaction checks were not run.

No remote issue transition, draft PR or independent QA is claimed.
