# Changelog

## 8/12/2026 — de-brand the fork

Finished the de-branding the 8/5 pass deliberately stopped short of. Nothing
that was a feature was removed; things that were only an identity were.

### Removed

- **The Help Centre.** Its entire corpus was 58 Vietnamese-only articles under
  Vietnamese slugs, with a test that actively asserted "Shinhan Workspace"
  appeared in article text. Models, API, God Mode authoring UI, the reader, the
  screenshot tooling and the fixtures are all gone. Migration `0183` drops the
  four tables and the orphaned inline-image assets; `license/0008` strips the
  now-invalid `help-center` key from stored admin menu grants.
- **The `vi` and `ko` locale packs.** The app is English-only; the language
  picker went with them, and `TLanguage` is now just `"en"`. Profiles still
  holding a retired locale fall back to English instead of erroring.

### Renamed

- **Bank-wide Projects → Global Projects**, end to end: `is_bank_wide` →
  `is_global` (migration `0184`), the `bank_wide_project` display-property key →
  `global_project` (data migration `0185`, so saved views keep their columns),
  routes `/bank-wide-projects` → `/global-projects` and
  `/settings/projects/:id/bank-wide` → `/global`, plus every symbol, label and
  i18n key. The spreadsheet column's icon referenced a `BankIcon` that never
  existed; it is now `Globe`.
- **The `shb-*` release pipeline** → `release`/`plane-*`: `docker-compose.shb.yml`,
  `build-shb-images.sh`, `deploy-shb.sh`, the `shb_v*` image tags,
  `/opt/shb-deploy`, `plane-shb-release`, the `shb-dev`/`shb-prod` runner tags
  and the `start-shbvn` action. **This changes a live deploy path** — the server
  directory and GitLab runner tags must be renamed in the same window.

### Neutralised

- **The Swing SSO email domain.** `sh{id}@swing.shinhan.com` was hardcoded at six
  sites and is the identity key for every SSO account. It now comes from a
  `SWING_SSO_EMAIL_DOMAIN` instance setting (default `swing.local`) via
  `plane.utils.staff_email`. Existing accounts are not renamed; an operator who
  needs continuity sets the old domain back.
- **The business calendar.** Kept as a feature, stripped of its region: the
  seeded Vietnamese holidays and swap-day overrides are gone (migration `0186`
  for existing instances, `0167` rewritten so fresh installs never create them),
  and `Asia/Ho_Chi_Minh`/`VN` defaults became `UTC`/empty. `VN_TZ` is now
  `CALENDAR_TZ`, configurable via `BUSINESS_CALENDAR_TIMEZONE`.
- **Seed data, deployment docs, and scripts.** Shinhan-named departments, the
  hardcoded seed password, `uat-jms.shinhan.com.vn` and its cert paths, the
  `dc=shinhan` LDAP block, and the `shbvn/plane` upstream reference.
- **Every remaining Vietnamese-language file**, including
  `docs/shbvn-deployment/` (63 files, deleted) and the git-workflow and GitNexus
  guides (translated to English).

Past `CHANGELOG` entries and `docs/journals/*` are left as written — they record
what actually happened.

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
