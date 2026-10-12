# Setup report

Inspection found no application code: only empty Readme.md and .gitignore were tracked. Existing ignored docs are empty placeholders in the original working directory and are preserved there, including roles/pm-tl.md. The initial setup used an isolated worktree on chore/team-setup; this follow-up uses docs/local-development-decisions from merged development; original work is not overwritten. Existing base branches are development and master, with master as remote default; no main branch exists.

GitHub CLI is absent, but PM verified authenticated REST access through the existing credential manager for MuhammadTayyab-SE, with repository push/admin permission and Issues enabled. PM created 15 remote Issues; returned links are recorded in docs/github-issues.json. Initial setup PR16 is merged; the documentation follow-up PR will be reported after creation. No AI user accounts are invented. Both base branches were observed unprotected; no protections were modified.

The project now defines role boundaries, one-ticket workflow, exact-SHA independent QA, approval gates, requirements, proposed architecture, decisions and a prioritized MVP backlog. Currency PKR is agreed; country, tax, payment and other material choices remain unresolved. Django/PostgreSQL is adopted as the technical baseline because there is no existing application to migrate. No application features, dependencies, database or CI were created.

Zilly was supplied as inspiration but page retrieval failed. No visual assessment or asset reuse is claimed. Setup validation consists of actual document/diff checks and independent QA on the committed SHA; PM records final evidence and remote links after handoff. Application/browser/database validation remains unavailable until a runnable scaffold exists.

## Recommended protections (not applied)
Protect development and master with required PRs, human approval and relevant QA/CI status checks once implemented. Block direct pushes, force pushes and branch deletion; apply administrator restrictions where appropriate. Agree merge strategy and stale-review dismissal for new commits. User approval is required before changing any protection.

## Next work
Setup PR [#16](https://github.com/MuhammadTayyab-SE/retail_website_application/pull/16) is merged; SETUP-001 is Done. This follow-up must be reviewed and merged only after explicit user approval. Recommended first implementation is MVP-001, a portable Django/PostgreSQL foundation. No application ticket starts during this assignment. Country, payment and delivery choices should be resolved before dependent tickets become Ready.

Current scope clarification: run/test locally, use configurable local filesystem media with distinct retailer/test roots, and support only the admin role. PM selects Django admin with a single superuser/admin; custom admin UI and staff role matrices are deferred. Production hosting/OS/rollout/retention/recovery details and cloud storage are deferred; eventual independent production infrastructure remains required. Upload limits remain explicit technical follow-up. SETUP-001 is Done following merged PR16. This documentation revision is owned by Developer, coordinated by PM, and independently validated by QA; all application tickets remain Backlog. Renewed independent QA must validate this revision's exact commit.

Documentation revision [DOC-001 / #17](https://github.com/MuhammadTayyab-SE/retail_website_application/issues/17) is In Development, owned by Developer through role comments and coordinated by PM. QA validation is pending the new exact commit.
