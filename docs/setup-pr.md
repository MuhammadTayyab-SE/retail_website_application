The repository has no application scaffold or executable test suite. This setup establishes a PM/developer/QA workflow, retailer isolation architecture, requirements, decisions, and a prioritized MVP backlog before feature implementation.

All seven requested documents are included. Django and PostgreSQL are selected after inspecting the empty codebase; PKR is confirmed by the user. Country, payment, delivery, staff roles, and other business choices remain explicit decisions. The previous ignored empty document placeholders remain untouched in the original checkout; docs are now tracked in this branch.

The developer used chore/team-setup in an isolated worktree. PM independently reviewed requirements, architecture, dependencies and the diff, and requested fixes to hosting dependencies, explicit server/storage isolation, backlog serialization and text encoding. Those fixes are included. QA prepares scenarios independently and validates the exact final PR SHA in a separate detached checkout; final results will be recorded in a PR comment.

Validation: backlog JSON parses as 15 tickets with acceptance criteria; document and whitespace checks run. Application, browser, permission, and database tests cannot run because no application exists; documentation review does not validate future application behavior.

GitHub issue links are recorded in docs/github-issues.json. SETUP-001 is owned by the Developer role and coordinated by PM; no AI GitHub accounts are invented. All application tickets remain Backlog. Recommended first ticket is MVP-001: portable Django/PostgreSQL foundation, after setup is reviewed and merged.

No application features, base-branch pushes, merge, production deployment, or branch-protection changes are included. This draft PR targets development and awaits explicit user merge approval. Done means merged.
