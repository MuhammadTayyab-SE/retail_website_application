# Category photo editor and hierarchy

User requested the category-list screenshot as layout inspiration, retaining the existing theme. Scope confirmed: category photos and hierarchy first; brands/products next in backlog (CATALOG-FLOW-003). Continue existing admin-visual worktree/PR #25. QA is explicitly deferred until user asks.

Implementation: optional single ImageField per category; original image in configurable MEDIA_ROOT (default checkout media/categories); random filename; image format and 8 MB limit validation; saved horizontal/vertical position and 100?200% zoom. Native multipart admin form supports replacement and removal. Replaced/removed file is deleted after database transaction commits. Admin-protected image endpoint serves previews/thumbnails without publicly exposing media. Photo is optional; previous categories retain defaults.

List retains native pagination, ordering, inline position/status edits, errors and permissions, with thumbnails/actions and combined search/status/parent filter toolbar. Statuses remain Active/Inactive; no mock products or arbitrary statuses added. Parent category action opens category creation with an empty parent; child category creation selects an existing parent. Existing cycle validation retained.

Developer setup only: Pillow dependency installed and locked; additive migration applied to local development database; Django system check, Ruff, template compilation and static collection recorded below. No QA, regression suite, browser walkthrough or screenshots run for this revision.

Developer setup completed: migration applied successfully; Django check (0 issues), Ruff lint/format, three category-template compilations, collectstatic and diff checks passed. PM source review identified and confirmed fixes for empty exact filters and image MIME handling. No QA or regression suite executed per user instruction.
