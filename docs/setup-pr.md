# Local development decisions follow-up

Previous setup PR16 is merged. This follow-up records the user's local development, local media and admin-only scope decisions. It contains documentation changes only and requires renewed exact-SHA QA and explicit user merge approval.

The repository has no application scaffold or executable test suite. This setup establishes a PM/developer/QA workflow, retailer isolation architecture, requirements, decisions, and a prioritized MVP backlog before feature implementation.

All seven requested documents are included. Django and PostgreSQL are selected after inspecting the empty codebase; PKR is confirmed by the user. Country, payment, delivery, and other business choices remain explicit decisions. The previous ignored empty document placeholders remain untouched in the original checkout; docs are now tracked in this branch.

The developer used chore/team-setup in an isolated worktree. PM independently reviewed requirements, architecture, dependencies and the diff, and requested fixes to hosting dependencies, explicit server/storage isolation, backlog serialization and text encoding. Those fixes are included. QA prepares scenarios independently and validates the exact final PR SHA in a separate detached checkout; final results will be recorded in a PR comment.

Validation: backlog JSON parses as 15 tickets with acceptance criteria; document and whitespace checks run. Application, browser, permission, and database tests cannot run because no application exists; documentation review does not validate future application behavior.

GitHub issue links are recorded in docs/github-issues.json. SETUP-001 is owned by the Developer role and coordinated by PM; no AI GitHub accounts are invented. All application tickets remain Backlog. Recommended first ticket is MVP-001: portable Django/PostgreSQL foundation, after setup is reviewed and merged.

No application features, base-branch pushes, merge, production deployment, or branch-protection changes are included. The original setup PR targeted development and has been merged. The follow-up PR targets development and awaits explicit user merge approval. Done means merged.

Current scope clarification: run/test locally, use configurable local filesystem media with distinct retailer/test roots, and support only the admin role. PM selects Django admin with a single superuser/admin; custom admin UI and staff role matrices are deferred. Production hosting/OS/rollout/retention/recovery details and cloud storage are deferred; eventual independent production infrastructure remains required. Upload limits remain explicit technical follow-up. SETUP-001 is Done following merged PR16. This documentation revision is owned by Developer, coordinated by PM, and independently validated by QA; all application tickets remain Backlog. Renewed independent QA must validate this revision's exact commit.
