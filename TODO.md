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
- [x] Fix the GitHub wiki sync Celery task never running — beat scheduled
      `github_wiki_sync_task.schedule_github_wiki_syncs` but nothing imported the
      module, so the worker discarded every message as unregistered
- [x] Fix the failing tests. `497 passed / 22 failed / 10 errors` →
      **`1097 passed, 0 failed, 0 errors`** across unit, contract and smoke.
      Run: `./scripts/dev-site-test.sh`.
- [x] Fix the sub-page count disagreeing with the sub-page list, and the
      recursive archive hanging on a parent loop
- [x] Stop the public invite endpoint returning its own acceptance token

### Prioritising by what this instance actually runs

Row counts on the live database, not uncovered-statement counts, should drive
what gets hardened next. Every fork headline feature holds **zero rows** —
departments, staff profiles, GitHub sync, HO export, dashboards,
worklogs, capacity exports — so their large uncovered surface is not what puts
the deployment at risk. The tables carrying real data are core Plane: issue
activities, notifications, recent visits, issues, states, holidays,
invitations, pages, module/cycle issues and file assets.

Re-check with:

```sql
SELECT relname, n_live_tup FROM pg_stat_user_tables
WHERE n_live_tup > 0 ORDER BY n_live_tup DESC;
```

- [ ] Continue bug-hunting where in-use features meet fork-modified code. Done:
      pages, invitations. Not yet examined: issue activities, notifications and
      their email logs, recent visits, file assets, the business calendar.
- [ ] Decide the invite-acceptance question left open: acceptance currently
      needs only the emailed token, with no authenticated session and no check
      that the caller's email matches the invitee. Upstream requires both
      (GHSA-4vj8-p63v-8p24). Adding it changes who can accept, so it needs a
      decision rather than a silent behaviour change.
- [ ] Raise backend coverage. **Currently 52%** (~16,000 / 30,922 statements).
      90% means covering ~12,000 more — several thousand tests, not a single
      sitting. Prefer coverage of in-use paths over the global percentage.
- [x] Remove the remaining Shinhan branding — done wholesale: the Help Centre
      feature was removed (its whole corpus was Vietnamese-only), the `vi`/`ko`
      locales dropped, Bank-wide Projects renamed to Global Projects, the SSO
      email domain made configurable, and the seed/calendar/ops/docs de-branded
- [ ] Audit the UI for dark-theme correctness — no hardcoded colours, semantic
      tokens only, no `dark:` variants (see `.claude/rules/color-tokens.md`)
