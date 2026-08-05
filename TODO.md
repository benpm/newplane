# Todo
<!-- AGENT:
    work on these tasks when asked to. Make sure to build and test everything in a separate dev environment before deploying to production. Make sure to thoroughly test your changes before moving on to the next task. One task, one commit.
    
    when a task is completed, mark it as done and copy them to CHANGELOG.md, and make sure to update docs and README.md
     -->

**newplane** is a fork of plane with additional features, including extensive synchronization with a git repo that can be associated with a specific project.

See [./CHANGELOG.md](./CHANGELOG.md) for a list of changes and new features.

- [ ] Allow guests to view the project without logging in, but not able to edit
- [ ] Discord integration for notifications and updates for when new work items are created, updated, or completed. Should be customizable. Allow commands for various actions, such as creating a new work item, updating an existing one, or marking a work item as complete. Allow for multiple Discord servers to be integrated with the same project.
- [ ] Integrate GitHub Actions to automatically rebuild the site when changes are pushed to the repository.
- [ ] Enable Google SSO for authentication, allowing users to log in with their Google accounts. This should create an account with the associated email address if one does not already exist, and allow for linking to an existing account if the email address is already associated with a different account. Make sure to write tests and handle edge cases, such as when a user tries to log in with a Google account that is already associated with a different account.

## Dev-site hardening (2026-08-05)

Work queued from testing this branch on the dev site. One task, one commit.

- [x] Fix the live/space image builds — pnpm global bin dir missing from PATH
- [x] Fix sub-page creation returning 500 — `project_ids` reaching `Page.objects.create()`
- [x] Restore the stock email sign-in flow so any account can authenticate
- [x] Replace Shinhan branding with stock Plane across web, admin, i18n and emails
- [x] Add an isolated dev-site stack + log feed script
- [ ] Fix the GitHub wiki sync Celery task never running — beat schedules
      `github_wiki_sync_task.schedule_github_wiki_syncs` but `autodiscover_tasks()`
      does not register it, so the worker discards every message
- [x] Fix the GitHub wiki sync Celery task never running
- [x] Fix the failing unit tests. `497 passed / 22 failed / 10 errors` →
      **`529 passed, 0 failed, 0 errors`**. Run: `./scripts/dev-site-test.sh -m unit`.
- [x] Fix the contract/smoke suites. **All suites green: 975 passed, 0 failed,
      0 errors** (`./scripts/dev-site-test.sh`).
- [ ] Raise backend coverage toward 90%. **Currently 50%** (15,448 / 30,922
      statements). Reaching 90% means covering ~12,400 more statements — the
      two dense utility suites added here covered ~180 across 102 tests, so
      this is several thousand more tests, not a single sitting.
      Highest-value targets by uncovered statements:
      | module | missing |
      |---|---|
      | `license/api/views/department.py` | 328 |
      | `app/views/asset/v2.py` | 306 |
      | `app/views/ho.py` | 274 |
      | `license/api/views/staff.py` | 252 |
      | `api/views/issue.py` | 250 |
      | `bgtasks/issue_activities_task.py` | 243 |
      | `app/views/issue/base.py` | 217 |
      | `app/views/workspace/staff.py` | 211 |
      | `app/views/search/base.py` | 206 |
      | `app/views/analytic/advance.py` | 178 |
      Suggested order: finish the pure-logic utils (cheap, no DB), then the
      fork-specific view modules above, which are both the least covered and
      the least exercised by upstream tests.
- [ ] Sweep for further unrelated bugs surfaced by the dev site logs
- [ ] Remove the remaining Shinhan branding: the Vietnamese help-centre fixtures
      (~40 files, note the `lam-quen-shinhan-workspace` slug is cross-referenced)
      and the seed-data org names in `seed_department_staff_data.py`
- [ ] Audit the UI for dark-theme correctness — no hardcoded colours, semantic
      tokens only, no `dark:` variants (see `.claude/rules/color-tokens.md`)

