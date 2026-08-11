# Git Workflow Guide — newplane

> Git workflow guidelines for developers and operators.

---

## Branch Strategy

```
┌─────────────────────────────────────────────────────────┐
│                    BRANCH STRUCTURE                      │
├─────────────────────────────────────────────────────────┤
│                                                         │
│   preview (Production)                                  │
│   ════════════════════                                  │
│     ▲                                                   │
│     │  Pull Request (merged at release time)            │
│     │                                                   │
│   develop (Development)                                 │
│   ═════════════════════                                 │
│     ▲         ▲         ▲                               │
│     │         │         │                               │
│   feat/     fix/      chore/                            │
│   xxx       xxx       xxx                               │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

| Branch    | Purpose                              | Who merges?                           |
| --------- | ------------------------------------ | ------------------------------------- |
| `preview` | Production — stable, tested          | Lead / Manager                        |
| `develop` | Development — integrate new features | Developer                             |
| `feat/*`  | New feature                          | Developer (create & merge to develop) |
| `fix/*`   | Bug fix                              | Developer                             |
| `chore/*` | Config, docs, refactor               | Developer                             |

---

## Daily workflow (Developer)

### Step 1 — Start a new task

```bash
# 1. Get the latest develop
git checkout develop
git pull origin develop

# 2. Branch off develop
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
> | Type       | When to use          | Example                                 |
> | ---------- | -------------------- | --------------------------------------- |
> | `feat`     | New feature          | `feat(auth): add OAuth login`           |
> | `fix`      | Bug fix              | `fix(sidebar): resolve scroll issue`    |
> | `perf`     | Performance work     | `perf(api): optimize query N+1`         |
> | `refactor` | Restructuring        | `refactor(store): simplify state logic` |
> | `chore`    | Config, deps         | `chore(deps): upgrade react to v18.3`   |
> | `docs`     | Documentation        | `docs: update API reference`            |
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
gh pr create --base develop --title "feat(auth): implement login form"
```

### Step 4 — Review & merge into develop

```
┌──────────┐     PR      ┌──────────┐    Review    ┌──────────┐
│  Push    │ ──────────▶ │  GitHub  │ ──────────▶  │  Merge   │
│  branch  │             │  PR page │    ✅ OK      │   into   │
│          │             │          │              │  develop │
└──────────┘             └──────────┘              └──────────┘
```

- At least **1 reviewer** approval
- CI/CD checks must pass
- No conflicts

### Step 5 — Clean up after the merge

```bash
# Back to develop and update
git checkout develop
git pull origin develop

# Delete the merged branch
git branch -d feat/feature-name
```

---

## Release workflow (Lead / Manager)

### Merge develop → preview (Production)

```
  develop                          preview
  ═══════                          ═══════
     │                                │
     │  ① Open PR                     │
     │──────────────────────────────▶ │
     │                                │
     │  ② Review + Approve            │
     │                                │
     │  ③ Merge PR                    │
     │──────────────────────────────▶ │ ← Production updated
     │                                │
```

```bash
# Open the release PR: develop → preview
gh pr create --base preview --head develop \
  --title "release: merge develop into preview" \
  --body "## Changes
- Feature A
- Fix B
- Improvement C"
```

**Pre-merge checklist:**

- [ ] All tests pass on develop
- [ ] Code review complete
- [ ] No conflicts with preview
- [ ] Tested on the staging/dev environment

---

## Common situations

### 1. Conflicts when merging a PR

```bash
# Pull develop into your branch
git checkout feat/feature-name
git merge develop

# Resolve the conflicts in your editor, then:
git add .
git commit -m "merge: resolve conflicts with develop"
git push
```

### 2. Pulling the latest develop into your working branch

```bash
git checkout feat/feature-name
git merge develop
# or
git rebase develop  # (only if not yet pushed)
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
# Branch the hotfix off preview
git checkout preview
git pull origin preview
git checkout -b fix/critical-bug

# Fix → commit → push
git push -u origin fix/critical-bug

# Open the PR straight into preview
gh pr create --base preview --title "fix: critical bug in production"

# AFTER merging: sync back into develop
git checkout develop
git merge preview
git push origin develop
```

```
  preview ◀── fix/critical-bug (direct PR)
     │
     ▼
  develop ◀── merge preview (sync back)
```

---

## Frequently used Git commands

| Situation                 | Command                 |
| ------------------------- | ----------------------- |
| Show the current branch   | `git branch`            |
| Show all branches         | `git branch -a`         |
| Show commit history       | `git log --oneline -10` |
| Show uncommitted changes  | `git diff`              |
| Shelve changes            | `git stash`             |
| Restore shelved changes   | `git stash pop`         |
| List open PRs             | `gh pr list`            |
| Show PR status            | `gh pr status`          |

---

## Mandatory rules

| #   | Rule                                                      | Why                                    |
| --- | --------------------------------------------------------- | -------------------------------------- |
| 1   | **NEVER push directly to `preview`**                      | Production branch — merge via PR only  |
| 2   | **NEVER push directly to `develop`**                      | Must go through PR so it gets reviewed |
| 3   | **NEVER commit `.env` files, API keys, or credentials**   | Security                               |
| 4   | **NEVER `--force` push** (unless the Lead approves it)    | Avoid destroying other people's work   |
| 5   | **ALWAYS pull before starting work**                      | Avoid conflicts                        |
| 6   | **Commit messages must follow the format**                | Keeps history readable                 |
| 7   | **1 PR = 1 feature/fix**                                  | Easy to review, easy to revert         |

---

## End-to-end flow

```
Developer A          Developer B          Lead/Manager
    │                    │                     │
    ├─ feat/login        ├─ fix/sidebar        │
    │                    │                     │
    ├─ PR → develop ───▶ │                     │
    │                    ├─ PR → develop ─────▶│
    │                    │                     │
    │                    │              Review & Approve
    │                    │                     │
    │                    │       develop ◀──── Merged
    │                    │                     │
    │                    │              ┌──────┴──────┐
    │                    │              │  Test on    │
    │                    │              │  Staging    │
    │                    │              └──────┬──────┘
    │                    │                     │
    │                    │              PR: develop → preview
    │                    │                     │
    │                    │              preview ◀── Merged
    │                    │              (Production Updated)
```

---

_Updated: 2026-04-08 | Repo: github.com/benpm/newplane_
