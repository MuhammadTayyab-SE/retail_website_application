# Team instructions

## Scope and architecture
Maintain one reusable grocery ecommerce codebase with an independent deployment, domain, hosting server, PostgreSQL database, credentials and image storage for each retailer. Do not implement shared-database tenancy. See docs/requirements.md, architecture.md, decisions.md and backlog.md. Existing work must be preserved; inspect status, instructions and diffs before editing. Never overwrite another role's changes.

## Roles and workflow
PM / Technical Lead owns requirements, decisions, dependency ordering, ticket readiness, coordination and independent technical review. Developer owns scoped implementation and fixes. QA owns independent scenarios, execution evidence, bug reports and retests; QA never silently fixes application code. Role details live in docs/roles/.

Backlog -> Ready -> In Development -> In QA -> Awaiting My Review -> Done. Changes Required and Blocked must record reason, owner and next action. Done means merged. Setup is merged. Keep one implementation ticket active initially; claim only the PM-approved Ready ticket. Implement only its agreed scope.

Use GitHub Issues when authenticated access is available. Track AI ownership through role labels and comments, never fabricated accounts. Before work, developer claims one Ready ticket with a role ownership comment and moves it to In Development. Use an isolated Git worktree and feature branch from development. Clarify ambiguous acceptance criteria with PM; PM asks the user about material unresolved business choices. Implement only ticket scope and record notes, blockers and checks.

Developer opens a draft PR targeting development and links the Issue. PM independently reviews the actual diff. QA prepares scenarios before handoff and tests the exact PR commit SHA in a separate checkout and separate disposable test database with synthetic data. Record SHA, environment, commands, outcomes and browser viewports. Test positive, negative, permissions and relevant edges. Bugs link the originating Issue/PR and follow docs/backlog.md template; PM routes them to the responsible developer. Fixes stay on the same feature branch. Every new commit requires renewed PM review and affected QA/regression checks. Advance to Awaiting My Review only with evidence and explicit remaining limitations.

## Local development configuration

Use `python manage.py` for local commands; it loads the checkout's `.env` directly.
Do not introduce a separate `manage_local.py` launcher. When creating a feature
worktree from development, copy the development checkout's `.env` into the new
worktree locally, without overwriting an existing `.env`. Keep `.env` ignored and
never commit or print its contents. Install the worktree's Python environment so
the user can run it. Independent QA must still use a separate disposable test
database and its own configuration.

## Approval and safety
Never merge without explicit user approval. Never push directly to master/main or development. Never deploy production or alter branch protections without explicit user approval. Do not commit secrets or use production customer data. Do not expose credentials in logs or commands. Use environment configuration, placeholder examples and synthetic test fixtures. Report unavailable tooling and blocked checks; never claim an unrun check passed. Resolve conflicts with PM without discarding existing work.

## Commands and evidence
MVP-001 provides a Django/PostgreSQL foundation. From an isolated checkout, configure the explicit local environment and disposable test database described in Readme.md, then run:

- `uv sync --frozen --python 3.13`
- `uv run --frozen python manage.py check`
- `uv run --frozen python manage.py migrate --noinput`
- `uv run --frozen python manage.py makemigrations --check --dry-run`
- `uv run --frozen python manage.py test --verbosity 2`
- `uv run --frozen ruff check .`
- `uv run --frozen ruff format --check .`
- `uv run --frozen python manage.py runserver 127.0.0.1:8000 --noreload` for local HTTP/browser checks.

Also run `git diff --check`. PostgreSQL is mandatory for development and tests; no SQLite fallback exists. QA uses a distinct local test database/user/checkout with synthetic data. Never infer passing checks from documented commands; record actual execution evidence and the exact commit. Production checks are deferred to separately approved scope.
