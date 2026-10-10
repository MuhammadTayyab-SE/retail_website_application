# Grocery application foundation

Python 3.13, Django 5.2 LTS and PostgreSQL 17+ are required. `/admin/` provides owner-only category management; `/categories/` lists active category paths. GET/HEAD `/health/` is process liveness only, independent of database availability: JSON `{"status":"ok"}`, Cache-Control no-store. Other health methods return 405; root and product routes return 404.

## Install and configure (PowerShell)

For local development, configure this checkout's ignored `.env` using `.env.example`
as the format reference. `manage.py` automatically loads that file; no separate
launcher or repeated environment setup is needed. Existing process variables take
precedence. Values are literal `KEY=value` entries with optional matching quotes;
full-line comments are supported, but interpolation and inline comments are not.
WSGI/ASGI deployments continue to require explicit process environment configuration.

With an installed project environment and configured local PostgreSQL:

```powershell
.venv\Scripts\python.exe manage.py check
.venv\Scripts\python.exe manage.py migrate --noinput
.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000 --noreload
```

New feature worktrees receive a local copy of development's `.env` without replacing
an existing file. `.env` remains ignored by Git; independent QA still needs separate
database configuration. Never commit credentials.

Alternatively, configure explicit process variables from this checkout, with uv and Python 3.13 available:

```powershell
$env:UV_CACHE_DIR = Join-Path (Get-Location) '.uv-cache'
uv sync --frozen --python 3.13
$env:DJANGO_SECRET_KEY = uv run --frozen python -c "import secrets; print(secrets.token_urlsafe(64))"
$env:DJANGO_DEBUG = 'false'
$env:DJANGO_ALLOWED_HOSTS = 'localhost,127.0.0.1'
$env:DB_HOST = '127.0.0.1'
$env:DB_PORT = '5432'
$env:DB_NAME = 'retail_dev'
$env:DB_TEST_NAME = 'test_retail_dev'
$env:DB_USER = 'retail_dev'
$localPassword = Read-Host 'Local database password' -AsSecureString
$env:DB_PASSWORD = [System.Net.NetworkCredential]::new('', $localPassword).Password
```

Lock pins Django 5.2.18 and dependencies. `.env.example` contains placeholders only; `manage.py` loads the checkout-local `.env` when present, without overriding process variables. Missing/blank/placeholder required values and malformed settings fail without echoing values. Secret keys need 50 characters; DEBUG is explicitly true/false; hosts exclude wildcards/ports; ports use ASCII integers 1–65535. Database names use lowercase ASCII letters/digits/underscores, begin with a letter, and have <=63 characters; system databases are rejected. Test name starts test_ and differs from development. Use synthetic local data, never production credentials/data.

## Initialize local PostgreSQL

Use an approved local PostgreSQL installation or workspace-local binaries; no system service is needed. For a NEW cluster only (preserve existing data), set pgBin to its bin directory:

```powershell
$pgBin = 'C:\path\to\postgresql\bin'
New-Item -ItemType Directory -Force .local | Out-Null
& "$pgBin\initdb.exe" -D "$PWD\.local\pgdata" -U postgres -W --auth=scram-sha-256 --encoding=UTF8
& "$pgBin\pg_ctl.exe" -D "$PWD\.local\pgdata" -l "$PWD\.local\postgres.log" -o '-h 127.0.0.1 -p 5432' start
& "$pgBin\psql.exe" -h 127.0.0.1 -p 5432 -U postgres -d postgres
```

At interactive psql, configure the local application role. The password prompt uses the same local password as DB_PASSWORD:

```sql
CREATE ROLE retail_dev LOGIN CREATEDB NOSUPERUSER NOCREATEROLE;
\password retail_dev
CREATE DATABASE retail_dev OWNER retail_dev;
\q
```

CREATEDB is needed locally for Django to create/drop the disposable test database. QA must use a separate approved cluster or role/development database/test database with synthetic data, separate checkout and test media root. Do not use --keepdb for independent clean validation. No SQLite fallback exists.

## Run and validate

With configuration set and PostgreSQL available:

```powershell
uv run --frozen python manage.py check
uv run --frozen python manage.py migrate --noinput
uv run --frozen python manage.py makemigrations --check --dry-run
uv run --frozen python manage.py test --verbosity 2
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen python manage.py runserver 127.0.0.1:8000 --noreload
```

In another terminal: `Invoke-RestMethod http://127.0.0.1:8000/health/`. Stop server with Ctrl+C; stop your local cluster with `& "$pgBin\pg_ctl.exe" -D "$PWD\.local\pgdata" stop`. Migrations now create Django authentication/session/admin tables and catalog categories. This is local development only; products, cloud and production hardening are future scope.

## Owner login and category management (MVP-003 / MVP-004)

After configuring the environment and running migrations, create your local owner interactively:

```powershell
uv run --frozen python manage.py createsuperuser
uv run --frozen python manage.py runserver 127.0.0.1:8000 --noreload
```

Open `http://127.0.0.1:8000/admin/`. Active staff Super Admins and workers with an
assigned role can sign in. Workers can use only their role's module/action permissions.
Logout uses the admin's POST form. No default account/password is provided.
For local admin CSS with `DJANGO_DEBUG=false`, first run `uv run --frozen python manage.py collectstatic --noinput`
and use `uv run --frozen python manage.py runserver 127.0.0.1:8000 --noreload --insecure`.
The `--insecure` flag is for local static asset serving only, never production. Alternatively,
set `DJANGO_DEBUG=true` for local development. Keep explicit allowed hosts configured.

Under Catalog > Categories, create names (up to 100 characters), optionally select a parent,
set sibling position (lower first) and toggle Active. Names are unique across the hierarchy,
ignoring case and surrounding whitespace. Cycles and negative positions are rejected.
Delete actions require confirmation. Deleting a parent also deletes its subcategories and their photos; deactivate entries when you want to retain them. An inactive parent hides all descendants
from `http://127.0.0.1:8000/categories/`, without changing their own active flags.
The public page includes an empty state; products and storefront styling are later tickets.

The expanded MVP-003 implementation is in the isolated `retail-mvp-003` checkout on
`feature/mvp-003-roles-audit`. See [roles and audit notes](docs/tickets/MVP-003-roles-audit.md)
and the [original implementation history](docs/tickets/MVP-003-004.md).

Pure environment tests can run without a database: `uv run --frozen python -m unittest tests.test_foundation.EnvironmentTests -v`. This does not validate HTTP or PostgreSQL. Full tests include real PostgreSQL test-database verification and transaction rollback.

## Foundation validation history

Frozen dependency installation, Django system check, five pure configuration tests and lint/format checks ran successfully. Windows Application Control blocks both local PostgreSQL initdb and the psycopg binary DLL on this workstation; approved PostgreSQL and psycopg/libpq runtimes are required. Database migration/full Django tests and the documented runserver migration probe are blocked, not passed. Independent QA exercised the normal config.wsgi application through stdlib wsgiref without backend alterations: 11 HTTP scenarios passed on the prior candidate. This commit requires renewed QA; no browser result is claimed here. Do not bypass host controls or replace PostgreSQL with SQLite/cloud. See docs/tickets/MVP-001.md for evidence.

### Local category photos

Run `uv sync --frozen --python 3.13` and `uv run --frozen python manage.py migrate` after pulling the category-photo revision. Photos are stored under `media/categories/` by default; set `MEDIA_ROOT` locally to use another folder. Media stays gitignored. The admin serves images through its authenticated category-photo endpoint, including when DEBUG is false. Upload a JPEG, PNG or WebP up to 8 MB, adjust the square preview and save. The original image is retained; saved position/zoom controls thumbnail display. Removing/replacing a photo deletes the previous local file after a successful save.


### Category administration updates

Run `python manage.py migrate` after pulling to apply migrations 0003 and 0004.
Parent Categories and Categories have separate admin lists. Independent categories
remain supported; parent selectors offer only parent entries. Existing records
used as parents are classified automatically; historical empty parents cannot be
distinguished from independent categories without identifying them.

Search/status/parent filters update the table automatically. Counts distinguish
visible rows, matching rows and the overall total. Status indicators are read-only;
Save order updates positions. Category photos use a circular position/zoom preview
and equal-height desktop panels. Settings contains Change password; the sidebar
account menu contains Sign out.

Delete opens an in-place confirmation popup listing affected items. Confirming a
parent deletion removes all descendants and schedules photo removal after commit.
The server confirmation page remains a fallback when JavaScript is unavailable.

### Workers, roles and activity logs

Run `python manage.py migrate` to apply access migration 0001 and catalog migration
0005. Sign in as your existing Super Admin, open Roles and choose module/action
permissions, then open Workers to create an account and assign its role. Categories
and Parent Categories have separate view/add/change/delete permissions. Workers
without an assigned role cannot sign in. Access changes apply on the next request.

Only Super Admin manages accounts, roles and the Activity log. Passwords are hashed
and never displayed; use Set a new password on an employee account to reset it.
Workers can change their own password in Settings. Deactivate employees rather than
deleting their attribution history. Record history on category forms shows who
created/updated the entry and when; legacy creation values remain unknown.

Product persistence is a later MVP-005 feature and must inherit the provided
attribution foundation. No Product CRUD is introduced by MVP-003.
