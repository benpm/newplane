# `newplane`

> Open-source project management platform with all the features you need, forked from [makeplane/plane](https://github.com/makeplane/plane).

## New Features

See [CHANGELOG.md](./CHANGELOG.md) for a list of changes and new features. Notable additions include:

- Extensive synchronization with a git repo that can be associated with a specific project.
- Page relationships

## Quick Links

- **Documentation:** [docs/](./docs/)
  - [Project Overview & PDR](./docs/project-overview-pdr.md)
  - [Codebase Summary](./docs/codebase-summary.md)
  - [Code Standards](./docs/code-standards.md)
  - [System Architecture](./docs/system-architecture.md)
  - [Design Guidelines](./docs/design-guidelines.md)
  - [Deployment Guide](./docs/deployment-guide.md)
  - [Project Roadmap](./docs/project-roadmap.md)
  - [GitNexus Setup Guide](./docs/gitnexus-guide.md) — code intelligence for Claude Code
- **Repository:** https://github.com/benpm/newplane
- **Upstream:** [`makeplane/plane`](https://github.com/makeplane/plane)

## Features

### Core Capabilities

- **Issue Management:** Multiple layouts (List, Kanban, Gantt, Calendar, Spreadsheet)
- **Sprint Planning:** Cycles (sprints) with burndown tracking
- **Feature Planning:** Modules for organizing features/epics
- **Wiki Pages:** Markdown-based project documentation
- **Custom Workflows (CE):** Fork-specific workflow states and validation
- **Time Tracking (CE):** Estimate and log hours per issue
- **Organization Chart (CE):** Org hierarchy visualization
- **Real-Time Collaboration:** WebSocket-based live editing (Y.js CRDT)
- **Multi-Workspace:** User-level workspace management
- **RBAC:** Workspace/Project-level role-based access control

### Tech Stack

**Frontend:**

- React 18 + Router v7
- MobX (state management)
- Tailwind CSS v4 (semantic color tokens)
- Atlaskit Pragmatic DnD (drag-and-drop)
- Next.js (app router)

**Backend:**

- Django 4.2 + Django REST Framework
- PostgreSQL (primary database)
- Redis (caching, sessions)
- RabbitMQ + Celery (async task queue)
- Hocuspocus + Y.js (real-time collaboration)

**Infrastructure:**

- Docker + Docker Compose
- Caddy (reverse proxy)
- AWS S3 (file uploads)
- pnpm (monorepo)
- Turbo (build orchestration)

## Getting Started

### Prerequisites

- Node.js 22.18+
- Python 3.11+
- PostgreSQL 13+
- Redis 7+
- RabbitMQ 3.12+ (optional, for async tasks)
- Docker 24+ (recommended)

### Local Development (5 minutes)

**1. Clone & Install**

```bash
git clone https://github.com/benpm/newplane.git
cd newplane
pnpm install
```

**2. Create env files** (first time only)

```bash
cp apps/api/.env.example apps/api/.env
cp apps/web/.env.example apps/web/.env
cp apps/admin/.env.example apps/admin/.env
```

**3. Start the full stack — one command**

```bash
pnpm dev:local      # backend + Caddy proxy (Docker) + all frontends (turbo, hot reload)
# ports busy from an old run?  ->  pnpm dev:clean
```

`pnpm dev:local` brings up the backend (Django + Postgres + Redis + RabbitMQ + MinIO) and a Caddy reverse proxy in Docker, then runs the frontends on the host with hot reload. Everything is served through **one origin — http://localhost**:

| URL                          | App              | Host port     |
| ---------------------------- | ---------------- | ------------- |
| `http://localhost`           | Web app          | 3000          |
| `http://localhost/god-mode/` | Admin (god mode) | 3001          |
| `http://localhost/spaces/`   | Public spaces    | 3002          |
| `http://localhost/live/`     | Live server      | 3003          |
| `http://localhost/api/…`     | Backend API      | 8000 (Docker) |

> Reach **god-mode at `http://localhost/god-mode/`** through the proxy — not `localhost:3001` directly (the admin dev server has no `/api` proxy of its own).
> Backend is mounted live (Django autoreload); frontends hot-reload via Vite. Always start frontends with `pnpm dev:local`, never `cd apps/web && pnpm dev` repeatedly — duplicate dev servers cascade onto :3001 and shadow god-mode (you'd see the web app's "no workspace" at /god-mode/).

Open **http://localhost** and sign in. For instance admin (god-mode) first-time setup, open `http://localhost/god-mode/`.

**Full Guide:** [Deployment Guide → Local Development](./docs/deployment-guide.md#local-development-setup)

### Dev site — a second deployment beside production

For testing a branch as a real deployment rather than a hot-reload dev server:

```bash
./scripts/dev-site.sh build && ./scripts/dev-site.sh up -d   # start / rebuild
./scripts/dev-site-logs.sh                                   # live log feed
./scripts/dev-site.sh down                                   # stop (data kept)
```

It runs as the `planedev` compose project, which gives it its own images,
volumes, network, database, object store and crypto keys — nothing is shared
with a production stack in the same checkout. The proxy publishes **8091**
(production keeps 8090); environment files live outside the repo so no secrets
enter version control.

> Drive it through `scripts/dev-site.sh`, never a bare `docker compose`: an
> unqualified compose command in this directory resolves to the production
> stack. Note `docker-compose.dev.yml` is the separate local hot-reload overlay
> used by `pnpm dev:local`; the dev site uses `docker-compose.devsite.yml`.

**4. (Recommended) Setup Code Intelligence**

```bash
./scripts/gitnexus.sh pull       # pull pinned Docker image (~1.2GB)
./scripts/gitnexus.sh analyze    # index codebase (~2-3 min)
```

Enables Claude Code's GitNexus MCP tools (impact analysis, call graph, refactor safety). See [GitNexus Setup Guide](./docs/gitnexus-guide.md) for details.

## Project Structure

```
plane/
├── apps/
│   ├── web/              # React frontend (port 3000)
│   ├── api/              # Django backend (port 8000)
│   ├── admin/            # Admin panel (port 3001)
│   ├── space/            # Guest access (port 3002)
│   ├── live/             # WebSocket server (port 3003)
│   └── proxy/            # Caddy reverse proxy
├── packages/             # Shared libraries (18 total)
├── docs/                 # Project documentation
├── plans/                # Planning & task tracking
├── .claude/              # Claude AI context
└── README.md             # This file
```

**Detailed Structure:** [Codebase Summary](./docs/codebase-summary.md#directory-structure)

## Development Workflow

### Before Starting

1. Read [Code Standards](./docs/code-standards.md)
2. Understand [System Architecture](./docs/system-architecture.md)
3. Follow [Design Guidelines](./docs/design-guidelines.md)

### Development Steps

1. **Create Feature Branch**

   ```bash
   git checkout -b {user}/feat/{feature-name}
   ```

2. **Code & Test**

   ```bash
   # Frontend
   pnpm test
   pnpm check:lint
   pnpm check:format

   # Backend
   cd apps/api && python run_tests.py
   ```

3. **Commit with Conventional Format**

   ```bash
   git commit -m "feat(issue): add time tracking support"
   ```

4. **Create Pull Request**

   ```bash
   git push origin {user}/feat/{feature-name}
   # Then open PR on GitHub (develop branch)
   ```

5. **Code Review & Merge**
   - Requires 1 approval
   - CI/CD must pass (tests, linting, types)
   - Merge to `develop`, then PR to `preview`

**Detailed Workflow:** [Code Standards → Code Review Checklist](./docs/code-standards.md#code-review-checklist)

## Documentation Map

| Document                    | Purpose                                    | Audience            |
| --------------------------- | ------------------------------------------ | ------------------- |
| **project-overview-pdr.md** | Project goals, requirements, constraints   | PMs, Team Leads     |
| **codebase-summary.md**     | File structure, key modules, concepts      | All Developers      |
| **code-standards.md**       | Naming, patterns, testing, review criteria | Developers          |
| **system-architecture.md**  | System design, data flow, scaling          | Architects, DevOps  |
| **design-guidelines.md**    | UI/UX, components, Tailwind tokens         | Frontend Developers |
| **deployment-guide.md**     | Local setup, Docker, production deploy     | DevOps, Backend     |
| **project-roadmap.md**      | Phases, milestones, timelines, metrics     | All Stakeholders    |

## Key Architectural Decisions

### CE Pattern (Customization Extension)

All fork-specific features live in `apps/web/ce/` and `apps/api/` — **never modify `core/`**. This ensures upstream code stays clean and merges are manageable.

```
core/ (upstream) + ce/ (customizations) = RootStore (composition)
```

See [System Architecture → CE Pattern](./docs/system-architecture.md#ce-pattern-customization-extension)

### MobX State Management

Single source of truth per feature store. Async mutations use `flow` + `runInAction`.

```typescript
issueStore.fetchIssues(); // async, uses flow
issueStore.updateIssue(id, data); // sync, uses action.bound
```

See [Code Standards → MobX Conventions](./docs/code-standards.md#mobx-store-conventions)

### Multi-Layout Issue Views

All layouts (List, Kanban, Gantt, Calendar, Spreadsheet) read from the same MobX store. Switching views doesn't refetch data.

See [System Architecture → Issue Layouts](./docs/system-architecture.md#issue-layouts-multi-view-single-store)

### API Versioning

- **V0** (Session auth, internal) — Used by web UI
- **V1** (API key auth, external) — Used by external integrations

Never share serializers between versions.

See [System Architecture → API Versioning](./docs/system-architecture.md#api-versioning)

## API Documentation

### V0 API (Internal)

Used by web UI with session-based authentication.

```bash
# Example: Create an issue
curl -X POST http://localhost:8000/api/v0/issues/ \
  -H "Content-Type: application/json" \
  -d '{
    "title": "New issue",
    "description": "Issue description",
    "project_id": "project-id",
    "state_id": "state-id"
  }'
```

### V1 API (External)

Used by external integrations with API key authentication.

```bash
# Example: List issues
curl http://localhost:8000/api/v1/issues/ \
  -H "X-API-KEY: your-api-key"
```

**OpenAPI Docs:** http://localhost:8000/api/v1/docs/

## Environment Variables

### Frontend (apps/web/.env.local)

```env
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
NEXT_PUBLIC_ENABLE_WORKFLOWS=true
NEXT_PUBLIC_ENABLE_TIME_TRACKING=true
NEXT_PUBLIC_ENABLE_HO=true
```

### Backend (apps/api/.env)

```env
DATABASE_URL=postgresql://user:password@localhost:5432/plane
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=amqp://guest:guest@localhost:5672//
SECRET_KEY=your-secret-key-min-50-chars
DEBUG=True
```

**Full List:** [Deployment Guide → Environment Variables](./docs/deployment-guide.md#environment-variables-checklist)

## Testing

### Run All Tests

```bash
# Frontend
pnpm test

# Backend
cd apps/api && python run_tests.py

# Backend, against the dev-site datastores (no local Python env needed)
./scripts/dev-site-test.sh                 # everything
./scripts/dev-site-test.sh -m unit         # one marker
./scripts/dev-site-test.sh --cov=plane     # with coverage
```

`dev-site-test.sh` builds a test image once from `requirements/test.txt` on top
of the dev-site API image, because the runtime image ships no test dependencies.
It also installs `git`, which the wiki-sync tests need to seed a local bare repo
as a stand-in for a GitHub wiki — the task itself uses the GitHub API, so the
runtime image rightly omits it.

Current state: **1105 passing, 0 failed, 0 errors**; backend coverage ~52%.

### Coverage Requirements

- Minimum 80% for merging PRs
- Use `--cov` flag for coverage report
- Prefer covering paths the deployment actually exercises over the global
  percentage — see the prioritisation note in [TODO.md](./TODO.md)

### Guidelines

- One test per behavior (not per line of code)
- Test both success + error paths
- Mock external services (S3, email)
- No hardcoded test data (use factories)

**Details:** [Code Standards → Testing Standards](./docs/code-standards.md#testing-standards)

## Performance Targets

| Metric          | Target           | Current | Status        |
| --------------- | ---------------- | ------- | ------------- |
| API p95 latency | <200ms           | ~250ms  | ⚠️ Optimizing |
| Kanban render   | <1s (500 issues) | ~1.2s   | ⚠️ Optimizing |
| Frontend bundle | <250KB (gzip)    | ~280KB  | ⚠️ Optimizing |
| Page load       | <2s              | ~1.8s   | ✅ Good       |

See [Project Roadmap → Performance & Stability](./docs/project-roadmap.md#phase-5-performance--stability-45-complete)

## Troubleshooting

### Backend won't start

```bash
# Check if port 8000 is in use
lsof -i :8000

# Check database connection
python manage.py dbshell

# Clear Redis cache
redis-cli FLUSHDB
```

### Frontend won't start

```bash
# Clear Node cache
rm -rf node_modules/.pnpm-store
pnpm install

# Clear Vite cache, then restart cleanly
rm -rf apps/web/node_modules/.vite
pnpm dev:clean
```

### WebSocket connection issues

```bash
# Check if the live server port is open (live runs on the host via pnpm)
lsof -i :3003

# Restart all frontends cleanly
pnpm dev:clean
```

**More:** [Deployment Guide → Troubleshooting](./docs/deployment-guide.md) (coming soon)

## Contributing

1. **Read** [Code Standards](./docs/code-standards.md)
2. **Follow** [Development Workflow](./README.md#development-workflow)
3. **Create PR** against `develop` (not `preview`)
4. **Request review** from team lead
5. **Merge** after approval + CI passes

### Commit Message Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types:** `feat`, `fix`, `docs`, `refactor`, `test`, `chore`
**Example:** `feat(workflow): add transition validation`

See [Code Standards → Pre-commit/Push Rules](./docs/code-standards.md#pre-commitpush-rules)

## Deployment

### Local Docker (all-in-Docker, production-like)

```bash
docker compose up -d
# Services: web (3000), api (8000), admin (3001), space (3002), live (3003)
```

> For day-to-day development with hot reload use **`pnpm dev:local`** (see [Local Development](#local-development-5-minutes) — frontends run on the host). The command above builds every app into a Docker image, which is slower and production-like.

### Production Checklist

- [ ] All tests passing
- [ ] Linting/formatting passes
- [ ] Environment variables configured
- [ ] Database migrations ready
- [ ] Secrets not committed
- [ ] Images built and scanned
- [ ] Health checks passing

**Full Guide:** [Deployment Guide](./docs/deployment-guide.md)

## Support & Contact

- **Issues:** [GitHub Issues](https://github.com/benpm/newplane/issues)
- **Discussions:** [GitHub Discussions](https://github.com/benpm/newplane/discussions)
- **Team:** Internal Slack channel
- **Docs Lead:** @docs-manager

## License

Plane is forked from [makeplane/plane](https://github.com/makeplane/plane) under the AGPL-3.0 license. See [LICENSE](./LICENSE) for details.

## Related Projects

- **Upstream:** [makeplane/plane](https://github.com/makeplane/plane) — Original open-source project
- **Web:** [apps/web/](./apps/web/) — React frontend
- **API:** [apps/api/](./apps/api/) — Django backend
- **Components:** [packages/propel/](./packages/propel/) — UI component library

---

**Last Updated:** 2026-08-11 | **Version:** 1.2.0
