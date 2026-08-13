# System Architecture

## High-Level Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        Internet / Users                          │
└────────────────────────────────┬────────────────────────────────┘
                                 │
                    ┌────────────┴────────────┐
                    │  Caddy Reverse Proxy    │
                    │  (apps/proxy)           │
                    └────┬──────┬──────┬──────┘
         ┌──────────────┬─┘      │      └┬──────────────────┐
         │              │        │       │                  │
    ┌────▼───┐  ┌──────▼──┐ ┌───▼───┐ ┌▼────────┐  ┌──────▼──┐
    │ web    │  │  admin  │ │ space │ │ live    │  │ Webhook │
    │ (3000) │  │ (3001)  │ │ (3002)│ │ (3003)  │  │ Handler │
    └─┬──────┘  └────┬────┘ └───┬───┘ └────┬────┘  └─────────┘
      │              │          │          │
      └──────────────┴──────────┴──────────┘
                     │
            ┌────────▼────────┐
            │  Django API     │
            │  (apps/api:8000)│
            │  10-layer stack │
            └────────┬────────┘
                     │
      ┌──────────────┼──────────────┐
      │              │              │
   ┌──▼──┐      ┌───▼────┐     ┌──▼──┐
   │ PG  │      │ Redis  │     │ S3  │
   └─────┘      └────┬───┘     └─────┘
           ┌────────────┴──────────┐
           │                       │
       ┌───▼────┐          ┌──────▼─┐
       │ Cache  │          │ Session│
       │ Layers │          │ Store  │
       └────────┘          └────────┘
                     │
            ┌────────▼──────────┐
            │  RabbitMQ Broker  │
            │  (Celery Queue)   │
            └────────┬──────────┘
                     │
         ┌───────────┴────────────┐
         │                        │
    ┌────▼─────┐          ┌──────▼──┐
    │  Workers │          │  Beat   │
    │ (Celery) │          │Scheduler│
    └──────────┘          └─────────┘
```

## Frontend Architecture

### React Application Structure (apps/web)

```
apps/web/
├── core/                           # Upstream code (read-only)
│   ├── app/                        # React Router v7 route tree
│   │   ├── layout.tsx              # Root layout
│   │   ├── (auth)/                 # Auth routes (login, signup)
│   │   └── (all)/[workspaceSlug]/  # Main app routes
│   │
│   ├── store/                      # MobX stores (33+)
│   │   ├── root-store.ts           # Root store
│   │   ├── workspace.store.ts      # Workspace root store
│   │   ├── project.store.ts        # Project root store
│   │   ├── issue.store.ts          # Issue root store (multi-layout)
│   │   ├── cycle.store.ts          # Cycle (sprint) store
│   │   ├── module.store.ts         # Module store
│   │   ├── page.store.ts           # Page (wiki) store
│   │   └── [other].store.ts
│   │
│   ├── hooks/                      # Custom hooks (47 total)
│   │   ├── store/                  # Store access hooks
│   │   │   ├── use-workspace.ts
│   │   │   ├── use-project.ts
│   │   │   ├── use-issue.ts
│   │   │   └── use-workflow.ts    # Reads CE store
│   │   ├── use-issue-form.ts
│   │   ├── use-drag-n-drop.ts
│   │   └── [other].ts
│   │
│   ├── services/                   # API clients (30+)
│   │   ├── api-base.ts             # Axios instance
│   │   ├── workspace.service.ts
│   │   ├── issue.service.ts
│   │   └── [other].service.ts
│   │
│   ├── components/                 # Shared components (51 dirs)
│   │   ├── layouts/
│   │   ├── modals/
│   │   ├── form/
│   │   ├── issue-layouts/          # List, Kanban, Gantt, Calendar, Sheet
│   │   └── [other]/
│   │
│   └── context/                    # React context
│       └── store-context.ts        # Provides RootStore
│
├── ce/                             # Fork customizations (extend core)
│   ├── store/
│   │   ├── root.store.ts           # Extends CoreRootStore
│   │   ├── workflow.store.ts       # Workflow MobX store
│   │   ├── time-tracking.store.ts  # Time tracking store
│   │   ├── ho.store.ts             # Org chart (HO) store
│   │   ├── analytics.store.ts      # Analytics dashboard store
│   │   ├── task-category.store.ts  # Task categories store
│   │   └── monitoring.store.ts     # Monitoring dashboard store
│   │
│   ├── services/
│   │   ├── workflow.service.ts
│   │   ├── time-tracking.service.ts
│   │   ├── ho.service.ts
│   │   ├── analytics.service.ts
│   │   ├── task-category.service.ts
│   │   └── monitoring.service.ts
│   │
│   └── components/
│       ├── workflow/                # Workflow UI
│       │   ├── use-workflow-drag-n-drop.ts  # Kanban DnD hook
│       │   ├── kanban-group.tsx
│       │   └── workflow-blocker-modal.tsx
│       ├── time-tracking/           # Time tracking UI
│       ├── ho/                       # Org chart UI
│       ├── analytics/                # Analytics dashboard UI
│       ├── task-category/            # Task categories admin UI
│       ├── monitoring/               # Monitoring dashboard UI
│       └── [other]/
│
├── app/                            # Old routing (gradual migration)
└── tsconfig.json                   # Path aliases
    # @/* → core/*
    # @/plane-web/* → ce/*
```

### State Management (MobX)

**Store Hierarchy:**

```
RootStore (ce/store/root.store.ts extends CoreRootStore)
├── workspaceStore: WorkspaceRootStore
│   └── workspaces: Map<id, Workspace>
├── projectStore: ProjectRootStore
│   └── projects: Map<id, Project>
├── issueStore: IssueRootStore
│   ├── issues: Map<id, Issue>
│   ├── issueFilters: IssueFilters
│   ├── issueLayouts: "list" | "kanban" | "gantt" | "calendar" | "spreadsheet"
│   └── issueDetails: Map<id, DetailedIssue>
├── cycleStore: CycleRootStore
├── moduleStore: ModuleRootStore
├── pageStore: PageRootStore
├── workflowStore: WorkflowRootStore (CE)
│   └── workflows: Map<projectId, Workflow>
├── timeTrackingStore: TimeTrackingRootStore (CE)
│   └── timeLogs: Map<issueId, TimeLog[]>
├── hoStore: HORootStore (CE)
│   └── orgChart: OrgNode[]
├── analyticsStore: AnalyticsRootStore (CE)
│   └── dashboardData: Map<projectId, AnalyticsData>
├── taskCategoryStore: TaskCategoryRootStore (CE)
│   └── categories: Map<workspaceId, TaskCategory[]>
└── workflowStore: WorkflowStore (CE)
    └── workflows: Map<projectId, ProjectWorkflow>
```

**Data Flow:**

```
User Action (click, drag, form submit)
    ↓
Hook (useIssue, useWorkflow)
    ↓
Store.action (updateIssue, moveIssueToState)
    ↓
Service.fetch (issueService.update)
    ↓
API v0 (PUT /api/v0/issues/{id}/)
    ↓
Store.runInAction (apply response data)
    ↓
Component re-renders (via observer)
```

### Issue Layouts (Multi-View, Single Store)

**Architecture:**

```
IssueRootStore (single source of truth)
├── issues: Map<id, Issue>
├── filters: IssueFilters
├── sortBy: string
└── groupBy: string

Layout Selector (in project view)
├─ List View   → ListLayout component
├─ Kanban      → KanbanLayout component (with DnD)
├─ Gantt       → GanttLayout component
├─ Calendar    → CalendarLayout component
└─ Spreadsheet → SpreadsheetLayout component

All layouts read from same store
All mutations update same store
Switching layouts = changing view, not refetching
```

**Kanban with DnD & Workflow Validation:**

```
KanbanLayout
├── KanbanGroup (per state, one per column)
│   ├── useWorkflowFDragNDrop hook
│   │   ├── Validates state transition via workflow
│   │   └── Returns: disabled flags, handleWorkFlowState
│   ├── IssueCard (Atlaskit pragmatic DnD)
│   └── onDragEnter → handleWorkFlowState(source, dest)
│
└── Blocked transition
    └── throw WORKFLOW_TRANSITION_BLOCKED
        └── unhandledrejection event
            └── WorkflowBlockerModal catches & shows reason
```

## Backend Architecture

### Django Application Structure (apps/api)

```
apps/api/
├── plane/
│   ├── settings/
│   │   ├── common.py         # Core Django config (DB, Redis, RabbitMQ, S3)
│   │   ├── production.py     # Production overrides
│   │   ├── local.py          # Local dev overrides
│   │   ├── test.py           # Test overrides (excludes django_celery_beat)
│   │   ├── redis.py          # Redis client helper
│   │   └── storage.py        # S3Storage backend
│   ├── urls.py               # Root URLconf
│   ├── asgi.py               # ASGI entry
│   ├── celery.py             # Celery app + beat_schedule
│   │
│   ├── db/
│   │   ├── models/           # 44 model modules
│   │   │   ├── workspace.py  # Workspace, WorkspaceMember
│   │   │   ├── project.py    # Project, ProjectMember
│   │   │   ├── issue.py      # Issue, IssueLabel, IssueLink
│   │   │   ├── cycle.py      # Cycle, CycleIssue
│   │   │   ├── module.py     # Module, ModuleIssue
│   │   │   ├── page.py       # Page, PageBlock
│   │   │   ├── state.py      # State (workflow states)
│   │   │   ├── workflow.py   # ProjectWorkflow, WorkflowTransition (fork)
│   │   │   ├── worklog.py    # IssueWorkLog (fork)
│   │   │   └── [other].py
│   │   └── managers.py       # SoftDeletionManager, etc.
│   │
│   ├── app/
│   │   ├── views/            # DRF ViewSets (41+ endpoints)
│   │   │   ├── workspace/
│   │   │   ├── project/
│   │   │   ├── issue/
│   │   │   ├── cycle/
│   │   │   ├── module/
│   │   │   ├── page/
│   │   │   ├── workflow/     # CE endpoints
│   │   │   └── [other]/
│   │   │
│   │   ├── serializers/
│   │   │   ├── v0/           # Session auth (internal)
│   │   │   │   ├── issue.py
│   │   │   │   └── [other].py
│   │   │   └── v1/           # API key auth (external)
│   │   │       ├── issue.py
│   │   │       └── [other].py
│   │   │
│   │   ├── permissions.py    # Custom DRF permissions
│   │   └── authentication.py # API key + Session auth
│   │
│   ├── utils/
│   │   ├── workflow_checker.py   # Workflow transition validation
│   │   ├── decorators.py         # @allow_permission decorator
│   │   ├── export.py             # CSV/JSON export logic
│   │   └── [other].py
│   │
│   ├── middleware/
│   │   ├── auth.py               # Session/API key extraction
│   │   ├── logging.py            # Request/response logging
│   │   ├── workspace.py          # Workspace detection
│   │   ├── read_replica.py       # Route reads vs writes
│   │   └── [9 more layers]
│   │
│   ├── tasks/                    # Celery async tasks (41 tasks)
│   │   ├── notification.py       # Email, Slack, webhooks
│   │   ├── activity.py           # Activity logging
│   │   ├── export.py             # CSV/PDF exports to S3
│   │   └── [other].py
│   │
│   └── constants/
│       ├── roles.py              # ROLE.ADMIN, MEMBER, GUEST
│       └── [other].py
│
├── manage.py
├── requirements.txt
└── Dockerfile
```

### Request Pipeline (10-Layer Middleware)

```
HTTP Request
    ↓
1. CORS Middleware           (Domain validation)
    ↓
2. Auth Middleware           (Extract session/API key)
    ↓
3. Logging Middleware        (Winston structured logs)
    ↓
4. Workspace Detection       (Slug → workspace_id)
    ↓
5. Read-Replica Router       (Route to read/write DB)
    ↓
6. Rate Limiting            (Per user/API key)
    ↓
7. GZip Compression         (Response compression)
    ↓
8. Request Validation       (Schema validation)
    ↓
9. @allow_permission Check  (RBAC: ADMIN/MEMBER/GUEST)
    ↓
10. View Logic              (DRF serializers, queryset)
    ↓
Response (JSON)
```

### The two API layers

There are two API layers, and they are separated by _module_, not by a version
segment in the path.

**Application API — `plane/app/`**

- Used by `apps/web`, `apps/admin` and `apps/space`
- Django session cookie (`BaseSessionAuthentication`, CSRF disabled for REST)
- Mounted at `/api/` from `plane/urls.py`
- Views in `plane/app/views/`, serializers in `plane/app/serializers/`

**External API — `plane/api/`**

- Used by third-party integrations
- Header API key: `X-API-KEY`
- Mounted at `/api/v1/`, OpenAPI docs at `/api/v1/docs/`
- Views in `plane/api/views/`, serializers in `plane/api/serializers/`

**God-mode API — `plane/license/`**

- Used by `apps/admin` only
- A _separate session cookie_ (`admin-session-id`) — see below
- Mounted at `/api/instances/`
- Menu RBAC by URL prefix via `plane/license/menu_registry.py`

**Never share serializers across layers.** A `plane/app/serializers/*` class
must not be used from a `plane/api/` view or vice versa; the field sets and
permission assumptions differ.

### The session-cookie split

`plane/authentication/middleware/session.py` selects the session cookie by
testing whether the substring `instances` occurs anywhere in `request.path`:

```python
if "instances" in request.path:
    session_key = request.COOKIES.get(settings.ADMIN_SESSION_COOKIE_NAME)  # admin-session-id
else:
    session_key = request.COOKIES.get(settings.SESSION_COOKIE_NAME)        # session-id
```

Web and god-mode therefore share an origin but not a session. A user signed
into the web app cannot call `/api/instances/*` at all — the middleware finds
no cookie and resolves `AnonymousUser`.

Because the test is a substring rather than a prefix, any new route containing
`instances` silently switches cookies. This is why the instance dashboard
lives at `/api/instance-dashboard/`, and why a test asserts the name never
drifts into matching.

### User & Profile Endpoints (V0 API)

Cross-workspace aggregation for performance (Session auth, internal use).

| Method | Path                                | Auth            | Purpose                                                    |
| ------ | ----------------------------------- | --------------- | ---------------------------------------------------------- |
| GET    | `/api/users/me/work-items/today/`   | Session + login | Open issues assigned to user, not yet overdue (≤200 items) |
| GET    | `/api/users/me/work-items/overdue/` | Session + login | Open issues assigned to user, past due (≤200 items)        |

**Parameters:**

- `?workspace=<slug>` (optional) — Filter to single workspace; default: all workspaces

**Serializer:** `UserCrossWorkspaceWorkItemSerializer` — ID-only response (minimal payload):

- `id`, `name`, `identifier`, `state_id`, `priority`, `target_date`
- `assignee_ids: UUID[]` (list of assignee IDs, not objects)
- `label_ids: UUID[]` (list of label IDs, not objects)
- `workspace_id`, `project_id`

**Filters:**

- Assignee = current user
- Active workspace membership (`workspace_member.is_active=True`)
- Active project membership (`project_member.is_active=True`)
- Project not archived
- State group in {backlog, unstarted, started} (open tasks only)
- Parent is null (excludes sub-tasks — critical for accuracy)

**Query optimization:**

- `use_read_replica=True` — read-only queries
- `select_related("workspace", "project", "state")` — joins on meta
- `prefetch_related("assignees", "labels")` — bulk-fetch relationships
- Supports DB partial index `issues_workitems_idx` on `(target_date, state_id) WHERE parent_id IS NULL AND deleted_at IS NULL AND archived_at IS NULL AND is_draft=FALSE`

**Capping:** 200-item hard limit (KISS principle; sub-task exclusion + state filter keeps real-world counts much lower).

**Feature flag:** `VITE_USE_AGGREGATE_PROFILE_ENDPOINT` (frontend env var, default `"true"`). When `"false"`, UI falls back to legacy client-side fan-out across individual workspace profile endpoints.

### Database Schema

**Core Hierarchy:**

```
Workspace
├── WorkspaceMember (user, role, join_date)
├── Project
│   ├── ProjectMember (user, role)
│   ├── Issue
│   │   ├── IssueFavorite
│   │   ├── IssueLabel
│   │   ├── IssueLink (parent/duplicate/related)
│   │   ├── IssueActivity (audit trail)
│   │   └── TimeLog (CE)
│   ├── Cycle (sprints)
│   │   └── CycleIssue (M2M)
│   ├── Module (features)
│   │   └── ModuleIssue (M2M)
│   ├── State (workflow states)
│   │   └── WorkflowTransition (CE, state A → B)
│   ├── Label
│   ├── Priority
│   ├── Estimate
│   ├── Page (wiki)
│   │   └── PageBlock (nested blocks)
│   ├── PageFavorite
│   └── ProjectTemplate
│
├── Notification
├── Webhook
│   └── WebhookLog
└── Activity (audit log, workspace-level)
```

**Key Features:**

- Soft delete: `deleted_at` field with unique constraint conditions
- Audit trail: `created_by`, `updated_by` foreignkeys
- Timestamps: `created_at`, `updated_at` auto-set
- Indexing: Frequent queries indexed
- Relationships: `select_related()` + `prefetch_related()`

### Celery Task Queue

**Broker:** RabbitMQ
**Result Backend:** Redis
**Scheduler:** Celery Beat

**Task Categories (41+ tasks):**

| Category             | Tasks | Examples                                                                          |
| -------------------- | ----- | --------------------------------------------------------------------------------- |
| **Notifications**    | 8     | Email notification, Slack webhook, user mention                                   |
| **Webhooks**         | 6     | Send webhook event, retry failed delivery                                         |
| **Activity Logging** | 5     | Log issue state change, activity digest                                           |
| **Exports**          | 4     | CSV export, PDF report generation                                                 |
| **Cleanup**          | 6     | Archive soft-deleted issues, expire sessions                                      |
| **Analytics**        | 3     | Generate dashboard data, report aggregation                                       |
| **Real-Time Sync**   | 5     | Update WebSocket connections, Y.js sync                                           |
| **CE-Specific**      | 4+    | Time log processing, org chart updates, analytics computation, monitoring metrics |

**Async Patterns:**

```python
# View triggers task
@allow_permission("project.member")
def create_issue(request, workspace_slug, project_slug):
    issue = Issue.objects.create(...)
    # Fire async task
    send_issue_notification.delay(issue.id, request.user.id)
    return Response(issue_serializer.data, status=201)

# Task runs in worker
@shared_task
def send_issue_notification(issue_id, user_id):
    issue = Issue.objects.get(id=issue_id)
    user = User.objects.get(id=user_id)
    # Send email
    send_mail(...)
```

## Real-Time Architecture (apps/live)

```
WebSocket Server (Hocuspocus + Y.js CRDT)
    ↓
┌─────────────────────────────────┐
│ Shared Document State (Y.Doc)   │
│ ├─ PageBlock edits (text, rich) │
│ ├─ Issue updates (fields)       │
│ └─ Cursors/Awareness (future)   │
└─────────────────────────────────┘
    ↓
Y.js CRDT Engine (Conflict-Free)
    ↓
Broadcast to all connected clients
    ↓
ClientA, ClientB, ClientC receive updates
```

**Characteristics:**

- Operational Transform (CRDT): No conflict on concurrent edits
- Websocket upgrade from HTTP
- Y.js Awareness for presence (cursors, user colors)
- Persistent state: Y.js IndexedDB adapter
- Scalable: Y.js can scale to 10k+ users per document

## Reverse Proxy (Caddy)

```
caddy reverse proxy (apps/proxy)
    ↓
Route by Host/Path:
├── /api/* → :8000 (Django API)
├── /live/* → :3003 (Websocket)
├── /admin* → :3001 (Admin panel)
├── /space/* → :3002 (Public projects)
└── /* → :3000 (React web)
```

**Responsibilities:**

- TLS/SSL termination
- Load balancing
- Rate limiting
- Static file caching
- Gzip compression

## Data Flow Diagram: Creating an Issue

```
User submits form
    ↓
useIssueForm hook (useMemo)
    ↓
issueService.createIssue (POST /api/v0/issues/)
    ↓
Django View (IssueViewSet.create)
    ├─ @allow_permission("project.member")
    ├─ Serializer validation
    ├─ Issue.objects.create()
    ├─ Fire Celery task: send_issue_notification.delay()
    └─ Return IssueSerializer(issue)
    ↓
issueStore.addIssue(response)
    ├─ issues.set(id, new_issue)
    ├─ runInAction()
    └─ Notify observers
    ↓
List/Kanban/Gantt view re-renders
    ↓
New issue appears in all layouts
```

## Scalability & Performance

### Caching Strategy

| Layer              | Tool                 | Data                                 | TTL           |
| ------------------ | -------------------- | ------------------------------------ | ------------- |
| **Browser**        | LocalStorage         | User preferences, UI state           | Session       |
| **HTTP Cache**     | ETags, Cache-Control | API responses                        | Varies        |
| **Redis Cache**    | Redis                | Workspace/project metadata, sessions | 1h            |
| **DB Query Cache** | ORM select/prefetch  | Related objects                      | Request scope |

### Database Optimization

- **Indexing:** Frequent filter fields indexed
- **Denormalization:** Count fields cached (issue_count on project)
- **Query optimization:** No N+1 queries (select_related, prefetch_related)
- **Read replicas:** Middleware routes reads to replicas
- **Connection pooling:** Psycopg2 pool (10-20 connections)

### Frontend Optimization

- **Code splitting:** Route-based chunks (Vite)
- **Image optimization:** WebP, lazy loading
- **Tree shaking:** Unused code removed (Webpack)
- **Kanban virtualization:** Only visible items rendered
- **MobX optimization:** Fine-grained reactivity

## Security

### Authentication & Authorization

**Authentication:**

- V0 API: Django session (cookie-based)
- V1 API: API Key (header-based)
- CSRF protection: Token validation

**Authorization (RBAC):**

```python
@allow_permission("workspace.member")  # User is workspace member
@allow_permission("project.member")    # User is project member
@allow_permission("workspace.admin")   # User is workspace admin
```

Roles per level:

- Workspace: ADMIN, MEMBER, GUEST
- Project: ADMIN, MEMBER, GUEST

**God Mode (instance admin) menu RBAC:**

- `InstanceAdmin` carries `is_super_admin` + `allowed_menus` (12 grantable keys in `plane/license/menu_registry.py`; `authentication`/general/email/ai/image config screens share the grouped `settings` key — all five persist through one `InstanceConfigurationEndpoint`).
- Enforcement is **route-group / URL-prefix based and fail-closed**: `InstanceAdminMenuPermission` resolves the required menu from `request.path` via `PREFIX_MENU_MAP` (longest-prefix). Unmapped paths deny scoped admins; identity/session paths (`admins/me|session|sign-*`) are shared; super-admins bypass. Views carry no per-class menu annotation.
- Coverage is build-enforced: `plane/tests/unit/test_menu_registry_parity.py` fails if any `/api/instances/` route is unmapped, any view re-introduces the bare pre-RBAC `InstanceAdminPermission`, or the admin-app sidebar permission keys drift from the backend registry.
- Management: `POST/PATCH/DELETE /api/instances/admins/` — only super-admins mint super-admins; `administrators`-menu admins grant only subsets of their own menus and never edit their own row. Lockout guards protect the last active loginable super-admin (ghost `user=NULL` and inactive rows never count) across admin demote/delete, user deactivation, password reset, and staff deactivation.
- Admin app sidebar (`apps/admin/hooks/use-sidebar-menu/`) filters by `currentUser.allowed_menus`; a layout-level guard redirects ungranted direct navigation. UI filtering is cosmetic — the backend permission is the security boundary.

**God-mode workspace ownership:**

- Workspaces created from God Mode are owned by the **General Director** (the single active staff with `job_grade="GD"`, resolved by `plane/utils/general_director.py`) or an explicitly chosen user — never the acting instance admin, who receives no `WorkspaceMember`/`ProjectMember` row on any creation/import path (attribution `created_by` stays the actor).
- Owner precedence: explicit `owner_id`/`owner_email` > GD; unresolvable or ambiguous GD fails with 400. `GET /api/instances/workspaces/owner-options/` feeds the create-form picker (staff-directory enumeration gated behind the `staff`/`users` menu).

### Data Security

- **Soft delete:** Data preserved, not deleted
- **Audit trail:** All changes logged (created_by, updated_by)
- **API scoping:** Queries filtered by workspace slug
- **S3 upload:** Pre-signed URLs, no direct access
- **Secrets:** Env vars (never hardcoded)

## Monitoring & Observability

**Logging:**

- Winston structured JSON logs
- Correlation IDs for request tracing
- Log levels: ERROR, WARN, INFO, DEBUG
- Central log aggregation (future)

**Metrics:**

- APM: Request duration, error rates
- Database: Query count, execution time
- Celery: Task success/fail rates
- Redis: Cache hit rates

**Health Check:**

- Endpoint: `/health`
- Checks: DB connection, Redis, RabbitMQ
- Response: JSON status

---

## Business Calendar Subsystem

> Plan: `plans/260428-1427-vietnam-working-day-holiday-management/`
> Research: `plans/reports/researcher-260428-1412-vietnam-working-day-holiday-management.md`

### Overview

Manual, god-mode source-of-truth for Vietnamese working-day rules. No third-party calendar API, no auto-import. Instance admins define schedules, holidays, and day overrides via the `/calendar` admin UI; Celery tasks consult the service at invocation time.

**Design goals:** deterministic (same inputs → same result), fail-open (calendar errors never block critical background jobs), cache-backed (TTL 1 day, signal-invalidated on any data change).

### Data Model

```
WorkSchedule (1) ──────────┬── Holiday (N)
  id, name                 │     id, schedule_fk, date, name
  week_pattern[7] bool     │
  timezone (Asia/HCM)      └── DayOverride (N)
  is_default bool                id, schedule_fk, date
  country_code "VN"              type WORKDAY|HOLIDAY
  workspace_fk (null=instance)   reason, swap_with_date
```

**Resolution priority** (highest wins):

1. `DayOverride` for the date → WORKDAY or HOLIDAY
2. `Holiday` for the date → not working
3. `week_pattern[weekday]` → True/False

### Service

`plane/utils/business_calendar/service.py` — `BusinessCalendarService` (all class methods, no state):

| Method                 | Signature                              | Purpose                   |
| ---------------------- | -------------------------------------- | ------------------------- |
| `is_working_day`       | `(d, schedule_id=None) → bool`         | Core predicate            |
| `next_working_day`     | `(d, schedule_id=None) → date`         | Skip to next working date |
| `add_business_days`    | `(d, n, schedule_id=None) → date`      | Walk forward/back N days  |
| `working_days_between` | `(start, end, schedule_id=None) → int` | Count half-open interval  |

**Cache:** `calendar:{schedule_id}:{year}` → serialised holiday+override dict, TTL 86400 s.

**Signal invalidation** (`plane/db/models/business_calendar.py`):

- `Holiday` post_save/post_delete → `cache.delete(calendar:{schedule_id}:{year})`
- `DayOverride` post_save/post_delete → same
- `WorkSchedule` post_delete (hard) → year-range sweep; post_save with `deleted_at` set → same

Signals auto-imported in `plane/db/apps.py` `ready()`.

### API

Instance-admin layer at `plane/license/api/` — requires `InstanceAdminPermission`.

| Method           | Path                                                      | Action                          |
| ---------------- | --------------------------------------------------------- | ------------------------------- |
| GET/POST         | `/api/instances/calendar/schedules/`                      | List / create schedules         |
| GET/PATCH/DELETE | `/api/instances/calendar/schedules/{id}/`                 | Retrieve / update / soft-delete |
| GET/POST         | `/api/instances/calendar/schedules/{id}/holidays/`        | List / bulk-create holidays     |
| DELETE           | `/api/instances/calendar/schedules/{id}/holidays/{hid}/`  | Delete holiday                  |
| GET/POST         | `/api/instances/calendar/schedules/{id}/overrides/`       | List / create overrides         |
| DELETE           | `/api/instances/calendar/schedules/{id}/overrides/{oid}/` | Delete override                 |
| POST             | `/api/instances/calendar/schedules/{id}/copy-year/`       | Bulk-copy one year to another   |
| GET              | `/api/instances/calendar/schedules/default/`              | Resolve instance default        |

### UI

`apps/admin` — route `/calendar`:

- Workweek toggle panel (Mon–Sun checkboxes per schedule)
- Holidays grid (date + name, inline add/delete, grouped by month)
- Overrides table (date, type WORKDAY/HOLIDAY, reason, swap-with link)
- Copy-year action (clone all holidays/overrides from year A to year B)

### Celery Integration

`plane/utils/celery_helpers.py` — `working_day_required()` decorator factory:

```python
@shared_task          # outermost — Celery registers it
@working_day_required()  # inner — guard runs at invocation
def archive_and_close_old_issues(): ...
```

**Fail-open:** if `BusinessCalendarService` raises, logs exception and runs task anyway.
**Log on skip:** `INFO plane.utils.celery_helpers "Skip {task}: {date} is not a working day"`.
The timezone comes from `BUSINESS_CALENDAR_TIMEZONE` (`CALENDAR_TZ`, default `UTC`).

---

## Instance Dashboard Subsystem

An instance-admin-only operational view at `/dashboard`, served by `apps/web`.
Full documentation: [Instance Dashboard](./instance-dashboard.md).

### Why it is not under `/api/instances/`

The session middleware reads the god-mode cookie for any path containing
`instances` (see _The session-cookie split_). Since the dashboard is served to
the web app, mounting it there would 403 every request. It lives at
`/api/instance-dashboard/` under `plane.app.urls`, guarded by
`InstanceAdminPermission` — which checks the same thing the client-side gate
(`GET /api/users/me/instance-admin/`) checks, so the two agree.

### Probes

`plane/utils/instance_probes.py` exposes one probe per dependency. Every probe
returns `{status, latency_ms, error, details}` and never raises; the view wraps
each in its own guard, so one dead service renders as a red card rather than a 500.

| Probe          | Mechanism                                                    | Timeout |
| -------------- | ------------------------------------------------------------ | ------- |
| Postgres       | `connection.cursor()`, `SET LOCAL statement_timeout`         | 3s      |
| Redis          | probe-local client with socket timeouts                      | 2s      |
| RabbitMQ       | kombu `queue_declare(passive=True)`, fresh channel per queue | 3s      |
| Object storage | `head_bucket` on a short-timeout boto3 client                | 2+5s    |
| Celery workers | `app.control.inspect()`                                      | 3s ×2   |
| Celery beat    | `PeriodicTask.last_run_at` vs schedule                       | DB      |

The three network probes run in a `ThreadPoolExecutor`; Postgres stays on the
request thread because Django connections are thread-local. If the broker
probes down, worker inspection is skipped rather than paying the timeout again.

Two deliberate departures from the shared helpers: `redis_instance()` sets no
socket timeout, and `S3Storage` inherits botocore's 60s/5-retry defaults and
rewrites its endpoint to the public host when given a request. Neither is safe
for a health check.

Credentials are scrubbed from every error string — `AMQP_URL` contains the
broker password.

### Storage measurement

Three sources disagree about how much space is used, and the dashboard reports
all three rather than blending them:

- `FileAsset.size` — declared by the client at presign, clamped. A reservation.
- `storage_metadata["ContentLength"]` — a real measurement, present only on
  assets that completed the v2 upload handshake.
- A bucket scan — ground truth, and the only source that sees orphans.

`measured_coverage` states what fraction is genuinely measured; the difference
between the scan and the measured total is labelled _unreconciled_, not
_orphaned_. Scans are manual, bounded to 20s / 500k objects, cached 6h, and
lock-guarded.

---

## GitHub Sync Subsystem

A project binds to one GitHub repository. Authentication is instance-wide via
`GITHUB_PERSONAL_ACCESS_TOKEN`; there are no per-project credentials.

**Issue sync** — `bgtasks/github_issue_sync_task.py` plus a push signal at
`db/signals/github_issue_push.py`. `GithubIssueLink.github_state` records the
last-observed remote state, so an update echoed back from GitHub converges
instead of ping-ponging between the two systems.

**Wiki sync** — `bgtasks/github_wiki_sync_task.py` clones
`https://x-access-token:{token}@github.com/{owner}/{repo}.wiki.git` and
round-trips pages as GFM. This is why the page-link editor extension inserts a
plain link mark rather than a mention node: mentions have no Markdown
representation and would not survive the trip.

Both run on Celery beat every five minutes, and both are registered in
`CELERY_IMPORTS` — omitting that leaves beat dispatching into an empty registry.

---

## God Mode RBAC

Instance admins hold a subset of god-mode menus in
`InstanceAdmin.allowed_menus`. Enforcement happens in
`InstanceAdminMenuPermission`, which resolves a required menu key from the
request path via `plane/license/menu_registry.py` — longest-prefix match, with
unmapped paths denied (fail-closed). Super admins bypass.

Because enforcement is by URL prefix rather than per-view annotation, one
registry covers every endpoint under `/api/instances/`, including views
declared outside `license/api/views/`. The trade is that `PERMISSION_KEYS` must
stay in lockstep with `apps/admin/hooks/use-sidebar-menu/core.ts`;
`tests/unit/test_menu_registry_parity.py` asserts it does.

---

**Last Updated:** 2026-08-13
**Version:** 1.4
