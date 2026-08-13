# GitNexus — Developer Guide for Plane

> Graph-based (call graph) code intelligence for a 500k LOC codebase. This document is for new developers onboarding.

---

## TL;DR

```bash
# One-time setup (Docker must already be running)
./scripts/plane gitnexus pull              # pull the image (~1.2GB)
./scripts/plane gitnexus analyze           # first index (~2-3 minutes)
./scripts/plane gitnexus status            # verify "up-to-date"

# After that: automatic re-index on commit / pull / branch switch
```

The MCP server (`./scripts/plane gitnexus mcp`) is already wired into Claude Code via `.mcp.json` — no manual config needed.

---

## 1. What is GitNexus, and why use it?

GitNexus is a **knowledge graph** of the whole codebase: it reads the code → extracts symbols (function/class/method), call relationships, and execution flows → stores them in a local DB → and lets you query them semantically.

### Why does Plane need it?

| Problem at 500k LOC            | Old way                            | GitNexus way                           |
| ------------------------------ | ---------------------------------- | -------------------------------------- |
| Find the callers of a function | `grep -r` → noise + misses dynamic | `gitnexus_impact`, precisely           |
| Understand an execution flow   | Read 10+ files                     | `gitnexus_query` → ranked flows        |
| Refactor safely                | Find/replace → breaks at runtime   | `gitnexus_rename`, call-graph aware    |
| Verify scope before committing | Plain `git diff`                   | `gitnexus_detect_changes` maps symbols |

Project rules (see `.claude/rules/gitnexus-mcp-usage.md`):

- **MUST** run `gitnexus_impact` before modifying a function/class.
- **MUST** run `gitnexus_detect_changes` before committing, to verify the blast radius.

---

## 2. Requirements

| Tool               | Version     | Notes                                                  |
| ------------------ | ----------- | ------------------------------------------------------ |
| Docker Desktop     | ≥ 24        | The daemon must be running before any GitNexus command |
| Disk space         | ~1.4 GB     | Image ~1.2GB + index ~150MB                            |
| RAM while indexing | ~2 GB peak  | Idle ≈ 200MB                                           |
| Architecture       | amd64/arm64 | Multi-arch image (native on Apple Silicon)             |

**Why Docker rather than `npx gitnexus`?**

- The project pins version `1.6.4-rc.63`, while `npm latest = 1.6.3` → a different build from the one the team standardised on.
- Docker avoids cross-platform native build issues (tree-sitter, onnxruntime-node, ladybugdb).
- Docker avoids the SSH-fetch dependency failure (`tree-sitter-dart` over `git+ssh://`).
- A pinned image tag means the index schema matches across the team's machines.

---

## 3. First-time setup

### Step 1 — Make sure Docker is running

```bash
docker info > /dev/null && echo "Docker OK" || echo "Start Docker Desktop first"
```

### Step 2 — Pull the image

```bash
./scripts/plane gitnexus pull
```

Default: `akonlabs/gitnexus:1.6.4-rc.63` (~1.2GB). Override with the env var `GITNEXUS_IMAGE=...`.

> ⚠️ **Pre-release notice:** the team pins a **Release Candidate** (`rc.63`), not a stable build. Reason: stable `1.6.3` cannot index Django migrations and lacks capability detection (FTS, vectorSearch). Migrate when `1.6.4` goes stable. Track it at https://hub.docker.com/r/akonlabs/gitnexus/tags.

### Step 3 — First index

```bash
./scripts/plane gitnexus analyze
```

Takes ~2-3 minutes on the Plane codebase (~5500 files). It creates:

- `.gitnexus/lbug` — graph DB (~150MB, gitignored)
- `.gitnexus/meta.json` — metadata (commit SHA, stats)

> The wrapper script always passes `--skip-agents-md`, so it never writes to `CLAUDE.md` or `AGENTS.md`. The rules for Claude live separately in `.claude/rules/gitnexus-mcp-usage.md` (static, doesn't churn with stats).

### Step 4 — Verify

```bash
./scripts/plane gitnexus status
# Expected: "Status: ✅ up-to-date"

./scripts/plane gitnexus list
# Expected: "plane" appears in the list

# Sanity check: the right version is running
docker images akonlabs/gitnexus
# Expected: TAG column = 1.6.4-rc.63 (or whatever tag the team currently pins)
```

### Step 5 — Restart the Claude Code session

The MCP server reads the index at startup. Restart so Claude sees the graph:

- VS Code: reload window
- Terminal: quit and reopen the CLI

Test: ask Claude `"What does the issue_serializer function do?"` — if Claude uses the `gitnexus_context` tool, you're good.

Or verify from the shell:

```bash
claude mcp list
# Expected: "gitnexus: ./scripts/plane gitnexus mcp - ✓ Connected"
```

---

## 4. How it works

### 4.1 The big picture

```
┌─────────────────────────────────────────────────────────────┐
│  Developer working tree (.ts/.tsx/.py/.js)                  │
└────────────────────────┬────────────────────────────────────┘
                         │ git commit / pull / checkout
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  Husky hooks:                                               │
│    .husky/post-commit    → reindex-bg (after commit)        │
│    .husky/post-merge     → reindex-bg (after pull)          │
│    .husky/post-checkout  → reindex-bg (after branch switch) │
└────────────────────────┬────────────────────────────────────┘
                         │ background, non-blocking
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  scripts/plane gitnexus reindex-bg                             │
│    docker run akonlabs/gitnexus:1.6.4-rc.63 analyze         │
│      → updates .gitnexus/lbug + meta.json                   │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  .mcp.json → ./scripts/plane gitnexus mcp                      │
│    Claude Code spawns container, talks via stdio MCP        │
│    Tools: impact, context, query, detect_changes, rename... │
└─────────────────────────────────────────────────────────────┘
```

### 4.2 When does it re-index automatically?

| Event                    | Hook                   | Skip condition                                          |
| ------------------------ | ---------------------- | ------------------------------------------------------- |
| `git commit` (success)   | `.husky/post-commit`   | Throttled: skipped if it re-indexed < 60s ago           |
| `git pull` / `git merge` | `.husky/post-merge`    | Skipped if no `.ts/.tsx/.py/.go/.rs/...` files changed  |
| `git checkout <branch>`  | `.husky/post-checkout` | Skipped for file checkouts (only branch switches count) |

Why **post-commit** rather than pre-commit: pre-commit is slow and would block the developer. Post-commit runs after the commit succeeds, detached in the background, so it never gets in the way.

Why there is **no** `pre-push` re-index: pushing doesn't change local code, so the graph is already built from the commit. Re-indexing before a push is redundant.

### 4.3 Where is the index stored?

```
plane.so/
├── .gitnexus/                  ← gitignored, local-only
│   ├── lbug                    ← LadybugDB (call graph)
│   ├── meta.json               ← stats, last commit, capabilities
│   └── .gitignore              ← contains "*" → the whole folder is ignored
└── ~/.gitnexus/registry.json   ← list of repos indexed on your machine
```

**Important:**

- The index is never committed to git.
- Every developer has their own index (built from their local source).
- The Docker image mounts the `gitnexus-data` volume for shared cache (LadybugDB engine).

### 4.4 MCP integration

`.mcp.json` at the project root:

```json
{
  "mcpServers": {
    "gitnexus": {
      "command": "./scripts/plane gitnexus",
      "args": ["mcp"]
    }
  }
}
```

When Claude Code starts, it:

1. Reads `.mcp.json`
2. Spawns `./scripts/plane gitnexus mcp` → starts a Docker container running the MCP server over stdio
3. The container reads `.gitnexus/lbug` from the host volume
4. Exposes the tools: `impact`, `context`, `query`, `cypher`, `detect_changes`, `rename`...

The container lives for the duration of the Claude session. Close Claude and the container exits.

---

## 5. Daily workflow

### Before modifying a function/class

```
Ask Claude: "What's the impact of changing X?"
→ Claude calls gitnexus_impact → returns callers, processes, risk level
→ You review that first, then make the change
```

### Before committing

```bash
# Verify the scope of the change
# (Claude can call gitnexus_detect_changes itself when reviewing the diff)
git add ...
git commit -m "feat(...): ..."
# post-commit hook → re-indexes automatically in the background
```

### When the index reports stale

```bash
./scripts/plane gitnexus analyze    # synchronous rebuild (blocks ~3 minutes)
# Or just wait for the next commit/pull to auto re-index
```

### When pulling new code from the team

```bash
git pull
# the post-merge hook re-indexes if code changed → nothing to do
```

### When the team bumps the GitNexus version (e.g. rc.63 → rc.70)

Trigger: `scripts/plane gitnexus` changes the image tag in a newly merged PR.

```bash
git pull                              # pick up the new tag in scripts/plane gitnexus
./scripts/plane gitnexus pull            # pull the new image
./scripts/plane gitnexus analyze         # rebuild the index (the schema can change between RCs)
# Restart the Claude Code session so the MCP container uses the new image
```

> Why re-analyze? A new RC can change the DB schema (LadybugDB) or the capability flags, so an old graph may be incompatible. Rebuilding keeps them in sync.

---

## 6. Command cheat sheet

| Purpose                            | Command                                                               |
| ---------------------------------- | --------------------------------------------------------------------- |
| Pull/update the Docker image       | `./scripts/plane gitnexus pull`                                       |
| Index synchronously (blocking)     | `./scripts/plane gitnexus analyze`                                    |
| Index in the background            | `./scripts/plane gitnexus reindex-bg`                                 |
| Current status                     | `./scripts/plane gitnexus status`                                     |
| List all indexed repos             | `./scripts/plane gitnexus list`                                       |
| Start the MCP server               | `./scripts/plane gitnexus mcp` (Claude calls this itself)             |
| Tail the background index log      | `tail -f /tmp/gitnexus-reindex-plane.so.log`                          |
| Wipe the index for a clean rebuild | `rm -rf .gitnexus/ && ./scripts/plane gitnexus analyze`               |
| Override the image tag             | `GITNEXUS_IMAGE=akonlabs/gitnexus:X.Y.Z ./scripts/plane gitnexus ...` |

### Commands Claude uses (via MCP — you don't type these)

| MCP tool                  | Use case                               |
| ------------------------- | -------------------------------------- |
| `gitnexus_impact`         | "What breaks if I change X?"           |
| `gitnexus_context`        | "Show callers/callees of X"            |
| `gitnexus_query`          | "Find execution flows for concept Y"   |
| `gitnexus_detect_changes` | "Map my git diff to affected symbols"  |
| `gitnexus_rename`         | "Rename X across call graph"           |
| `gitnexus_cypher`         | Query the graph with Cypher (advanced) |

---

## 7. Troubleshooting

### `Cannot connect to the Docker daemon`

→ Docker Desktop isn't running. Open it, wait for the icon to go green, retry.

### `Status: ⚠️ stale`

→ Code changed since the last index. Run `./scripts/plane gitnexus analyze`, or trigger a commit/pull so the hook runs.

### Background re-index locks the `lbug` file

```
Error: database is locked
```

→ Another re-index process is running. Check:

```bash
ps aux | grep gitnexus | grep -v grep
```

Wait for it to finish or kill the stale process, then retry.

### Claude doesn't see the GitNexus tools

1. Verify `.mcp.json` exists at the project root.
2. Restart the Claude Code session.
3. Run `/mcp` in Claude → check the `gitnexus` server status.
4. Still broken: run `./scripts/plane gitnexus mcp` by hand and look for stdio errors.

### The image pulls too slowly

```bash
# Set a Docker registry mirror:
# Docker Desktop → Settings → Docker Engine → add "registry-mirrors"
```

### Docker Hub rate limit (`toomanyrequests`)

```
Error response from daemon: toomanyrequests: You have reached your pull rate limit
```

→ Anonymous Docker Hub pulls are capped at 100/6h per IP. Log in to raise it to 200/6h:

```bash
docker login
# Then retry: ./scripts/plane gitnexus pull
```

### The index is too large (>500MB)

```bash
./scripts/plane gitnexus analyze --max-file-size 256   # skip files >256KB
# Or add entries to .gitnexusignore:
echo "apps/space/dist/" >> .gitnexusignore
echo "*.min.js" >> .gitnexusignore
```

### The hooks don't run

```bash
# Verify husky is installed
ls -la .husky/_/
# Re-init if missing:
pnpm prepare
```

---

## 8. FAQ

### Do I need to re-index when I only changed CSS/Markdown?

No. The `post-merge` hook only triggers when `.ts/.tsx/.js/.jsx/.mjs/.cjs/.py/.go/.rs/.java/.kt/.swift` files change. CSS/MD/config are skipped.

### Is re-indexing on every commit slow?

It doesn't block. The hook runs `reindex-bg` detached in the background, and a 60s throttle prevents spam during rapid successive commits.

### Does the index include sensitive code?

It can — the full source is parsed. **Never commit `.gitnexus/` to git**; `.gitnexus/.gitignore` already contains `*`. To exclude specific paths, use `.gitnexusignore`.

### Do I need to index on CI?

No. CI doesn't use MCP. Only local development needs GitNexus for Claude to help.

### When can the graph MISS a relationship?

- Django signals, Celery tasks → async edges usually aren't captured.
- Deeply nested React HOCs, MobX reactions, dynamic imports → indirect deps are missed.
- String-based lookups (registry pattern) → invisible to the graph.
  → Rule: on critical paths (auth, billing, permissions), **always cross-check** with `Read` + `grep`.

### Can I disable GitNexus temporarily?

```bash
# Skip the hooks once:
git commit --no-verify

# Disable entirely: delete or rename .mcp.json
# Or: rm -rf .gitnexus/ → the tools will report "no index"
```

### Does it affect me if a colleague hasn't installed GitNexus?

No. The index is local-only and per-machine. The hooks skip themselves if `.gitnexus/` doesn't exist.

---

## 9. Performance & tuning

### Re-index throttle

`scripts/plane gitnexus reindex-bg` skips itself if `.gitnexus/meta.json` was modified < 60s ago. This prevents overlapping runs during successive commits/checkouts.

### Excluding more paths

Create a `.gitnexusignore` file at the root (optional; not shipped in the repo). Same syntax as `.gitignore`:

```
apps/space/out/
apps/web/.next/
**/__pycache__/
*.bundle.js
```

Then run `./scripts/plane gitnexus analyze` to rebuild with the new exclusions.

### Speeding up analyze on a slower machine

```bash
./scripts/plane gitnexus analyze --max-file-size 256
GITNEXUS_NO_GITIGNORE=1 ./scripts/plane gitnexus analyze   # skip .gitignore parsing
```

---

## 10. Appendix: related files

| File                                  | Role                                      |
| ------------------------------------- | ----------------------------------------- |
| `scripts/plane gitnexus`              | Docker wrapper and its subcommands        |
| `.husky/post-commit`                  | Auto re-index after commit                |
| `.husky/post-merge`                   | Auto re-index after pull                  |
| `.husky/post-checkout`                | Auto re-index after branch switch         |
| `.mcp.json`                           | Registers the MCP server with Claude Code |
| `.gitnexus/`                          | Local index (gitignored)                  |
| `.gitnexusignore`                     | Excludes paths from the index             |
| `.claude/rules/gitnexus-mcp-usage.md` | MCP usage rules for Claude (auto-loaded)  |

---

## 11. Contact & documentation

- Skill files: `.claude/skills/gitnexus/*/SKILL.md`
- Upstream: https://github.com/abhigyanpatwari/GitNexus
- Reporting bugs: ping the Lead in a PR comment

> **Golden rule:** before modifying a large function/class → ask Claude `"impact of X"` → read the result → then change it. Don't skip this, especially for code touching `core/` or `apps/api/plane/db/`.
