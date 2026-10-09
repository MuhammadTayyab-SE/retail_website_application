# Grocery application foundation

Python 3.13, Django 5.2 LTS and PostgreSQL 17+ are required. `/admin/` provides owner-only category management; `/categories/` lists active category paths. GET/HEAD `/health/` is process liveness only, independent of database availability: JSON `{"status":"ok"}`, Cache-Control no-store. Other health methods return 405; root and product routes return 404.

## Install and configure (PowerShell)

From this checkout, with uv and Python 3.13 available:

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

Lock pins Django 5.2.18 and dependencies. `.env.example` contains placeholders only; `.env` is not automatically loaded. Missing/blank/placeholder required values and malformed settings fail without echoing values. Secret keys need 50 characters; DEBUG is explicitly true/false; hosts exclude wildcards/ports; ports use ASCII integers 1–65535. Database names use lowercase ASCII letters/digits/underscores, begin with a letter, and have <=63 characters; system databases are rejected. Test name starts test_ and differs from development. Use synthetic local data, never production credentials/data.

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

Open `http://127.0.0.1:8000/admin/`. Only active staff superusers can log in or access
admin operations. Logout uses the admin's POST form. No default account/password is provided.
For local admin CSS with `DJANGO_DEBUG=false`, first run `uv run --frozen python manage.py collectstatic --noinput`
and use `uv run --frozen python manage.py runserver 127.0.0.1:8000 --noreload --insecure`.
The `--insecure` flag is for local static asset serving only, never production. Alternatively,
set `DJANGO_DEBUG=true` for local development. Keep explicit allowed hosts configured.

Under Catalog > Categories, create names (up to 100 characters), optionally select a parent,
set sibling position (lower first) and toggle Active. Names are unique across the hierarchy,
ignoring case and surrounding whitespace. Cycles and negative positions are rejected.
Deleting categories is disabled; deactivate instead. An inactive parent hides all descendants
from `http://127.0.0.1:8000/categories/`, without changing their own active flags.
The public page includes an empty state; products and storefront styling are later tickets.

The implementation is in the isolated `retail-mvp-003-004` checkout on
`feature/mvp-003-004-admin-categories`. The main checkout remains unchanged until review/merge.
See [implementation and validation notes](docs/tickets/MVP-003-004.md).

Pure environment tests can run without a database: `uv run --frozen python -m unittest tests.test_foundation.EnvironmentTests -v`. This does not validate HTTP or PostgreSQL. Full tests include real PostgreSQL test-database verification and transaction rollback.

## Foundation validation history

Frozen dependency installation, Django system check, five pure configuration tests and lint/format checks ran successfully. Windows Application Control blocks both local PostgreSQL initdb and the psycopg binary DLL on this workstation; approved PostgreSQL and psycopg/libpq runtimes are required. Database migration/full Django tests and the documented runserver migration probe are blocked, not passed. Independent QA exercised the normal config.wsgi application through stdlib wsgiref without backend alterations: 11 HTTP scenarios passed on the prior candidate. This commit requires renewed QA; no browser result is claimed here. Do not bypass host controls or replace PostgreSQL with SQLite/cloud. See docs/tickets/MVP-001.md for evidence.
