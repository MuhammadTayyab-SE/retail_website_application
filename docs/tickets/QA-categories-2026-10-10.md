# Category QA — 2026-10-10

Result: automated regression and authenticated Django request smoke checks pass.
Desktop/mobile visual and native photo-selection checks remain unverified because
there is no connected browser. This is a QA execution report, not an independent
reviewer approval or merge recommendation.

## Tested source and environment

- Source: retail-admin-visual working tree based on commit
  437ad476dbacde11eaf53a443ddf2cc1463e2926, with current uncommitted changes.
- Separate detached QA checkout: ../retail-category-qa-20261010. Overlaid the
  current tracked/untracked nonignored source, including deletion of the old photo
  script. Exact copied-file hashes are in qa-source-manifest.txt there.
- Manifest SHA256: 92d72a259a8bac4f99ee366eccec914a4e90814e5c884cbf6275133d1a1fb648.
- Separate disposable PostgreSQL database: test_retail_category_qa_20261010.
  The test runner created it, applied all migrations, and destroyed it after tests.
- Separate QA MEDIA_ROOT: retail-category-qa-20261010/qa-media.
- Frozen offline environment installation was attempted but the pinned Pillow
  wheel was not cached. Used the existing development Python environment against
  the QA checkout instead. Dependency installation is not claimed as passed.

## Executed checks

Commands executed in the QA checkout with the development virtualenv executables:

- python manage.py check: no issues.
- python manage.py test --verbosity 2: 44 passed.
- python manage.py makemigrations --check --dry-run: no changes detected.
- ruff check .: passed.
- ruff format --check .: 42 files already formatted.
- git diff --check: passed, with normal line-ending conversion notices.

Coverage includes owner/unauthorized/CSRF permissions; category and parent
creation; optional parenting; regular-category ID rejection; separate lists;
counts/filters/pagination; sidebar and Settings; parent edit access; photo editor
markup; duplicates, hierarchy cycles and database constraints.

## Requested data in the existing local application database

Created via authenticated admin POST requests, using synthetic names:

- Parent: QA Parent Category - 2026-10-10, ID 16, active, no parent.
- Category: QA Category - 2026-10-10, ID 17, active, parent ID 16.

These records are intentionally retained in the application database, as requested.
No photos were requested or attached. Verified the committed relationship in a
second management process. Authenticated request smoke checks confirmed:

- Parent appears in Add Category's parent dropdown; the child does not.
- Combined search/status/parent filtering returns exactly the child and count 1.
- Parent Categories returns the parent with child count 1.
- Both edit pages return HTTP 200 with circular-preview markup.
- Temporary QA login session was logged out after the checks.

No application source was changed during this QA run. No merge or deployment.
