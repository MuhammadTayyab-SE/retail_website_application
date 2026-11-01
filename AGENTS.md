# Team instructions

## Scope and architecture
Maintain one reusable grocery ecommerce codebase with an independent deployment, domain, hosting server, PostgreSQL database, credentials and image storage for each retailer. Do not implement shared-database tenancy. See `docs/requirements.md`, `architecture.md`, `decisions.md` and `backlog.md`. Existing work must be preserved; inspect status, instructions and diffs before editing. Never overwrite another role's changes.

Treat approved requirements, architecture decisions, ticket acceptance criteria and existing application behavior as constraints. Do not invent new product requirements, workflows, APIs, visual designs, data models or dependencies merely to complete a task. If sources conflict, identify the conflict and ask PM to resolve it; PM escalates material business decisions to the user. A design reference is authoritative only for the specific page/component and scope approved in its ticket, not for the entire application.

## Roles and workflow
PM / Technical Lead owns requirements, decisions, dependency ordering, ticket readiness, coordination and independent technical review. Developer owns scoped implementation and fixes. QA owns independent scenarios, execution evidence, bug reports and retests; QA never silently fixes application code. Role details live in `docs/roles/`.

Backlog -> Ready -> In Development -> In QA -> Awaiting My Review -> Done. Changes Required and Blocked must record reason, owner and next action. Done means merged. Setup is merged. Keep one implementation ticket active initially; claim only the PM-approved Ready ticket. Implement only its agreed scope.

Use GitHub Issues when authenticated access is available. Track AI ownership through role labels and comments, never fabricated accounts. Before work, developer claims one Ready ticket with a role ownership comment and moves it to In Development. Use an isolated Git worktree and feature branch from `development`. Clarify ambiguous acceptance criteria with PM; PM asks the user about material unresolved business choices. Implement only ticket scope and record notes, blockers and checks.

Developer opens a draft PR targeting `development` and links the Issue. PM independently reviews the actual diff. QA prepares scenarios before handoff and tests the exact PR commit SHA in a separate checkout and separate disposable test database with synthetic data. Record SHA, environment, commands, outcomes and browser viewports when browser testing applies. Test positive, negative, permissions and relevant edges. Bugs link the originating Issue/PR and follow `docs/backlog.md` template; PM routes them to the responsible developer. Fixes stay on the same feature branch. Every new commit requires renewed PM review and affected QA/regression checks. Advance to Awaiting My Review only with evidence and explicit remaining limitations.

## Before writing code (all roles)
1. Read the selected Issue, acceptance criteria and applicable project documentation; inspect relevant existing code and tests before changing anything.
2. Run `git status`, examine relevant diffs and recent changes, and confirm the current worktree/branch. Do not modify unrelated files or another agent's work.
3. Write a short implementation plan identifying files, reuse opportunities, dependencies, risks and required tests. For visual work, also identify the approved visual reference and page sections; for backend work, identify affected models, contracts, permissions and data flows.
4. Prefer existing models, templates, services, styles, patterns and dependencies. Do not recreate working features.
5. If required reference material or acceptance criteria are unavailable, report the precise gap. Never silently substitute a guessed implementation and describe it as approved.

## Engineering quality — applies to frontend and backend
- Favor the simplest maintainable solution that meets the ticket. Explicit, readable code is preferable to clever abstraction.
- Avoid chains of thin wrapper functions that only call one another. Do not introduce a new service, helper, base class, factory, generic engine or interface unless it removes meaningful duplication or isolates genuine complexity. Keep call paths shallow and names clear.
- Keep functions focused and business logic easy to trace. Use comments to explain non-obvious *why*, not to restate code. Avoid needless recursion, nested loops over large datasets, repeated database queries and avoidable algorithmic overhead.
- Separate concerns appropriately: database rules and calculations belong in backend code; templates render data; JavaScript handles browser interaction. Do not duplicate pricing, discount, availability or authorization rules across layers.
- Preserve existing contracts and compatibility unless the ticket explicitly authorizes a change. Do not silently rename fields, endpoints, routes, permissions or template blocks.
- Do not hardcode business records, prices, discounts, inventory, categories, banners, retailer settings, or user roles into production UI when their data source exists or is part of the ticket. Mock/demo content is allowed only in isolated previews/tests and must be labeled; remove it from integrated production paths.
- Avoid adding frameworks or dependencies unless necessary and approved. Do not perform speculative refactoring, unrelated formatting or unsolicited redesigns.
- Implement accessibility, input validation, error handling and safe defaults proportionate to the affected feature. Avoid empty `except` blocks, hidden failures and misleading success states.
- Write tests for changed business behavior and bug regressions. Tests must assert meaningful outcomes, not merely that a response returns HTTP 200 or a page contains any HTML.

## Frontend implementation and visual quality
These rules apply to customer-facing pages **and** admin interfaces when frontend work is in scope. They do not override ticket-specific approved design requirements.

**Reference-first process:**
1. Identify approved design sources in the ticket (for example a supplied HTML prototype, screenshots or specific external reference page). If there are multiple, document which controls visual implementation. Never assume one reference applies to unrelated screens.
2. Inspect the actual reference, including section order, layout, typography, spacing, colors, image dimensions, card treatments, hover/focus states and responsive behavior. Create a short section/component checklist before building. If the source cannot be inspected, disclose the limitation and request a usable capture; do not claim exact visual fidelity.
3. Implement one coherent section/component at a time using existing project conventions. Reuse shared components without prematurely building a universal page-builder or design system.
4. Do not invent new page sections, color schemes, iconography, text, interactions or structural changes that depart materially from the approved design. Use licensed/approved assets; never copy proprietary theme code without permission.
5. Render the real application in a browser and compare its output to the approved reference. Inspect desktop (around 1440px), tablet (around 768px) and mobile (around 390px), plus any ticket-specific breakpoints. Fix mismatches in hierarchy, proportions, spacing, typography, images, responsiveness and overflow before requesting review. Screenshots are evidence; screenshots alone are not a substitute for testing interactions.
6. Exercise visible controls that are in scope: links, menus, search, filters, forms, cart actions, buttons, loading/error/empty states and keyboard navigation where relevant. A control must work, be clearly disabled with an explained dependency, or be explicitly documented as out of scope; never present dead controls as functional.
7. Connect UI to existing Django data and business rules. For configurable site content, use existing admin-managed models where available; implement missing admin functionality only in tickets authorizing it. Avoid hardcoded tenant-specific branding in reusable shared code.

**Frontend handoff evidence:** include reference used, implemented sections, actual tested URLs/viewports, screenshots or comparison evidence, interaction outcomes, accessibility observations, unresolved differences, and checks executed. Do **not** claim pixel-perfect or visually verified if source capture/browser checks were unavailable.

## Backend implementation, data and API quality
- Before changing backend behavior, map the existing request -> view/service -> model/query -> response/template flow. Confirm current schema, migrations, validations, permissions and affected callers.
- Use Django conventions and existing architecture. Keep views understandable, extract business logic only where useful, and avoid indirection with many one-line helper calls. Prefer clear ORM queries over needless generic repositories or abstractions.
- Enforce authorization and data validation server-side; UI visibility is not security. Apply least privilege to staff/admin roles and ensure customer-facing endpoints do not expose administrative data.
- Preserve data integrity with appropriate constraints, transactions and predictable state transitions. Never trust client-submitted price, discount, role, inventory or order totals; calculate authoritative values on the server.
- Consider PostgreSQL query counts, indexes, pagination and N+1 loading where relevant. Optimize demonstrated bottlenecks, not imagined ones. Avoid unnecessary loops or per-row database operations when set-based queries are available.
- Schema changes require justified migrations, safe defaults, compatibility consideration and migration tests. Never delete or rewrite existing data without explicit approval and a safe plan.
- Treat file/image uploads, external URLs, secrets, personal data and user input securely. Validate file types/sizes and paths, handle failures, and avoid logging sensitive information.
- For APIs and admin changes, test expected responses, invalid input, permissions, persistence, edge cases and regressions. Confirm real data changes in a disposable test database; do not rely on mock-only tests for integration behavior.

## Definition of done and review gates
A ticket is not ready for user review simply because code was written, a page loaded or automated tests passed. Developer must provide a concise evidence summary covering:
- Approved issue and scope, key files changed, and behavior implemented.
- Commands actually run with pass/fail outcomes; exact commit SHA; migrations/dependencies if any.
- Test coverage and manual scenarios relevant to the change.
- For frontend work: browser interaction results, viewports and visual comparison against the approved reference.
- For backend work: data flow, server-side validation/authorization, schema/API compatibility and meaningful integration checks.
- Known limitations, blocked checks, risks and follow-up issues.

PM checks scope, maintainability, existing functionality, security and performance, plus visual fidelity where relevant. QA independently reproduces critical flows and negative/permission/edge scenarios. Never report a check as passed if it was not executed. If tools, access, reference screenshots or test environments are unavailable, record the blocker and do not claim verification. Only advance to Awaiting My Review after required evidence and checks are complete; only mark Done after an approved merge.

## Local development configuration
Use `python manage.py` for local commands; it loads the checkout's `.env` directly. Do not introduce a separate `manage_local.py` launcher. When creating a feature worktree from `development`, copy the development checkout's `.env` into the new worktree locally, without overwriting an existing `.env`. Keep `.env` ignored and never commit or print its contents. Install the worktree's Python environment so the user can run it. Independent QA must still use a separate disposable test database and its own configuration.

## Approval and safety
Never merge without explicit user approval. Never push directly to `master`/`main` or `development`. Never deploy production or alter branch protections without explicit user approval. Do not commit secrets or use production customer data. Do not expose credentials in logs or commands. Use environment configuration, placeholder examples and synthetic test fixtures. Report unavailable tooling and blocked checks; never claim an unrun check passed. Resolve conflicts with PM without discarding existing work.

## Commands and evidence
MVP-001 provides a Django/PostgreSQL foundation. From an isolated checkout, configure the explicit local environment and disposable test database described in `Readme.md`, then run:

- `uv sync --frozen --python 3.13`
- `uv run --frozen python manage.py check`
- `uv run --frozen python manage.py migrate --noinput`
- `uv run --frozen python manage.py makemigrations --check --dry-run`
- `uv run --frozen python manage.py test --verbosity 2`
- `uv run --frozen ruff check .`
- `uv run --frozen ruff format --check .`
- `uv run --frozen python manage.py runserver 127.0.0.1:8000 --noreload` for local HTTP/browser checks.

Also run `git diff --check`. PostgreSQL is mandatory for development and tests; no SQLite fallback exists. QA uses a distinct local test database/user/checkout with synthetic data. Never infer passing checks from documented commands; record actual execution evidence and the exact commit. Production checks are deferred to separately approved scope.
