# Changelog

## 8/5/2026 — fixes

Found while running this branch on a dev deployment and driving its test suite
to green. Each was reproduced before it was fixed.

### Bugs

- **Sub-pages could not be created.** `label_ids`/`project_ids` are queryset
  annotations but were declared writable, so the sub-page action's payload
  reached `Page.objects.create()` and raised. Now read-only.
- **The GitHub wiki sync had never run.** Beat dispatched it every five minutes
  and the worker discarded each message: nothing imported the task module, and
  `autodiscover_tasks()` does not look in `plane/bgtasks/`. `deletion_task` and
  `github_issue_sync_task` were registering only by accident; all three are now
  declared, with a test asserting every scheduled task is importable.
- **The sub-page count disagreed with the sub-page list.** Pages showed an
  expander for another user's private children, which opened onto nothing and
  revealed that the hidden pages existed.
- **Archiving a page could hang.** The recursive walk used `UNION ALL`, which
  never terminates on a parent loop; now `UNION`.
- **The public invite endpoint returned its own acceptance token**, plus a link
  embedding it. That token is the only thing gating acceptance.
- **The date-permission toggle did nothing.** Unlocking a date for members still
  refused their edits with "a reason is required".
- **Field-permission changes were never recorded in activity** — the payload
  shape was wrong and, being async, the failure never surfaced in the response.
- **v1 cycle creation always failed** with "Project ID is required", because the
  view never passed the URL's project to the serializer.
- **Service tokens were readable and renameable** through the personal API-token
  endpoint.
- **Two god-mode RBAC gaps**: `bulk-export-projects/` had no menu mapping, and
  two bulk endpoints still used the pre-RBAC all-admin permission.
- **`filter_updated_at` filtered on `created_at`.**
- **The paginator crashed** when given a list `order_by`.
- **`apps/live` and `apps/space` images would not build** — pnpm's global bin
  directory was missing from `PATH`.

### Sign-in and branding

- Restored the stock email sign-in flow. The form mounted a Staff ID / Swing SSO
  component, so accounts without a staff profile could not log in at all.
- Replaced the Shinhan identity with stock Plane across web, admin, the three
  locale files and the backend email templates. The Vietnamese help-centre
  fixtures are deliberately unchanged — authored content with cross-referenced
  slugs, not chrome.

### Tests and tooling

- **873 → 1097 tests passing, 0 failed, 0 errors** across unit, contract and
  smoke. Most pre-existing failures could never have passed, e.g. patching a
  module that does not exist and fixtures using a role value that maps to
  nothing since `MEMBER` became 15.
- `scripts/dev-site.sh`, `scripts/dev-site-logs.sh`, `scripts/dev-site-test.sh`
  — an isolated second stack on port 8091, its log feed, and the backend test
  runner. See [docs/deployment-guide.md](./docs/deployment-guide.md).

## 8/5/2026

- [x] full GitHub-flavored markdown support
- [x] better GitHub integration - github issues show up as tasks and are closed upon task completion. A project should be able to be associated with a specific Github repo
- [x] pages should be able to be organized in a tree-like fashion where pages can have children pages
- [x] pages should also sync to the associated GitHub git repo's wiki. Pages written to the wiki should sync to Plane and visaversa
- [x] links to other pages should autocomplete - either through a slash command or by typing "["
- [x] New users should be automatically added to Projects that are configured with a new boolean setting: "auto-add new users".
