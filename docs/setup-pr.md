# Local development scope decisions

Local catalog development should proceed without choosing production hosting or cloud storage. This documentation follow-up records the user's agreed local development/testing scope, local filesystem media and admin-only management. It preserves the eventual independent production domain, server, database, credentials and storage requirements while deferring production implementation details.

PM selects Django admin with one superuser/admin as the technical implementation choice. Anonymous, inactive and non-admin access must be denied. Local retailer instances use distinct ports/local hosts, databases/users, secrets and media roots; QA uses separate test database/media roots. Storage remains configurable for later cloud selection; upload limits remain explicit technical follow-up.

Seven documentation files change: requirements, architecture, decisions, backlog Markdown/JSON, setup report and this PR description. MVP-002, MVP-003, MVP-005 context and MVP-014 now distinguish current local scope from deferred production readiness. All application tickets remain Backlog; no application code is included.

Links: [DOC-001 / #17](https://github.com/MuhammadTayyab-SE/retail_website_application/issues/17); prior setup [PR #16](https://github.com/MuhammadTayyab-SE/retail_website_application/pull/16) is merged. Developer owns docs/local-development-decisions in an isolated worktree, targeting development.

Validation: staged whitespace check and 15-ticket JSON parse ran. Independent QA and PM review must validate the final exact commit before Awaiting My Review. Application/browser/database tests remain unavailable because no scaffold exists. Merge requires explicit user approval; no production or protection changes are included.
