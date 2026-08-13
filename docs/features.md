# Feature Reference

Every feature this deployment ships, with the code behind it. Two sections:
**fork-original** features built on top of upstream Plane, and the **upstream
surface** inherited from Plane CE.

Paths are relative to the repo root. Backend lives under `apps/api/plane/`,
web frontend under `apps/web/` (`core/` upstream, `ce/` fork), god-mode under
`apps/admin/`.

---

## Fork-original features

### Instance dashboard

> Full documentation: **[Instance Dashboard](./instance-dashboard.md)**

`/dashboard` — an instance-admin-only operational view: service health
(Postgres, Redis/Valkey, RabbitMQ, object storage, Celery workers and beat),
storage usage, instance-wide entity counts, and paginated inventories of every
workspace, user and project.

- **Backend** — `app/views/instance_dashboard/` (health, overview, storage,
  listings, jobs), `app/urls/instance_dashboard.py`,
  `utils/instance_probes.py`, `utils/instance_storage.py`,
  `license/utils/instance_counts.py`
- **Frontend** — `apps/web/app/(all)/dashboard/`,
  `apps/web/ce/components/instance-dashboard/`,
  `packages/services/src/instance/instance-dashboard.service.ts`,
  `packages/types/src/instance-dashboard.ts`

Two design constraints worth knowing before changing anything here:

**The URL must not contain the substring `instances`.**
`authentication/middleware/session.py` selects the session cookie with
`if "instances" in request.path`, reading the god-mode cookie
(`admin-session-id`) when it matches and the app cookie (`session-id`)
otherwise. The dashboard is served to `apps/web`, so a path under
`/api/instances/` would resolve to `AnonymousUser` and return 403 to a
signed-in admin. `test_instance_dashboard_permissions.py` enforces this.

**Storage reports three numbers, not one.** `FileAsset.size` is declared by
the client at presign time and clamped — a reservation.
`storage_metadata["ContentLength"]` is a real measurement, but only on assets
that completed the v2 upload handshake. A bucket scan is ground truth and the
only source that sees objects with no row behind them. The UI shows all three
plus `measured_coverage`, and calls the gap "unreconciled" rather than
"orphaned", because partial coverage makes the stronger word untrue.

Bucket scans are manual, bounded to 20s / 500k objects, cached 6h, and
lock-guarded so two admins cannot double-scan.

It also carries **user management**: rename an account's display name (email
and username untouched), deactivate and reactivate accounts, and create named
invite links that carry the invitee's name and need no SMTP. There is no
delete — see the doc for why.

### Global Projects

A project flagged `is_global` becomes visible instance-wide rather than only
to its members. A cross-workspace directory lists every global project with
search and date filtering, and a `global_project` display property/spreadsheet
column marks work items belonging to one.

- **Backend** — `db/models/project.py` (`is_global`),
  `app/views/project/global_projects.py`, `app/urls/project.py`,
  `db/signals/project.py`
- **Frontend** — `/:workspaceSlug/global-projects`,
  `ce/components/global-projects/`, `ce/services/global-projects.service.ts`,
  per-project settings at `/settings/projects/:projectId/global`
- **Migrations** — `0184_rename_project_is_bank_wide_to_is_global`,
  `0185_rename_bank_wide_display_property` (rewrites the key inside stored
  `display_properties` so saved views keep their columns)

### HO (Head Office) datasheet and export

A cross-workspace flat datasheet of every work item the viewer can reach, with
department and task-category grouping, assignee aggregation from sub-tasks,
per-issue worklog breakdown popovers, column sorting and multi-select filters,
plus an async xlsx/csv export delivered by email.

- **Backend** — `app/views/ho.py`, `app/views/ho_export.py`, `app/urls/ho.py`,
  `app/serializers/ho.py`, `db/models/ho_export.py`,
  `bgtasks/ho_export_task.py`, `bgtasks/ho_export_helpers.py`,
  `bgtasks/ho_export_email_task.py`
- **Frontend** — `/:workspaceSlug/ho`, `ce/components/ho/`, `ce/store/ho/`

`app/views/ho.py` contains the repo's best-documented raw SQL — recursive CTEs
over `issues` with explicit depth bounds and soft-delete filtering.

### Swing SSO

Staff sign in with a Staff ID and password against an external REST API, or
arrive pre-authenticated from the Swing portal with an XML-validated token.
Accounts resolve by a derived email, `{prefix}{staffId}@{SWING_SSO_EMAIL_DOMAIN}`.
The provider stays inert while unconfigured, and stock email sign-in remains
available alongside it.

- **Backend** — `authentication/provider/credentials/swing_sso.py` and
  `swing_sso_token.py`, `authentication/views/app/swing_sso.py`,
  `utils/staff_email.py`
- **Frontend** — god-mode `/authentication/swing-sso`
- **Local dev** — mock server at `scripts/mock_swing_sso_api/`
- **Spec** — `docs/swing-sso-integration-spec.md`

The email domain is instance configuration (`SWING_SSO_EMAIL_DOMAIN`), not a
constant. Changing it on a live instance does not rename existing users — it
only affects addresses minted from that point on.

### Departments, staff and org chart

A hierarchical org structure (departments with a parent chain, a manager, an
optional 1:1 linked workspace) plus per-user `StaffProfile` records. Staff can
be bulk-imported from Excel/CSV, bulk-actioned, exported, transferred between
departments, and deactivated on resignation; department membership propagates
to workspace membership via a Celery task.

- **Backend** — `db/models/department.py`, `db/models/staff.py`,
  `app/views/workspace/{department,staff,org_chart}.py`,
  `license/api/views/department*.py`, `license/api/views/staff.py`,
  `bgtasks/department_membership_task.py`
- **Frontend** — god-mode `/departments`, `/staff`; web
  `/:workspaceSlug/settings/departments`
- **Spec** — `docs/hr-system-integration-spec.md`

### Business calendar

Three-tier working-day resolution — `DayOverride` beats `Holiday` beats
`week_pattern[weekday]` — behind a Redis-cached service exposing
`is_working_day()`, `next_working_day()`, `add_business_days()` and
`working_days_between()`, with signal-driven cache invalidation. A
`@working_day_required()` decorator (fail-open) gates Celery jobs such as
`archive_and_close_old_issues`.

- **Backend** — `db/models/business_calendar.py`,
  `utils/business_calendar/{service,resolver,cache}.py`,
  `utils/celery_helpers.py`, `license/api/views/business_calendar/`
- **Frontend** — god-mode `/calendar`
- **Config** — `BUSINESS_CALENDAR_TIMEZONE` (`CALENDAR_TZ`, default `UTC`)

Ships with an empty, neutral default schedule; operators populate it in
god-mode.

### GitHub sync (issues and wiki)

A project binds to one GitHub repo. Issues appear as Plane work items and
close/reopen bidirectionally — `GithubIssueLink.github_state` records the
last-observed remote state so echo updates converge instead of ping-ponging.
Separately, Plane pages sync both ways with the repo wiki over GFM.

- **Backend** — `db/models/github_sync.py`,
  `app/views/project/github_sync.py`, `bgtasks/github_issue_sync_task.py`,
  `bgtasks/github_wiki_sync_task.py`, `db/signals/github_issue_push.py`,
  `utils/github_client.py`, `utils/github_wiki.py`
- **Frontend** — `ce/components/projects/settings/github-sync/`
- **Ops** — `scripts/rotate-github-token.sh` validates a new token (API
  reachable, `repo` scope, push access to every configured repo) _before_
  writing it to either env file

Auth is instance-wide via `GITHUB_PERSONAL_ACCESS_TOKEN`; there are no
per-project credentials. Both syncs run on Celery beat every five minutes.

### Page-link autocomplete

Typing `[[` opens the mentions dropdown to search sibling pages and inserts a
**plain link mark**, not a mention node — deliberately, because links survive
the GFM round trip as `[Title](url)` (required by wiki sync and raw-markdown
mode) whereas mention nodes have no Markdown representation.

- `packages/editor/src/core/extensions/page-link/`, wired in
  `packages/editor/src/ce/extensions/document-extensions.tsx`

Editors without a `searchCallback` (work-item descriptions, comments)
contribute the plugin as a no-op.

### God-mode menu RBAC

Instance admins are scoped to a granted subset of god-mode menus. Enforcement
is by URL prefix under `/api/instances/` rather than per-view annotation, so
one registry covers every endpoint — anything unmapped is denied (fail-closed).
Super admins bypass.

- **Backend** — `license/menu_registry.py`,
  `license/api/permissions/instance.py`, `license/models/instance.py`
  (`allowed_menus`, `is_super_admin`)
- **Frontend** — god-mode `/administrators`,
  `apps/admin/hooks/use-sidebar-menu/`

`PERMISSION_KEYS` is mirrored between `license/menu_registry.py` and
`apps/admin/hooks/use-sidebar-menu/core.ts`, and
`tests/unit/test_menu_registry_parity.py` asserts they match. Adding a key
means touching both plus a god-mode page.

### Time tracking and worklogs

Per-work-item worklogs with workspace and project timesheets, analytics,
capacity planning and async export.

- **Backend** — `db/models/worklog.py`, `app/views/workspace/time_tracking/`,
  `bgtasks/worklog_export_task.py`, `bgtasks/worklog_reminder_task.py`
- **Frontend** — `/:workspaceSlug/time-tracking{,/analytics,/capacity,/exports}`,
  `ce/components/time-tracking/`

### Capacity dashboard and export

Donut charts of team capacity with day-level drill-down and issue peek, plus an
async export job.

- `db/models/capacity_export.py`, `bgtasks/capacity_export_*.py`,
  `bgtasks/capacity_report.py`, `app/views/capacity.py`

### Workflows and approvals

Per-project state machines: allowed transitions, approvers per transition, and
an activity log.

- `db/models/workflow.py`, `app/views/workflow.py`, `ce/store/workflow.store.ts`,
  `/:workspaceSlug/settings/projects/:projectId/workflows`

### Task categories

Two-level taxonomy (main/sub) linkable to departments, and assignable to work
items via `Issue.main_task_category` / `sub_task_category`.

- `db/models/task_category.py`, `app/views/task_category.py`,
  `license/api/views/task_category*.py`, god-mode `/task-categories`

### Job positions and grades

- `db/models/job_position.py`, `license/api/views/job_position*.py`,
  god-mode `/job-positions`

### Project field permissions

Per-project locks on date fields and deletion, with a `bypasses_field_locks`
escape for privileged roles.

- `db/models/project_field_permission.py`,
  `/:workspaceSlug/settings/projects/:projectId/field-permissions`

### Due-date change reason

A reason is required when `target_date` or `completed_at` changes, unless the
project unlocks it.

### Project copy

Async duplication of a project including its issues, into the same or another
workspace.

- `db/models/project_copy.py`, `bgtasks/copy_project_*.py`,
  `ce/store/project-copy.store.ts`

### Nested page tree

Recursive descendant walk with `sub_pages_count`, sub-page navigation and
cycle-safe re-parenting.

- `app/views/page/base.py`

### GFM markdown round-trip

Paste and copy Markdown, edit a page as raw Markdown, import `.md` files.

- `packages/editor/src/core/plugins/markdown-{clipboard,paste}.ts`,
  `utils/markdown.py`

### Dashboards V2

User-composed dashboards of chart widgets with drill-down.

- `db/models/dashboard.py`, `app/views/{dashboard,dashboard_chart}.py`,
  `utils/dashboard_chart_aggregation.py`, `utils/build_chart.py`,
  `/:workspaceSlug/dashboards`

### God-mode bulk operations

Bulk workspace creation, member assign/remove, project and module import,
project export, user import, department import.

- `license/api/views/{workspace_bulk_create,workspace_member_bulk_*,workspace_*_bulk_*,user_bulk_import,department_bulk_import}.py`

### Monitoring and usage monitor

Email notification logs, the Celery beat schedule, live worker health, and
worklog-derived active/standard user series by workspace and department.

- `license/api/views/monitoring.py`, `license/api/views/usage_monitor.py`,
  `license/utils/usage_metrics.py`, god-mode `/monitoring`, `/usage-monitor`

The worker and beat logic here is shared with the instance dashboard through
`utils/instance_probes.py`.

### GD (General Director) owner resolver

Resolves a default workspace owner for god-mode workspace creation.

- `utils/general_director.py`, `license/api/views/workspace_owner_options.py`

### LDAP / Active Directory auth

- `authentication/provider/credentials/ldap.py`,
  `authentication/views/app/ldap.py`, god-mode `/authentication/ldap`

### Gitea OAuth

- `authentication/provider/oauth/gitea.py`,
  `authentication/views/{app,space}/gitea.py`, god-mode `/authentication/gitea`

### Cross-workspace profile aggregation

One query for a user's work items across every workspace, replacing an N+1 fan-out.

- `app/serializers/user_work_items.py`,
  `GET /api/users/me/work-items/{today,overdue}/`, migration `0168` (partial index)
- Feature flag `VITE_USE_AGGREGATE_PROFILE_ENDPOINT`

### Module activity tracking

- `utils/module_activity.py`, `ce/store/module-activity.store.ts`

### Issue `frequency` property

A recurrence-cadence field on work items, surfaced in the modal, peek and sidebar.

- `db/models/issue.py`

### Email template management

- god-mode `/email`

---

## Upstream surface

Inherited from Plane CE. Enumerated for completeness; see upstream docs for
detail.

| Area                  | What it covers                                                                                                                                                                                                                          |
| --------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Workspaces**        | Slugs, members and roles, invitations, settings, exports, webhooks, timezone, home and quick links                                                                                                                                      |
| **Projects**          | Visibility, identifier, lead and default assignee, per-project feature toggles, members, archives, cover/logo, auto-archive and auto-close windows, public deploy boards                                                                |
| **Work items**        | States, labels, priorities, assignees, dates, estimate points, sub-items, relations, links, attachments, comments and reactions, mentions, activity feed, subscribers, drafts, archives, soft delete, issue types, description versions |
| **Layouts**           | List, Kanban, Calendar, Gantt/timeline, Spreadsheet                                                                                                                                                                                     |
| **Cycles**            | Dated iterations, issue assignment, transfer of incomplete work, active-cycles view, archives                                                                                                                                           |
| **Modules**           | Feature groupings with lead and members, issue links, archives                                                                                                                                                                          |
| **Views**             | Project and workspace-level saved filters and display properties                                                                                                                                                                        |
| **Pages**             | Collaborative rich-text wiki pages, versions, labels, archive, access control                                                                                                                                                           |
| **Intake**            | External submission queue with accept/reject/duplicate triage                                                                                                                                                                           |
| **Estimates**         | Estimate sets and points, per project                                                                                                                                                                                                   |
| **Analytics**         | Workspace analytics tabs, plots, exports                                                                                                                                                                                                |
| **Notifications**     | In-app centre, email notifications, subscriptions                                                                                                                                                                                       |
| **Stickies**          | Personal sticky notes                                                                                                                                                                                                                   |
| **Favorites**         | Server-side favourites and recently-visited entities                                                                                                                                                                                    |
| **Profile**           | User profile, activity feed, per-user work-item views, settings                                                                                                                                                                         |
| **Webhooks & tokens** | Outbound webhooks, personal and service API tokens                                                                                                                                                                                      |
| **Import/export**     | Issue import framework, CSV/xlsx export jobs                                                                                                                                                                                            |
| **Auth**              | Email/password, magic code, Google, GitHub, GitLab OAuth                                                                                                                                                                                |
| **Realtime**          | `apps/live` (Hocuspocus/Yjs) for collaborative pages                                                                                                                                                                                    |
| **Public space**      | `apps/space` renders published boards read-only                                                                                                                                                                                         |
| **God Mode**          | `apps/admin` instance configuration — general, email, AI, image, auth providers, users, workspaces                                                                                                                                      |
