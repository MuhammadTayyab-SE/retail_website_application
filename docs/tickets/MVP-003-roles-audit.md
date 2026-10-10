# MVP-003 expanded implementation

User authorized expanded requirements and implementation on 2026-10-11. GitHub
[#4](https://github.com/MuhammadTayyab-SE/retail_website_application/issues/4)
is authoritative. Developer owns `feature/mvp-003-roles-audit`, based on
development `a7a7572`. This supersedes the original single-admin-only D-004 scope.
State: In Development; independent PM review and independent QA remain pending.

## Implemented behavior

- Super Admin has the existing full dashboard and exclusive Workers, Roles and
  Activity log management. Workers have one optional assigned role. Workers
  without a role cannot sign in; a role with no grants provides a dashboard with
  no accessible modules. Accounts are deactivated rather than deleted in the UI.
- Roles grant view/add/change/delete separately for Categories and Parent
  Categories. Both use the existing Category table, including legacy records
  used as parents; authorization distinguishes the two modules on object,
  list, form, bulk position, delete, and private photo endpoints. A cascading
  delete also requires permission for every affected descendant. Parent
  assignment controls are omitted without Parent Categories view access.
- A dedicated authentication backend uses only role grants for workers.
  Existing Django group or direct-user grants cannot bypass role restrictions;
  account/role/audit administration additionally has an explicit Super Admin
  boundary. Permission caching lives only for one HTTP request. Role changes,
  reassignment and account deactivation apply to the next request in existing
  sessions. Existing Super Admin authentication remains supported.
- Super Admin creates worker accounts with validated passwords and can reset
  them. Workers can change their own password in Settings. Stored password
  hashes are never shown in account forms. Neither hashes nor password values
  are persisted in activity details. Password viewing is intentionally replaced
  by reset, as recorded in the updated ticket.
- AuditEvent records actor ID/name snapshots, UTC time, action, module, target
  identifier and outcome. Model signals record successful business mutations,
  cascading deletion, role assignment/permission changes and password events;
  middleware records page/request outcomes, failed forms and denied access.
  Authentication signals record login/logout and failed login. Authenticated
  public catalog visits are included. No request bodies, query strings,
  credentials, session tokens or password hashes are copied into the log.
  Only whitelisted non-sensitive field names and access/ordering state changes
  are recorded. Log entries remain after target deletion/username changes.
- Super Admin can filter activity by actor, date, module, action and outcome.
  The portal has no audit create/edit/delete actions, including for Super Admin.
  ORM model/queryset edits and deletes are rejected. This is application-level
  immutability; database administrators remain responsible for database access.
- Parent Categories and Categories have read-only created_by/created_at and
  updated_by/updated_at on their edit/detail screen. Authenticated portal saves
  assign the actor/time, including bulk position editing. Original attribution
  is retained. New non-portal saves have timestamps and unknown actor unless an
  explicit creator is supplied. Existing legacy rows remain NULL/unknown at
  migration, with no fabricated backfill; their next portal edit records the
  actual updater. Attributed users are protected from deletion, and the UI
  offers deactivation to preserve authorship.

## Product integration boundary

There is no Product model or Product management module yet: those belong to
MVP-005. `access.models.AttributedModel` is the reusable creator/editor/time
foundation, and its subclasses are automatically included in audit signals.
MVP-005 must inherit it, register its module permissions and run Product-specific
attribution/access tests. This PR does not claim Product CRUD is implemented.
Current supported bulk edits are the category/parent position formsets, which
save each record normally. Future endpoints must not use signal-bypassing
queryset updates/bulk inserts for attributed portal changes without equivalent
attribution/audit handling.

## Database and operation

`access.0001_initial` adds Role, WorkerProfile and AuditEvent tables.
`catalog.0005` adds nullable attribution fields and parent-module permissions.
Both applied successfully to the existing local PostgreSQL database with
`python manage.py migrate --noinput`; existing category data is preserved.
This is not a production deployment. Existing superusers need no role/backfill.
No permanent test worker accounts or passwords were inserted into the local
application database; test fixtures use a separate disposable database.

To use the feature, run this worktree's environment, sign in as the existing
Super Admin, create a Role with module/action permissions, then create a Worker
and select that role. Worker accounts have staff access set automatically and
cannot be promoted through forged form fields. Keep an active Super Admin.

## Developer verification and handoff

Frozen dependencies installed offline using the existing Python interpreter.
Developer test suite uses separate disposable PostgreSQL database
`test_mvp003_roles_20261011`; commands and final results are recorded in the PR.
Coverage includes two workers with distinct roles, active-session changes,
direct URLs and photos, account/role/log permission escalation, password
reset/self-change, role assignment/deactivation, add-only/read-only roles,
bulk edits, cascading deletion, failed forms, legacy attribution, and audit
immutability/actor retention. Existing catalog/dashboard tests also run.

Final developer validation: all 70 PostgreSQL-backed tests passed; Django system
check, `makemigrations --check --dry-run`, Ruff lint/format and `git diff --check`
passed. No independent review or QA approval is implied by these developer checks.

Browser runtime reports no available browser and discovery returns an empty
list. No rendered desktop/mobile or keyboard acceptance is claimed. Independent
PM review and QA of the exact PR SHA in a separate checkout/database must verify
these flows at desktop 1440px and mobile 360px/390px/767px before user review.
The separate admin QA fixes PR #27 remains independent of this feature.
