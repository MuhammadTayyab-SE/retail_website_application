# Team instructions

## Scope and architecture
Maintain one reusable grocery ecommerce codebase with an independent deployment, domain, hosting server, PostgreSQL database, credentials and image storage for each retailer. Do not implement shared-database tenancy. See docs/requirements.md, architecture.md, decisions.md and backlog.md. Existing work must be preserved; inspect status, instructions and diffs before editing. Never overwrite another role's changes.

## Roles and workflow
PM / Technical Lead owns requirements, decisions, dependency ordering, ticket readiness, coordination and independent technical review. Developer owns scoped implementation and fixes. QA owns independent scenarios, execution evidence, bug reports and retests; QA never silently fixes application code. Role details live in docs/roles/.

Backlog -> Ready -> In Development -> In QA -> Awaiting My Review -> Done. Changes Required and Blocked must record reason, owner and next action. Done means merged. Keep one implementation ticket active initially; setup is the only active ticket until the user reviews this assignment. Never begin application features during setup.

Use GitHub Issues when authenticated access is available. Track AI ownership through role labels and comments, never fabricated accounts. Before work, developer claims one Ready ticket with a role ownership comment and moves it to In Development. Use an isolated Git worktree and feature branch from development. Clarify ambiguous acceptance criteria with PM; PM asks the user about material unresolved business choices. Implement only ticket scope and record notes, blockers and checks.

Developer opens a draft PR targeting development and links the Issue. PM independently reviews the actual diff. QA prepares scenarios before handoff and tests the exact PR commit SHA in a separate checkout and separate disposable test database with synthetic data. Record SHA, environment, commands, outcomes and browser viewports. Test positive, negative, permissions and relevant edges. Bugs link the originating Issue/PR and follow docs/backlog.md template; PM routes them to the responsible developer. Fixes stay on the same feature branch. Every new commit requires renewed PM review and affected QA/regression checks. Advance to Awaiting My Review only with evidence and explicit remaining limitations.

## Approval and safety
Never merge without explicit user approval. Never push directly to master/main or development. Never deploy production or alter branch protections without explicit user approval. Do not commit secrets or use production customer data. Do not expose credentials in logs or commands. Use environment configuration, placeholder examples and synthetic test fixtures. Report unavailable tooling and blocked checks; never claim an unrun check passed. Resolve conflicts with PM without discarding existing work.

## Commands and evidence
Currently no application scaffold, dependency manifest, test runner or CI exists. Available setup checks: `git status --short`, `git diff --check`, `git diff --stat`, and manual cross-document review. A clean diff is not application validation.

Planned Django commands (NOT currently runnable; MVP-001 must confirm exact commands and document environment prerequisites): `python manage.py check`, `python manage.py makemigrations --check --dry-run`, `python manage.py test`, and `python manage.py runserver 127.0.0.1:8000` for local browser validation. Configure a disposable PostgreSQL test database with a distinct non-production database/user and storage before running tests. The implementation ticket must add exact installation, database initialization, test and lint commands and execute them before handoff. Production security checks require production-like synthetic configuration, never real production data.
