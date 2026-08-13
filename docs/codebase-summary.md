# Codebase Summary

A map of the repository: what lives where, and the entry points worth knowing
before changing anything. For _what the software does_, see
[`features.md`](./features.md). For _how the pieces fit at runtime_, see
[`system-architecture.md`](./system-architecture.md).

Counts in this document were taken from the tree and are approximate — treat
them as scale indicators, not invariants.

---

## Top level

```
apps/          web · admin · space · live · api · proxy
packages/      17 shared packages (@plane/*)
docs/          this documentation
scripts/       dev, deploy and ops scripts
.claude/rules/ engineering conventions, auto-loaded by file path
```

| App          | Stack                                                | Serves                         |
| ------------ | ---------------------------------------------------- | ------------------------------ |
| `apps/web`   | React 18 + React Router v7 + Vite, MobX, Tailwind v4 | The main application (CSR)     |
| `apps/admin` | Same stack, **English-only, no i18n**                | God Mode at `/god-mode/` (CSR) |
| `apps/space` | React Router v7 with **SSR loaders**                 | Public published boards        |
| `apps/live`  | Hocuspocus / Yjs                                     | Realtime collaborative pages   |
| `apps/api`   | Django 4.2 + DRF + Postgres + Celery                 | The backend                    |
| `apps/proxy` | Caddy                                                | One origin, routed by path     |

Caddy (`apps/proxy/Caddyfile.ce`) maps `/god-mode/*` → admin, `/api/*` → api,
and everything else → web. That single-origin routing is why the web app and
god-mode share a domain but not a session cookie (see below).

---

## Backend — `apps/api/plane/`

```
app/          The application API: views, serializers, urls (the large one)
api/          The external/public API — separate views AND serializers
license/      God Mode: instance config, admins, RBAC, monitoring
authentication/ Providers (credentials + oauth), views, session middleware
db/           Models, migrations, signals, management commands
bgtasks/      Celery tasks (52 modules)
utils/        Cross-cutting helpers
settings/     common · local · production · test · redis · storage · mongo · openapi
tests/        unit · contract · smoke
middleware/   API-token logging, request body size
web/          The bare health-check view
```

### Two API layers, never mixed

`plane/app/` and `plane/api/` each have **their own** serializers and views.
A `plane/app/serializers/*` class must not be used from a `plane/api/` view or
vice versa — see `.claude/rules/backend-serializers.md`. There is no `v0/`
or `v1/` directory; both layers are flat modules.

### Entry points

| File                              | Role                                                                                                             |
| --------------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| `plane/urls.py`                   | Root URLconf. Mounts `api/` → `plane.app.urls`, `api/instances/` → `plane.license.urls`, `""` → the health check |
| `plane/app/urls/__init__.py`      | Splats every per-domain urlpattern list                                                                          |
| `plane/app/views/base.py`         | `BaseAPIView` / `BaseViewSet` — auth, pagination, exception handling                                             |
| `plane/license/api/views/base.py` | God-mode base view, defaults to `InstanceAdminMenuPermission`                                                    |
| `plane/celery.py`                 | Celery app, `beat_schedule` (~18 jobs), DatabaseScheduler                                                        |
| `plane/settings/common.py`        | Everything: DB, Redis, RabbitMQ, S3/MinIO, sessions                                                              |

### Models — `db/models/` (44 modules)

Hierarchy is `TimeAuditModel` → `AuditModel` → `BaseModel` → `ProjectBaseModel`,
with soft delete via a custom manager. Core: `workspace`, `project`, `issue`,
`cycle`, `module`, `page`, `view`, `state`, `label`, `estimate`, `asset`,
`notification`, `webhook`, `api`, `dashboard`, `intake`.

Fork additions: `department`, `staff`, `worklog`, `workflow`, `task_category`,
`job_position`, `business_calendar`, `github_sync`, `ho_export`,
`capacity_export`, `project_copy`, `project_field_permission`.

### The session-cookie split

`authentication/middleware/session.py` chooses which cookie to read by testing
whether the literal substring `instances` appears in `request.path`:

```python
if "instances" in request.path:
    session_key = request.COOKIES.get(settings.ADMIN_SESSION_COOKIE_NAME)  # admin-session-id
else:
    session_key = request.COOKIES.get(settings.SESSION_COOKIE_NAME)        # session-id
```

Two consequences worth internalising:

1. A user signed into `apps/web` **cannot** call anything under
   `/api/instances/` — the middleware looks for a cookie they do not have and
   resolves `AnonymousUser`. God-mode endpoints are reachable only from
   god-mode.
2. The test is a _substring_, not a prefix. Any new route containing
   `instances` anywhere silently switches cookies. This is why the instance
   dashboard is mounted at `/api/instance-dashboard/` and why a test asserts
   that name never drifts.

---

## Frontend — `apps/web/`

```
app/           Routes and route-group directories
  routes/
    core.ts        Upstream routes — avoid modifying
    extended.ts    Fork routes — add here
    helper.ts      mergeRoutes(), deep-merges by `file` key
core/          Upstream shared code — do NOT modify for fork features
ce/            Fork overrides, mirrors core/
```

Aliases: `@/*` → `core/*`, `@/plane-web/*` → `ce/*`.

`mergeRoutes` merges by the `file` string, so a route in `extended.ts` that
should nest inside a core layout must repeat that layout's path **exactly**.
Route groups in parentheses — `(all)`, `(projects)`, `(settings)` — affect
nesting but not the URL.

### Data flow

```
packages/services/src/<domain>/*.service.ts   class extends APIService (axios)
        ↓
apps/web/ce/store/*.store.ts                  MobX, registered in ce/store/root.store.ts
        ↓
apps/web/ce/hooks/store/use-*.ts              useContext(StoreContext)
        ↓
component wrapped in observer()
```

Read-only pages may skip the store and use SWR directly against a service —
the [instance dashboard](./instance-dashboard.md) does, so each panel gets its
own loading and error state. Anything reading a store still needs `observer()` from `mobx-react`.

### Conventions that bite

- **i18n is mandatory in `apps/web`** (`t()` from `@plane/i18n`, keys in
  `packages/i18n/src/locales/en/translations.ts`) and **forbidden in
  `apps/admin`**, which is English-only.
- **Semantic colour tokens only** — `text-tertiary`, `bg-surface-1`,
  `bg-layer-2` for inputs. No hardcoded colours, no `dark:` variants. Chart
  fills are the one exception, since recharts needs literals.
- **Propel subpath imports** — `@plane/propel/button`, never the barrel.
- Files under 200 lines, components under 150.

---

## Packages — `packages/`

| Package                                                                                    | Contents                                                    |
| ------------------------------------------------------------------------------------------ | ----------------------------------------------------------- |
| `types`                                                                                    | All shared TypeScript types (`I` interfaces, `T` aliases)   |
| `services`                                                                                 | API service classes shared by web, admin and space          |
| `propel`                                                                                   | The current design system — prefer over `ui`                |
| `ui`                                                                                       | Legacy components still used where propel has no equivalent |
| `editor`                                                                                   | TipTap editor, extensions, markdown plugins                 |
| `i18n`                                                                                     | Translations (English only) and the `useTranslation` hook   |
| `constants`, `utils`, `hooks`, `logger`, `shared-state`, `decorators`                      | Shared primitives                                           |
| `tailwind-config`, `typescript-config`, `eslint-config`, `eslint-plugin-plane`, `codemods` | Tooling                                                     |

---

## Testing

```
apps/api/plane/tests/
  unit/       Views, models, serializers, utils
  contract/   End-to-end through the API layer
  smoke/      Minimal liveness
```

Run with `cd apps/api && python run_tests.py`, or `./scripts/plane test`
against the dev-site datastores when there is no local Python environment.

Two traps: pytest defaults to `--reuse-db`, so a schema change needs
`--create-db`; and `django_celery_beat` is excluded from `INSTALLED_APPS`
under the test settings, so anything touching `PeriodicTask` must degrade
gracefully.

Frontend: `pnpm check:types`, `pnpm check:lint`, `pnpm check:format`. Several
packages carry pre-existing failures — compare against a baseline rather than
expecting a clean tree.

---

## Local development

```
pnpm dev:local     # backend + Caddy in Docker, frontends via turbo
pnpm dev:clean     # stale ports
```

One origin at `http://localhost`: web at `/`, god-mode at `/god-mode/`, API at
`/api`. Running `pnpm dev` per-app twice cascades ports — a second web lands on
`:3001` and impersonates admin. Use `pnpm dev:local`.

The dev site is a separate full deployment from the same checkout (compose
project `planedev`, proxy on 8091). Drive it through `scripts/plane devsite`; a
bare `docker compose` in this directory targets **production**.
