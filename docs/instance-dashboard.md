# Instance Dashboard

An operational view of the whole deployment at **`/dashboard`**, restricted to
instance administrators. It answers three questions the rest of the app cannot:
is the infrastructure healthy, where is the disk going, and who is on this
instance.

- **Live:** https://plane.mousetrip.online/dashboard
- **Dev site:** https://dev.mousetrip.online/dashboard

---

## Access

The page is gated on `GET /api/users/me/instance-admin/`, and every endpoint
behind it independently enforces `InstanceAdminPermission` — the client gate is
convenience, not security. A non-admin who navigates to `/dashboard` gets a
plain "instance admins only" panel rather than a redirect, so a shared link
fails legibly instead of looking broken.

One consequence of `AuthenticationWrapper`: an admin with no workspace at all is
bounced to `/create-workspace` before reaching the page.

---

## Tabs

### Health

Live status for six dependencies, refreshed every 30 seconds (the server caches
for 15, so the poll is cheap).

| Service        | What is checked                                                      |
| -------------- | -------------------------------------------------------------------- |
| Postgres       | `SELECT 1`, server version, database size, active vs max connections |
| Redis / Valkey | `PING`, version, memory in use, connected clients, key count         |
| RabbitMQ       | Broker connection and queue depth with consumer count                |
| Object storage | `head_bucket` against the uploads bucket                             |
| Celery workers | Live worker list, pool size, active task count                       |
| Celery beat    | Enabled task count, time since the last run, overdue tasks           |

Each reports `ok`, `degraded`, `down` or `unknown`, plus its round-trip latency.
`degraded` is used where a service answers but something is off — Postgres past
80% of `max_connections`, Redis near its memory ceiling, a queue with messages
and no consumer draining it, or a beat task overdue by more than two intervals.

Below the service cards: the worker table with broker queue depths, the full
beat schedule with staleness flags, and a runtime panel (instance name,
version, Python and Django versions, SMTP configuration, and a warning badge if
`DEBUG` is on in production).

**A dependency being down is content, not an error.** The endpoint returns HTTP
200 with that service marked `down` and the others still reported. The page
stays usable precisely when you need it.

### Overview

Instance-wide counts: workspaces, users (total, active, bots, admins, joined in
the last 30 days), projects (total, archived, global), work items with a
breakdown by state group, cycles, modules, pages, comments, views, labels,
attachments, departments and staff. Plus a panel showing which sign-in methods
are enabled, read from the instance store rather than a fresh request.

### Storage

Database size with the fifteen largest tables by total size, charted and
tabulated. Row counts are `reltuples` — the estimate left by the last `ANALYZE`
— and the column says so.

Object storage is reported as **three separate figures**, never blended:

| Figure          | What it means                                                                                                               |
| --------------- | --------------------------------------------------------------------------------------------------------------------------- |
| **Scanned**     | Real bytes in the bucket. Ground truth, and the only source that sees objects with no database row. Requires a manual scan. |
| **Measured**    | Sum of real `ContentLength` readings, alongside a coverage percentage                                                       |
| **Declared**    | Sum of client-supplied sizes reserved at upload time                                                                        |
| **Reclaimable** | Soft-deleted assets plus reservations that were never fulfilled                                                             |

They disagree because they measure different things. `FileAsset.size` is
declared by the client at presign and clamped to the size limit — a
reservation, not a measurement. `storage_metadata["ContentLength"]` is a real
reading, but only present on assets that completed the v2 upload handshake.
Only a bucket scan sees what is actually on disk.

The difference between the scan and the measured total is labelled
**unreconciled**, not "orphaned": with partial coverage, the stronger word
would be a claim the data does not support.

### Inventory

Four searchable, paginated tables.

- **Workspaces** — projects, members, work items, owner, created date
- **Projects** — workspace, lead, members, work items, global and archived flags
- **Users** — email, workspace count, joined, last login, with row actions
- **Invites** — outstanding invites, with the form that creates them

---

## User management

Reached from the row actions on the **Users** table.

### Rename

Changes `display_name` only. The email address and username are untouched —
they are the account's login key and identity, and sessions and audit trails
are keyed on them. The person keeps their user name; only the label changes.

### Deactivate and reactivate

Deactivating sets `is_active = False` and suspends the account's workspace
memberships, so they cannot sign in and disappear from member lists and
pickers. Everything they authored stays exactly where it is. Reactivating
restores both.

**There is deliberately no delete.** `User` is not soft-deletable, and Django
cascades deletes in Python across the ~300 relations that point at it.
Simulated against a real account on this instance, a delete would have removed
**173 rows across 15 models** — 31 work items, 16 states, 10 pages, 2 projects
and 81 activity records. That is unrecoverable without a database restore, and
almost never what "remove this person" means.

Two guards refuse the request outright, because recovering from either needs
shell access:

- You cannot deactivate your own account.
- You cannot deactivate the last super admin who can still sign in.

One asymmetry worth knowing: reactivation restores _every_ workspace membership.
Someone who had been removed from a single workspace before the account was
deactivated comes back to it. Re-removing them is one click, which is a better
trade than persisting per-membership state for this case.

### Named invite links

The stock invite flow emails a link. This instance has **no SMTP configured**,
so those invites are created and then silently go nowhere. These invites return
the link instead, for you to send however you like.

An invite carries an optional **name**. A new account otherwise derives its
display name from the local part of the email address — `j.smith` from
`j.smith@example.com` — so naming the person up front means the account arrives
correctly labelled instead of needing a rename afterwards. The name is applied
on acceptance, and **only if the account never chose one for itself**: a name
someone set is theirs, and a second invite will not overwrite it.

The link and token are exactly what the email flow produces, so acceptance runs
through the same code path with the same validation. Re-inviting the same
address updates the outstanding invite rather than colliding with the
`(email, workspace)` uniqueness constraint — useful for correcting a
misspelled name or changing the role.

---

## API

All endpoints live under `/api/instance-dashboard/`.

| Method     | Path                               | Purpose                              | Cache      |
| ---------- | ---------------------------------- | ------------------------------------ | ---------- |
| GET        | `health/`                          | Service probes and runtime info      | 15s        |
| GET        | `overview/`                        | Instance-wide entity counts          | 60s        |
| GET        | `storage/`                         | Database and asset rollups           | 300s       |
| GET / POST | `storage/bucket-scan/`             | Read or trigger an object-store scan | manual, 6h |
| GET        | `workspaces/` `users/` `projects/` | Paginated inventories, `?search=`    | —          |
| GET        | `scheduled-jobs/`                  | Beat schedule with staleness         | 30s        |
| PATCH      | `users/<id>/`                      | Rename, deactivate, reactivate       | —          |
| GET / POST | `invites/`                         | List or create named invites         | —          |
| DELETE     | `invites/<id>/`                    | Revoke an outstanding invite         | —          |

### Why not `/api/instances/`

This is the single most important thing to know before changing any of these
routes.

`plane/authentication/middleware/session.py` picks which session cookie to read
by testing whether the substring `instances` appears anywhere in the request
path:

```python
if "instances" in request.path:
    session_key = request.COOKIES.get(settings.ADMIN_SESSION_COOKIE_NAME)  # admin-session-id
else:
    session_key = request.COOKIES.get(settings.SESSION_COOKIE_NAME)        # session-id
```

The dashboard is served to `apps/web`, whose users hold the _app_ cookie. A path
under `/api/instances/` would send the middleware looking for a cookie the
browser does not have, produce an empty session, resolve `AnonymousUser`, and
return 403 to a signed-in administrator — with nothing in the logs to explain
it.

Because the test is a substring rather than a prefix, renaming this namespace to
anything containing `instances` breaks authentication silently.
`plane/tests/unit/views/test_instance_dashboard_permissions.py` asserts no route
ever matches, and its failure message explains why. If that test fails, rename
the route back rather than "fixing" the test.

---

## Operational notes

**Probes never hang the page.** Each sets its own short timeouts and returns a
result instead of raising; the view guards each one separately. The shared
helpers were unsuitable and are deliberately not used here: `redis_instance()`
sets no socket timeout, and `S3Storage` inherits botocore's defaults (60s
connect, 60s read, five retries) and rewrites its endpoint to the public host
when handed a request. A wedged dependency would have hung the dashboard for
minutes.

**The cache is one of the things being monitored.** The stock `cache_response`
decorator calls `cache.get()` unguarded, and the cache backend is Redis — so
with Redis down the health page failed before the view ever ran, and the probe
that would have reported it never executed. These endpoints use
`resilient_cache_response`, which degrades to uncached instead of failing.

**A down broker short-circuits worker inspection.** Celery's `inspect`
broadcasts over the broker and waits the full timeout regardless, so with
RabbitMQ down it can only cost time. Health then reports workers as `unknown`
with the reason, and the whole response lands in ~60 ms instead of ~3 s.

**Worker inspection dominates a cold load.** `inspect` cannot know how many
workers should reply, so it always waits out its timeout — currently 1.5s, twice.
Expect a cold `/health/` around 3 s and a warm one in single-digit milliseconds.

**Bucket scans are bounded and manual.** 20 seconds of wall clock or 500,000
objects, whichever comes first, then `truncated: true` and the UI says the total
is a lower bound. Results cache for six hours and a lock prevents two admins
scanning at once.

**Credentials never reach the response.** `AMQP_URL` contains the broker
password and SMTP config contains its own; every error string is scrubbed and
truncated before it leaves the server.

**There is no task history.** `CELERY_RESULT_BACKEND` is not configured and
`django_celery_results` is not installed, so beat's `last_run_at` is the only
evidence the scheduler is alive. The UI does not imply otherwise.

---

## Where the code lives

**Backend** — `apps/api/plane/`

```
app/views/instance_dashboard/    base · health · overview · storage
                                 listings · jobs · users · invites · caching
app/urls/instance_dashboard.py   routes (no path may contain "instances")
utils/instance_probes.py         probe_* helpers, shared with God Mode monitoring
utils/instance_storage.py        postgres_sizes, asset_storage_rollup, scan_bucket
license/utils/instance_counts.py counts, shared with the telemetry tracer
```

**Frontend** — `apps/web/`

```
app/(all)/dashboard/                    layout (auth + admin gate) and page
ce/components/instance-dashboard/       root · gate · constants
  common/     panel-card · stat-card · status-pill · format
  health/     health-panel · service-card · workers-card · scheduled-jobs-card · runtime-card
  overview/   overview-panel · counts-grid · work-items-state-chart · instance-info-card
  storage/    storage-panel · postgres-card · object-storage-card · workspace-storage-card
  listings/   listings-panel · users/workspaces/projects/invites tables · modals
```

**Shared** — `packages/types/src/instance-dashboard.ts`,
`packages/services/src/instance/instance-dashboard.service.ts`, and the
`instance_dashboard.*` block in `packages/i18n/src/locales/en/translations.ts`.

Panels use plain SWR rather than a MobX store: the page is read-only, and
per-panel keys give each card its own loading and error state — the client-side
mirror of the server-side probe isolation.

---

## Tests

```
apps/api/plane/tests/unit/views/
  test_instance_dashboard_permissions.py     access control + the "instances" route guard
  test_instance_dashboard_probes.py          one dead dependency does not 500 the page
  test_instance_dashboard_storage.py         three-figure arithmetic, malformed JSON metadata
  test_instance_dashboard_counts.py          telemetry extraction parity
  test_instance_dashboard_user_management.py rename, deactivation guards, invites
```

Run with `./scripts/dev-site-test.sh plane/tests/unit/views/` or
`cd apps/api && python run_tests.py`.

---

## Related

- [Feature Reference](./features.md) — every feature and its code
- [System Architecture](./system-architecture.md) — the dashboard subsystem in context
- [Health Monitoring](./deployment/health-monitoring.md) — deployment-level checks
- [Codebase Summary](./codebase-summary.md) — repository map
