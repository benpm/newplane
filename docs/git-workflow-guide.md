# Git Workflow Guide — newplane

> Git workflow guidelines for developers and operators.

---

## Branch Strategy

This fork is **single-trunk**: `main` is the only long-lived branch. Work
happens on short-lived branches taken from `main` and merged back into it.

```
┌─────────────────────────────────────────────────────────┐
│                    BRANCH STRUCTURE                      │
├─────────────────────────────────────────────────────────┤
│                                                         │
│   main (deployed)                                       │
│   ═══════════════                                       │
│     ▲         ▲         ▲                               │
│     │         │         │  Pull Request                 │
│   feat/     fix/      chore/                            │
│   xxx       xxx       xxx                               │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

| Branch    | Purpose                                 | Notes                            |
| --------- | --------------------------------------- | -------------------------------- |
| `main`    | The trunk; what production deploys from | Never force-push                 |
| `feat/*`  | New feature                             | Branch from `main`, PR to `main` |
| `fix/*`   | Bug fix                                 | Same                             |
| `chore/*` | Config, docs, refactor                  | Same                             |

> **Never pull, merge or rebase from upstream (`makeplane/plane`).** This fork
> has diverged deliberately; upstream history is not a valid base.
>
> **Never force-push to `main`.**

---

## Daily workflow (Developer)

### Step 1 — Start a new task

```bash
# 1. Get the latest main
git checkout main
git pull origin main

# 2. Branch off main
git checkout -b feat/feature-name
```

> **Branch naming rules:**
>
> - `feat/login-page` — new feature
> - `fix/broken-sidebar` — bug fix
> - `chore/update-deps` — technical/housekeeping work

### Step 2 — Code & commit

```bash
# Review your changes
git status
git diff

# Stage & commit
git add file1.ts file2.ts
git commit -m "feat(auth): implement login form validation"
```

> **Commit message rules:**
>
> ```
> type(scope): short description
> ```
>
> | Type       | When to use      | Example                                 |
> | ---------- | ---------------- | --------------------------------------- |
> | `feat`     | New feature      | `feat(auth): add OAuth login`           |
> | `fix`      | Bug fix          | `fix(sidebar): resolve scroll issue`    |
> | `perf`     | Performance work | `perf(api): optimize query N+1`         |
> | `refactor` | Restructuring    | `refactor(store): simplify state logic` |
> | `chore`    | Config, deps     | `chore(deps): upgrade react to v18.3`   |
> | `docs`     | Documentation    | `docs: update API reference`            |
>
> See `code-standards.md` for detailed commit message guidelines.
>
> **Pre-push checks (automated):**
>
> ```bash
> # Linting (frontend)
> pnpm check:lint
>
> # Type checking (TypeScript)
> # Runs automatically if configured
>
> # Backend linting (Python)
> cd apps/api && ruff check .
>
> # Backend type checking (Python)
> cd apps/api && mypy .
> ```

### Step 3 — Push & open a Pull Request

```bash
# Push the branch to the remote
git push -u origin feat/feature-name
```

Then open a PR on GitHub, or use the CLI:

```bash
gh pr create --base main --title "feat(auth): implement login form"
```

### Step 4 — Review & merge into main

```
┌──────────┐     PR      ┌──────────┐    Review    ┌──────────┐
│  Push    │ ──────────▶ │  GitHub  │ ──────────▶  │  Merge   │
│  branch  │             │  PR page │    ✅ OK      │   into   │
│          │             │          │              │   main   │
└──────────┘             └──────────┘              └──────────┘
```

- At least **1 reviewer** approval
- CI/CD checks must pass
- No conflicts

### Step 5 — Clean up after the merge

```bash
# Back to main and update
git checkout main
git pull origin main

# Delete the merged branch
git branch -d feat/feature-name
```

---

## Release workflow

There is no promotion step — merging into `main` _is_ the release. What
follows a merge is a deploy, not another merge.

```bash
# 1. Verify on the dev site first (a full second deployment from this checkout)
./scripts/dev-site.sh build && ./scripts/dev-site.sh up -d
#    → https://dev.mousetrip.online

# 2. Once reviewed, deploy production
docker compose build && docker compose up -d
#    → https://plane.mousetrip.online
```

**Pre-deploy checklist:**

- [ ] Backend tests pass (`cd apps/api && python run_tests.py`)
- [ ] `pnpm check:types` / `check:lint` / `check:format` no worse than baseline
- [ ] Verified on the dev site
- [ ] Database backed up if the change includes migrations

> A bare `docker compose` in this repository targets **production**. The dev
> site must be driven through `scripts/dev-site.sh`.

---

## Common situations

### 1. Conflicts when merging a PR

```bash
# Pull main into your branch
git checkout feat/feature-name
git merge main

# Resolve the conflicts in your editor, then:
git add .
git commit -m "merge: resolve conflicts with main"
git push
```

### 2. Pulling the latest main into your working branch

```bash
git checkout feat/feature-name
git merge main
# or
git rebase main  # (only if not yet pushed)
```

### 3. Committed to the wrong branch

```bash
# Undo the last commit, keeping the changes
git reset --soft HEAD~1

# Switch to the right branch
git checkout -b feat/correct-branch
git commit -m "feat: message"
```

### 4. Emergency production hotfix

```bash
# Branch the hotfix off main
git checkout main
git pull origin main
git checkout -b fix/critical-bug

# Fix → commit → push
git push -u origin fix/critical-bug

# Open the PR into main
gh pr create --base main --title "fix: critical bug in production"

```

With a single trunk there is nothing to sync back — the fix is on `main` the
moment the PR merges. Deploy it as above.

---

## Frequently used Git commands

| Situation                | Command                 |
| ------------------------ | ----------------------- |
| Show the current branch  | `git branch`            |
| Show all branches        | `git branch -a`         |
| Show commit history      | `git log --oneline -10` |
| Show uncommitted changes | `git diff`              |
| Shelve changes           | `git stash`             |
| Restore shelved changes  | `git stash pop`         |
| List open PRs            | `gh pr list`            |
| Show PR status           | `gh pr status`          |

---

## Mandatory rules

| #   | Rule                                                          | Why                                 |
| --- | ------------------------------------------------------------- | ----------------------------------- |
| 1   | **NEVER pull/merge/rebase from upstream (`makeplane/plane`)** | This fork has diverged deliberately |
| 2   | **NEVER force-push to `main`**                                | Destroys history others have pulled |
| 3   | **NEVER commit `.env` files, API keys, or credentials**       | Security                            |
| 4   | **Branch from `main`, PR back into `main`**                   | Single trunk; no promotion step     |
| 5   | **ALWAYS pull before starting work**                          | Avoid conflicts                     |
| 6   | **Commit messages must follow the format**                    | Keeps history readable              |
| 7   | **1 PR = 1 feature/fix**                                      | Easy to review, easy to revert      |

---

## End-to-end flow

```
    feat/login ──┐
                 ├──▶ PR ──▶ review ──▶ main ──▶ dev site ──▶ production
    fix/sidebar ─┘
```

Each branch is reviewed and merged into `main` independently. `main` is
deployed to the dev site for verification, then to production.

---

_Repo: github.com/benpm/newplane · default branch `main`_
