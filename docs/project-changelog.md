# Project Changelog

All notable changes to the Plane project are documented here. This file tracks major features, performance improvements, bug fixes, and breaking changes.

## [Unreleased] — 2026-08-05

### Bug Fixes

- **Sub-pages could not be created**: `label_ids`/`project_ids` are `ArrayAgg` annotations on the page queryset but were declared as writable serializer fields, so the sub-page action's payload reached `Page.objects.create()` and raised `TypeError`. Both are now read-only. Latent upstream as well; only the sub-page path sends the field.
- **The GitHub wiki sync had never run**: task modules live in `plane/bgtasks/*.py`, which is not the app-level `tasks` module `autodiscover_tasks()` looks for, so a task reaches the worker's registry only if `CELERY_IMPORTS` lists it or something else imports it. `github_wiki_sync_task` had neither, so beat dispatched it every five minutes and the worker discarded each message as unregistered. `deletion_task` and `github_issue_sync_task` were registering only through an incidental view and signal import; all three are now declared explicitly, guarded by a test asserting every `beat_schedule` module appears in `CELERY_IMPORTS`.
- **Page sub-counts disclosed hidden pages**: `sub_pages_count` counted every non-deleted child while the rows themselves are filtered to those the caller owns or that are public, so a page whose children were another user's private pages advertised an expander that opened onto nothing, and the count revealed the hidden pages existed.
- **Archiving a page could hang**: the recursive descendant walk used `UNION ALL`, which does not terminate on a parent loop — verified against Postgres, where the statement runs until it is killed. Now `UNION`.
- **The public invite endpoint returned its own acceptance token**: the join endpoint is `AllowAny` so an invitee can see who invited them before signing in, but it serialised with `fields = "__all__"`, returning the token plus an `invite_link` embedding it. Served from an explicitly-listed serializer instead. The remaining half of GHSA-4vj8-p63v-8p24 — requiring an authenticated session whose email matches the invitee — is still open, as it changes who may accept.
- **The project date-permission toggle had no effect**: changing an existing `target_date`/`completed_at` demanded a justification unconditionally, so a project that had explicitly unlocked a date for members still refused their edits with a 400. The reason is now required only where the restriction binds. `_is_admin` becomes the exported `bypasses_field_locks`, so the view and the permission checker share one definition of who is exempt.
- **Field-permission changes were never written to activity**: `model_activity` diffs `requested_data` against `current_instance` and `json.loads()` the latter, but the view passed `{field: {old, new}}` for both and a raw dict where a JSON string was expected. Since `.delay()` is asynchronous the request never failed — the activity row simply never appeared.
- **v1 cycle creation always failed**: the serializer resolved `project_id` from the request body, but it comes from the URL and the view never passed it on, so every `POST /cycles/` returned "Project ID is required" unless the caller redundantly repeated the id.
- **Service tokens were reachable from the personal token endpoint**: `ApiTokenEndpoint` excluded `is_service=True` from its list and delete paths but not from retrieve and patch.
- **Two god-mode RBAC gaps**: `bulk-export-projects/` had no `PREFIX_MENU_MAP` entry, and the bulk project-export and bulk member-removal views still declared the pre-RBAC `InstanceAdminPermission`, granting any instance admin regardless of granted menus.
- **`filter_updated_at` filtered on `created_at`** in both its branches.
- **`OffsetPaginator` crashed on a sequence `order_by`**, which its own constructor accepts.
- **`apps/live` and `apps/space` images would not build**: pnpm installs global binaries into `$PNPM_HOME/bin` and refuses `add -g` unless that exact directory is on `PATH`.

### Authentication

- **Restored the stock email sign-in flow.** `AuthRoot` mounted a Staff ID / Swing SSO form for sign-in, so any account without a staff profile had no way to authenticate even with email/password enabled on the instance. The Swing SSO backend provider is retained and stays inert while unconfigured.

### Testing

- **873 → 1097 passing, 0 failed, 0 errors** across unit, contract and smoke; the contract suite alone started at 19 failed / 5 errors. Most pre-existing failures could never have passed: a patch target that does not exist, fixtures using `role=10` for "member" when that value has mapped to nothing since `MEMBER` became 15, `created_by=` silently discarded by `BaseModel.save()`, an assertion skipped by operator precedence, and one suite reading a single developer's own rows by email and workspace slug.
- New backend test runner `scripts/dev-site-test.sh`, plus the isolated dev-site stack (`scripts/dev-site.sh`) and its log feed (`scripts/dev-site-logs.sh`).

### Notes

- Prioritisation should follow live row counts, not uncovered-statement counts: every fork headline feature (departments, staff profiles, help centre, GitHub sync, HO export, dashboards, worklogs) currently holds zero rows, while pages, issues, invitations, cycles, modules, notifications and the business calendar carry real data.

## [Unreleased] — 2026-06-03

### New Features

- **God-mode workspace owner = General Director**: Workspaces created from God Mode (single create, bulk create, project import) are now owned by the GD (active staff with `job_grade="GD"`) or an explicitly picked user — the acting instance admin is never added as a workspace/project member. The create form gains a searchable Owner picker defaulting to the GD. **Go-live gate:** production staff data must carry grade code `"GD"` on exactly one active staff record (see deployment guide); seed-shaped data stores grade names and will NOT resolve. Existing admin-owned workspaces are intentionally left unchanged (no backfill); project imports into them explicitly exclude the acting admin.
- **Instance-admin menu RBAC (God Mode)**: New Administrators page to add/edit/remove instance admins with per-menu grants (12 keys; config screens grouped under a single `settings` permission). Enforced fail-closed at the API via URL-prefix route groups _and_ mirrored in the sidebar/route guard. First/setup admin and all pre-existing loginable admins are migrated as super-admins (migration `license/0007`). Escalation rules: only super-admins mint super-admins; delegated admins grant only menus they hold and cannot edit their own grants. Lockout guards protect the last active super-admin from demotion, deletion, deactivation, and password seizure.
- **Add-administrator multi-user picker**: The Add-administrator dialog now searches existing active staff by name, email, or staff ID (new `GET /api/instances/admins/user-options/`, gated by the `administrators` menu) and lets you select several users at once — all promoted with the same shared menus/super-admin grant. Submit reports a per-user summary (`N added, M skipped`). Users who are already admins are excluded from results.

### Fixes

- **Admins list staleness**: `GET /api/instances/admins/` cache and its invalidation were keyed to different paths, hiding grant changes for up to 2h in production — both now pinned to the same path.
- **Admin sidebar**: the hand-maintained menu array silently dropped Job Positions; the sidebar now derives from the registry record.

### Known Risks / Accepted Decisions

- Owner FK is `on_delete=CASCADE`: concentrating ownership on the GD means deleting that user cascade-deletes their workspaces. Accepted; mitigated by user-deactivation guards (no hard-delete-user flow in god-mode UI) — revisit if one is added.
- Last-super-admin guard is check-then-act (no row locks): two precisely concurrent demotes on a 2-super instance could leave zero supers. Accepted residual risk.

## [Unreleased] — 2026-05-13

### New Features

- **Copy Project to Another Workspace**: Workspace admins can now deep-copy entire projects to other workspaces they administer. Async copy via Celery maintains all states, labels, estimates, modules, cycles, issues (with comments and worklogs), and project members. Sub-issue parent links are preserved. Frontend polls copy status with 3s interval; identifier conflicts handled inline. All strings via i18n (en/ko/vi).

## [2026-05-05] — Previous Release

### Performance

- **Profile page cross-workspace work items**: Replaced client-side 600-call fan-out with single `/api/users/me/work-items/{today,overdue}/` aggregate endpoint. Page load reduced from 10–25s to <2s. Default `crossWorkspaces=true`; toggle hidden on other-user profiles.
- **`WorkspaceUserProfileStatsEndpoint`**: Collapsed 8 sequential count queries into single `.aggregate()` with `Count(filter=Q(...), distinct=True)` (-3 SQL round-trips per page load).
- **DB partial index `issues_workitems_idx`**: Added on `(target_date, state_id) WHERE parent_id IS NULL AND deleted_at IS NULL AND archived_at IS NULL AND is_draft=FALSE` (migration `0168`, uses `CREATE INDEX CONCURRENTLY`, `atomic=False`).

### Fixes

- **`WorkspaceUserProfileEndpoint`**: Fixed critical counting bug — 3 of 4 issue counts (`created_issues`, `completed_issues`, `pending_issues`) were missing `parent__isnull=True` filter and incorrectly included sub-tasks. All 4 counts now exclude sub-tasks via DRY `_base_issue_q`. Counts may decrease for users with sub-tasks; this is the correct value.
- **Profile sub-task parity**: Legacy fan-out path (other-user profile, feature-flag-off rollback) now applies `parent_id == null` defensive filter to match aggregate-endpoint behavior.

### New Endpoints

- **`GET /api/users/me/work-items/today/`** — Returns open work items assigned to current user with `target_date >= today` (or null). Supports optional `?workspace=<slug>` to filter to single workspace. Capped at 200 items. Includes `select_related`/`prefetch_related` optimization for minimal round-trips.
- **`GET /api/users/me/work-items/overdue/`** — Returns open work items assigned to current user with `target_date < today`. Supports optional `?workspace=<slug>`. Capped at 200 items.

Both endpoints:

- Return `UserCrossWorkspaceWorkItemSerializer` (ID-only serialization: `assignee_ids`, `label_ids` for minimal payload)
- Filter to active workspace/project members only
- Exclude sub-tasks (`parent__isnull=True`)
- Use read replica (`use_read_replica=True`)

### Configuration

- New environment variable `VITE_USE_AGGREGATE_PROFILE_ENDPOINT` (default `"true"`). Set to `"false"` and rebuild frontend to roll back to legacy client-side fan-out path.

### Breaking Changes

None. All existing endpoints (`/api/users/me/`, `/api/workspace/<slug>/users/<id>/profile/`, etc.) remain unchanged in contract; only internal optimizations applied.

---

## Previous Releases

[Releases from prior dates to be added here as project evolves]
