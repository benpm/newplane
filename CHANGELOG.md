# Changelog

## 8/14/2026 — wiki sync fixed: the markdown service was never wired up

The GitHub wiki sync had never transferred content. Two faults, one behind the
other.

### Fixed

- **`LIVE_BASE_URL` was empty in the API environment.** The API converts between
  HTML and Markdown by calling the live service; with the URL unset, `LIVE_URL`
  is `None` and both conversion helpers return `None` immediately. Every push
  and pull then no-ops **while the task still reports success** — the sync logged
  "wiki success: 0 pulled, 0 pushed" and nothing looked wrong.

  `apps/api/.env.example` shipped `http://localhost:3100`, which is wrong inside
  Docker and invites exactly this. It now carries the compose value with a
  comment about the silent-failure mode.

- **A failed transfer wedged the sync permanently.** The link row is written
  _before_ the first push, so an outage left a pairing with no file behind it.
  On every later run the linked-pairs loop saw a link whose wiki file was
  missing and treated it as a wiki-side deletion, while the "unlinked pages"
  pass skipped the page because a link existed. The page could never reach the
  wiki again. Links with no recorded content hash are now retried instead —
  genuine deletions, which do have a hash, are still not propagated.

  Both paths are covered by tests; the recovery test fails without the fix.

### Known issue

`github_wiki_page_links` has `UNIQUE (page_id)` with no exclusion for
soft-deleted rows, so a soft-deleted link permanently blocks re-linking that
page. Clearing wedged links needs a hard delete. A partial unique index on
`deleted_at IS NULL` would fix it properly.

## 8/14/2026 — one CLI instead of eighteen scripts

### Changed

- **`scripts/` is now a single entry point: `scripts/plane`.** The eighteen
  loose shell scripts became subcommands of one tool with one help system, one
  set of colours, one error handler and one log format. `scripts/plane help`
  lists everything; `docs/scripts.md` documents it, including a table of where
  each old script went.

  Every command now reports failures the same way — `✗` plus the message, and
  for unexpected errors the line and command that failed, which none of the
  originals did. Colour disables itself when output is not a terminal, and
  `--log-file` writes a timestamped transcript with the escape codes stripped.

  `setup.sh` deliberately stays a separate file. It is 800 lines of upstream
  Plane's installer; folding it in would turn every future upstream sync into a
  manual merge. It is reachable as `plane setup`.

  Callers were updated with the move: `package.json` (`dev:local`,
  `dev:clean`), `.mcp.json`, the three husky git hooks, and `.gitlab-ci.yml`.

- Shared logic that had been copy-pasted across scripts is now written once —
  the release compose override was generated in three separate places with
  three slightly different headers, and the preflight checks were duplicated in
  nearly every file.

- The build scripts still described themselves as building "SHB Docker images"
  in their headers and banner output; the de-branding pass had not reached
  `scripts/`. Gone with the rewrite.

## 8/14/2026 — user management on the dashboard

### Added

- **Rename accounts.** Changes `display_name` only — email and username are
  untouched, since they are the login key and identity and sessions and audit
  trails are keyed on them.
- **Deactivate and reactivate accounts.** Suspends sign-in and workspace
  membership together; everything the person authored stays put, and both
  restore on reactivation.

  **There is no delete, on purpose.** `User` is not soft-deletable and Django
  cascades in Python across the ~300 relations pointing at it. Simulated
  against a real account here, a delete would have removed **173 rows across 15
  models** — 31 work items, 16 states, 10 pages, 2 projects, 81 activity
  records — unrecoverable without a restore. Two guards refuse outright:
  deactivating yourself, and deactivating the last super admin who can sign in.
  Recovering from either needs shell access.

- **Named invite links.** Creates the invite and hands back the link rather
  than emailing it, which matters because this instance has no SMTP configured
  and emailed invites go nowhere. An invite carries an optional name, applied
  on acceptance — but only when the account never chose one for itself, so a
  second invite can't rewrite a name someone picked. Migration `0187` adds
  `display_name` to `WorkspaceMemberInvite`. Re-inviting the same address
  updates the outstanding invite instead of colliding with the
  `(email, workspace)` constraint.

- **`docs/instance-dashboard.md`** — full documentation for the feature:
  every tab, the probe model, why storage reports three separate figures, user
  management, the API table, and why the namespace cannot contain the substring
  `instances`. Linked from the README, `features.md`, `system-architecture.md`,
  `codebase-summary.md` and `deployment/health-monitoring.md`.

### Fixed

- **`docs/deployment/health-monitoring.md` documented five endpoints that do
  not exist.** It described `/health` returning per-dependency status plus
  `/health/db`, `/health/cache`, `/health/celery` and `/health/storage`. The
  only real route is `""` returning a static `{"status": "OK"}` that touches no
  dependency at all. Corrected, with a pointer to the dashboard, which actually
  does what that section claimed.

## 8/13/2026 — instance dashboard, and docs that match the repo

### Added

- **An instance dashboard at `/dashboard`.** Instance-admin-only. Four tabs:
  live service health (Postgres, Redis/Valkey, RabbitMQ, object storage, Celery
  workers, beat staleness), instance-wide entity counts, storage usage, and
  paginated inventories of every workspace, user and project.

  It is mounted at `/api/instance-dashboard/`, **not** under `/api/instances/`.
  The session middleware picks the session cookie by testing
  `"instances" in request.path`, so anything matching that would read the
  god-mode cookie — which web users do not have — and 403 every request. A test
  walks the urlpatterns to keep the substring out, with a failure message
  explaining why.

  Each probe sets its own short timeouts and never raises, so one dead
  dependency renders as a red card rather than a 500. The shared helpers were
  unsuitable: `redis_instance()` sets no socket timeout, and `S3Storage`
  inherits botocore's 60s/5-retry defaults. RabbitMQ is inspected through kombu
  rather than the management API, and a down broker short-circuits worker
  inspection instead of paying the timeout twice. Broker and SMTP credentials
  are scrubbed from every error string.

  Storage reports three figures separately — declared (a client-supplied
  reservation), measured (real `ContentLength`, present on only some rows), and
  a bucket scan (ground truth) — plus `measured_coverage`. The gap is labelled
  "unreconciled", not "orphaned", because partial coverage makes the stronger
  word untrue.

- **`docs/features.md`** — a reference for every feature and the code behind
  it. Roughly thirty fork-original features had no documentation at all,
  including GitHub sync, the page tree, page-link autocomplete, markdown
  round-trip, god-mode RBAC and Global Projects.

### Changed

- Celery worker and beat-schedule inspection moved to
  `plane/utils/instance_probes.py`; the god-mode monitoring endpoints now
  delegate to it. Instance-wide counts moved out of the telemetry tracer into
  `plane/license/utils/instance_counts.py`, which the tracer consumes.
- **`docs/codebase-summary.md` and `docs/system-architecture.md` rewritten.**
  Both described directories that do not exist (`app/serializers/v0/` and
  `v1/`, `settings/base.py`, `plane/tasks/`), called a React Router + Vite SPA
  a Next.js app router, and counted models and tasks wrongly. The architecture
  doc gains sections on the session-cookie split, the instance dashboard,
  GitHub sync and god-mode RBAC.
- `docs/git-workflow-guide.md` described a `preview`/`develop` branch model
  this repo has never used; it now documents the single-trunk `main` flow.
- CI job names across the deployment docs corrected against `.gitlab-ci.yml`
  (`deploy:dev:release` / `deploy:prod:release` never existed; the real jobs
  are `deploy:external-test` and `release:production`). Last "Plane SHB"
  strings removed.

### Removed

- **`docs/project-roadmap.md`** — invented owners (`@analytics-team`),
  percentages and "Next Steps (Apr 2-8)" describing work long since shipped or
  abandoned.
- **`docs/project-changelog.md`** — duplicated this file and still listed the
  deleted Help Centre.
- **`docs/deployment/migrate-to-u01.md`** — a one-off runbook for a
  decommissioned host.
- The orphaned `# Help Center authoring` comment left behind in
  `license/urls.py`.

`docs/journals/*` are left as written — they are a record of what happened, not
documentation of what is.

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
