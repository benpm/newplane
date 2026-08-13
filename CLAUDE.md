# CLAUDE.md

## Architecture

- React 18 + Router v7 + MobX + Tailwind v4 | Django 4.2 + DRF + Postgres + Celery
- CE pattern: new features in `ce/`, never modify `core/`
- UI: prefer `@plane/propel/*` over `@plane/ui`
- **Web vs Admin**: `apps/web/` uses i18n (`t()`); `apps/admin/` is **English-only, NO i18n**, uses Propel Dialog (`onOpenChange`)

## Rules

Engineering conventions live in `.claude/rules/` and load by file path — backend
architecture, models, views, serializers, testing; frontend design system, colour
tokens, component libraries, forms, routing, i18n.

## Git Safety

- Origin: `github.com/benpm/newplane.git` | Default: `main`
- Branch from `main`, PR back into it
- ❌ NEVER pull/merge/rebase from upstream (`makeplane/plane`)
- ❌ NEVER force push to `main`

## Build

- PM: pnpm | Lint: `pnpm check:lint` | Format: `pnpm check:format`
- Backend tests: `cd apps/api && python run_tests.py`, or `./scripts/plane test`
  to run against the dev-site datastores without a local Python env

## Local Dev

- **Start everything: `pnpm dev:local`** (backend + Caddy proxy in Docker, frontends via turbo, hot reload). Stale ports? `pnpm dev:clean`. Script: `scripts/plane dev`.
- **One origin: http://localhost** → web · **http://localhost/god-mode/** → admin · `/api` → backend. Caddy (:80) routes by path.
- Ports: web 3000 · admin 3001 · space 3002 · live 3003 · api 8000 · db 5434 · MinIO 9000/9090.
- **Pitfall:** running `pnpm dev` per-app twice cascades ports — a 2nd web lands on :3001 and impersonates admin (→ "no workspace"). Run `pnpm dev:local`.

## Dev site

A second, fully isolated deployment from the same checkout (compose project
`planedev`, proxy on 8091). See README. Drive it through `scripts/plane devsite` —
a bare `docker compose` here targets production.

## File Standards

- kebab-case, <200 lines code, <150 lines components
- YAGNI / KISS / DRY
