# The `plane` CLI

One entry point for every operational task in this repository:
**`scripts/plane`**.

It replaces the eighteen loose shell scripts that used to live in `scripts/`.
Each is now a subcommand, sharing one help system, one set of colours, one
error handler and one log format.

```bash
scripts/plane help              # every command
scripts/plane <group> help      # commands in a group
scripts/plane <command> --help  # usage for one command
```

---

## Global options

Accepted before or after the command.

| Option            | Effect                                                     |
| ----------------- | ---------------------------------------------------------- |
| `-v`, `--verbose` | Echo each command as it runs                               |
| `-q`, `--quiet`   | Suppress informational output; errors still print          |
| `--no-color`      | Plain output (also honours `NO_COLOR`)                     |
| `--log-file PATH` | Append a timestamped transcript, with colours stripped     |
| `--yes`           | Assume yes for confirmations (or set `PLANE_ASSUME_YES=1`) |
| `--version`       | Print the CLI version                                      |

Colour switches itself off when stdout is not a terminal, so piping to a file
or through `grep` gives clean text without a flag.

Every failure prints the same shape — `✗` in red, the message, and for
unexpected errors the line number and command that failed:

```
✗ failed at line 412: docker load < "$tar"
✗ exit code 1
```

---

## Development

### `plane dev [--clean]`

Starts the local stack. Backend and the Caddy proxy run in Docker; the
frontends run on the host through turbo with hot reload. Everything is reached
through one origin, **http://localhost**, so there are no ports to juggle.

`--clean` first kills any host dev server squatting on 3000-3003. That is worth
knowing about: a duplicate `pnpm dev` cascades onto `:3001` and impersonates the
admin app, which surfaces as a baffling "no workspace" error. Without `--clean`
the CLI warns when a port is already occupied rather than failing.

`plane dev stop` stops the backend containers.

Also available as `pnpm dev:local` and `pnpm dev:clean`.

### `plane test [pytest args...]`

Runs the backend suite against the dev-site datastores.

```bash
plane test                          # everything
plane test -m unit                  # one marker
plane test plane/tests/unit/views   # a subset
plane test --create-db              # rebuild the test database
plane test -m unit --cov=plane      # with coverage
```

`--create-db` matters more than it looks: pytest is configured with
`--reuse-db`, so after a schema change the suite runs against a stale database
and fails with confusing "column does not exist" errors.

The runtime API image ships no test dependencies and containers on this host
have no outbound network, so a test image is built once with `--network host`
from `requirements/test.txt` layered on `planedev-api`. The repo mounts at
`/repo` rather than `/code` because some tests locate the repo root by parent
depth from `apps/api`.

### `plane test drift`

Fails if a model has been edited without a matching migration.

```bash
plane test drift
```

Worth having as its own command because the suite structurally cannot catch
this: pytest runs with `--nomigrations`, so it builds its schema from the
models and never executes a migration file. Models and migrations can diverge
indefinitely with every test still passing — and the test database then stops
matching production, so a test can pass here and the same code fail there.

Needs Django and nothing else, not even a database, so it runs against
`planedev-api` rather than the test image and takes a couple of seconds.
`.husky/pre-push` runs it as step 5, skipping with a warning if the
`planedev-api` image has not been built. The same check also runs inside the
suite as `plane/tests/unit/db/test_migrations_in_sync.py`, which prints every
pending operation on failure.

### `plane gitnexus <command>`

Code-intelligence index, run through Docker so the version is pinned across
machines.

| Command          | Purpose                                             |
| ---------------- | --------------------------------------------------- |
| `analyze [args]` | Re-index synchronously (~2-3 min)                   |
| `mcp`            | Start the MCP server on stdio — used by `.mcp.json` |
| `status`         | Index status                                        |
| `list`           | Indexed repositories                                |
| `reindex-bg`     | Background re-index, throttled to once per 60s      |
| `pull`           | Pull or update the image                            |

`--skip-agents-md` is hard-wired with no opt-out: gitnexus rules live in
`.claude/rules/`, and letting it rewrite tracked `CLAUDE.md` / `AGENTS.md` on
every index would churn the repo differently for each developer.

`reindex-bg` is called from the `post-commit`, `post-checkout` and `post-merge`
git hooks; the throttle stops a run of rapid commits queueing an index each.

Override the image with `GITNEXUS_IMAGE`.

---

## Dev site

A full second deployment built from the working tree, sharing nothing with
production — separate images, volumes, network, database, object store and
crypto keys.

```
production  →  https://plane.mousetrip.online   (localhost:8090)
dev site    →  https://dev.mousetrip.online     (localhost:8091)
```

### `plane devsite <command>`

Anything not recognised is passed straight through to `docker compose`, with
the project name and env files already wired in.

```bash
plane devsite build            # rebuild images from the working tree
plane devsite up -d            # start or restart
plane devsite ps               # status
plane devsite down             # stop (volumes and data are kept)
plane devsite exec api sh      # shell into a container
```

> **Always go through this command.** A bare `docker compose` in this
> repository resolves to the **production** stack.

### `plane devsite logs [options] [service...]`

Prints a status header, then follows logs until interrupted.

| Option     | Effect                                    |
| ---------- | ----------------------------------------- |
| `--all`    | Include datastores (db, redis, mq, minio) |
| `--errors` | Only lines that look like problems        |
| `--tail N` | Scrollback lines (default 50)             |
| `--list`   | Show service names and exit               |

Datastores are excluded by default because their chatter drowns out app logs.

---

## Release

### `plane release build [--all]`

Builds `linux/amd64` images, exports them to `dist/` as `.tar.gz`, writes
`dist/.release-version`, verifies every tarball's architecture, and generates
`docker-compose.release.yml`.

By default it builds the three **dynamic** images — frontend, admin and backend
(shared by api, worker, beat-worker and migrator). Static services (space, live,
proxy, postgres, redis) are pre-loaded at provisioning and are not part of a
release. `--all` builds those too, for an initial provisioning run.

The version comes from `package.json`.

### `plane release verify [dir]`

Asserts every image tarball in `dir` (default `dist/`) is `linux/amd64`.
Called automatically by `release build`. On a machine without Docker — an
upload-only host, say — it skips rather than fails, since the images were
already verified at build time.

### `plane release package`

Assembles a self-contained `deploy/` folder: the compose override, the three
image tarballs, the version manifest, and a copy of this CLI so the target
server deploys with the same tool. Refuses to proceed if any tarball is missing
or suspiciously small (a common signature of a failed build).

### `plane release upload <tag>`

Reads `upload-release.env` (see `scripts/upload-release.env.example`), then
publishes. The tag must start with `dev/` or `prod/`:

```bash
plane release upload dev/v1.2.0-build.5
plane release upload prod/v1.2.0
```

### `plane release publish`

The low-level publish, expecting `GITLAB_URL`, `CI_PROJECT_ID`,
`GITLAB_PUBLISH_TOKEN`, `RELEASE_VERSION` and `RELEASE_TAG` in the environment.
`release upload` is the friendlier wrapper.

It zips the package, uploads it to the GitLab Generic Package Registry with a
`SHA256SUMS` file, creates the git tag, and creates or updates a GitLab Release
whose description embeds the SHA256. That checksum is the integrity anchor
`plane deploy from-gitlab` reads back — deliberately a _second, independent_
source from the package registry asset.

Uploads are idempotent: re-publishing the same version with a matching SHA256
is a no-op, and a mismatched SHA256 is a hard error rather than a silent
overwrite.

---

## Deploy

### `plane deploy release [options]`

Runs on the target server. Loads the images from `dist/`, stops any conflicting
Plane deployment from another compose project, runs migrations, then recreates
every service on the new images.

| Option           | Default               |
| ---------------- | --------------------- |
| `--dist DIR`     | `dist`                |
| `--env FILE`     | `plane.env`           |
| `--compose FILE` | `docker-compose.yaml` |

Migrations run first and **the deploy aborts if they fail** — finishing the
rollout on a half-migrated database is the one outcome worth failing loudly to
avoid.

### `plane deploy ci`

For the CI path, where the runner has already dropped images in
`/tmp/plane-deploy`. Requires `RELEASE_VERSION`; honours `PLANE_DIR`
(default `/opt/plane-deploy/plane-app`). Persists the images into the server's
`dist/` so a rollback or re-deploy does not need CI.

### `plane deploy from-gitlab`

Runs on the target server, driven entirely by GitLab CI variables. Downloads
the release package, verifies its SHA256 against the Releases API, extracts and
validates the manifest, loads every image, and only then deploys.

Two safeguards worth knowing:

- **Nothing is stopped until every image is loaded and verified present.** A
  corrupt or incomplete package fails with the running deployment untouched.
- The archive is extracted with Python rather than `unzip`, which normalises
  the backslash paths Windows zip tools embed.

Afterwards it archives the package (keeping the last `ARCHIVE_KEEP`, default 3)
and appends to `deploy-audit.log`.

---

## Operations

### `plane server setup [options]`

Prepares a fresh server: creates the deploy tree, the proxy config directory,
a Caddyfile, and installs this CLI into the server's `scripts/`.

| Option            | Effect                                               |
| ----------------- | ---------------------------------------------------- |
| `--domain DOMAIN` | Caddy domain (default `plane.example.com`)           |
| `--vps`           | HTTP-only Caddyfile for an external VPS, no TLS cert |
| `--dir PATH`      | Deploy directory                                     |

Without `--vps` it expects TLS certificates at `/opt/certs/{fullchain,privkey}.pem`
and reminds you to copy them.

### `plane images save|load`

Moves base images to an airgapped build host.

```bash
# On a machine with internet access (linux/amd64)
plane images save /media/usb

# On the airgapped host
plane images load /media/usb/base-images.tar.gz
```

`load` verifies every expected image is present afterwards and fails if any is
missing, rather than letting a build fail confusingly later.

### `plane token rotate [--no-restart]`

Replaces `GITHUB_PERSONAL_ACCESS_TOKEN` for the GitHub issue and wiki sync.

The token is read from a **hidden prompt** — never argv, so it stays out of
shell history and the process table — and validated _before_ anything is
written: the API must accept it, a classic token must carry the `repo` scope,
and push access is confirmed against every repo in `project_github_syncs`. Any
failure exits with no files touched.

On success it writes both `.env` and `apps/api/.env` (backing each up) and
recreates `api`, `worker` and `beat-worker`.

> **Use a classic token, not fine-grained.** Fine-grained PATs have no wiki
> permission at all, so issue sync would work while the wiki half kept failing
> with an auth error indistinguishable from a bad token.

The backups it leaves behind contain the old token _and every other secret in
`.env`_. Shred them once you are satisfied:

```bash
shred -u .env.bak-* apps/api/.env.bak-*
```

### `plane setup`

The upstream Plane self-hosted installer, passed through unmodified.

This one is deliberately **not** folded into the CLI. It is 800 lines of
third-party code, and rewriting it would turn every future upstream sync into a
manual merge. It stays at `scripts/setup.sh`, diffable against upstream.

---

## Where things went

| Was                                      | Now                                              |
| ---------------------------------------- | ------------------------------------------------ |
| `dev-local.sh`                           | `plane dev`                                      |
| `dev-site.sh`                            | `plane devsite`                                  |
| `dev-site-logs.sh`                       | `plane devsite logs`                             |
| `dev-site-test.sh`                       | `plane test`                                     |
| `gitnexus.sh`                            | `plane gitnexus`                                 |
| `rotate-github-token.sh`                 | `plane token rotate`                             |
| `build-release-images.sh`                | `plane release build`                            |
| `build-release-images-opt.sh`            | `plane release build --all`                      |
| `verify-release-package-architecture.sh` | `plane release verify`                           |
| `prepare-deploy-package.sh`              | `plane release package`                          |
| `upload-release.sh`                      | `plane release upload`                           |
| `publish-gitlab-release-package.sh`      | `plane release publish`                          |
| `deploy-release.sh`                      | `plane deploy release`                           |
| `ci-deploy.sh`                           | `plane deploy ci`                                |
| `deploy-from-internal-gitlab-release.sh` | `plane deploy from-gitlab`                       |
| `setup-server.sh`                        | `plane server setup`                             |
| `seed-base-images-save.sh`               | `plane images save`                              |
| `seed-base-images-load.sh`               | `plane images load`                              |
| `setup.sh`                               | `plane setup` (still a separate file — upstream) |

Callers updated with the move: `package.json` (`dev:local`, `dev:clean`),
`.mcp.json`, the three husky git hooks, and `.gitlab-ci.yml`.

The old scripts are in git history if you need to compare behaviour:

```bash
git show HEAD~1:scripts/deploy-release.sh
```

---

## Extending it

Add a subcommand by writing a `cmd_<name>` function and adding a `case` arm in
`main`. Use the shared helpers rather than rolling your own:

| Helper                                     | Purpose                            |
| ------------------------------------------ | ---------------------------------- |
| `log_info` `log_ok` `log_warn` `log_error` | Coloured, log-file-aware output    |
| `log_step N TOTAL "text"`                  | `[2/5] text` progress              |
| `log_header "text"`                        | Section banner                     |
| `die "message"`                            | Error and exit 1                   |
| `require_cmd` `require_file` `require_dir` | Preconditions with clear messages  |
| `require_docker`                           | Docker plus compose v2             |
| `run cmd...`                               | Execute, echoing under `--verbose` |
| `confirm "question"`                       | Prompt, honouring `--yes`          |

Two conventions worth keeping:

- Every command supports `--help`, and every group has a `help` arm.
- Preconditions are checked before anything is written or started, so a command
  either does its whole job or changes nothing.

---

## Related

- [README](../README.md) — repository overview
- [Deployment](./deployment/index.md) — CI/CD and runner setup
- [Instance Dashboard](./instance-dashboard.md) — the `/dashboard` operations view
