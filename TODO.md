# Newplane TODO

> ## **Instructions**
>
> - Work on these tasks when asked to
> - Build and test everything in a separate dev environment before deploying to production
> - Thoroughly test your changes before moving on to the next task. One task, one commit.
> - When a task is completed, mark it as done and move it to `CHANGELOG.md`, then update docs and `README.md`
> - See `CHANGELOG.md` for a list of changes and new features. Cut and paste finished tasks there. Before getting started here, remove completed tasks, and add them to the changelog.
> - _Before starting on a task_, make sure there is enough information to complete it. If not, ask for clarification before starting. If it's done already, mark it as done and copy it to CHANGELOG.md.

---

## Page / Task Markdown Editor

For the markdown editor in tasks and pages.

- [x] Typing `#` in the middle of the line should pull up a list search for issues to link to. Text with `#13` should link to issue 13, for instance.
- [x] The padding amount between list items in suggestion lists like when autocompleting in the text editor should be smaller, and configurable. Add to docs how to configure it. The number of items in the list should also be configurable, and documented.
- [x] Add a button in the toolbar for adding links. This should open a modal with a search box to search for issues or pages to link to. The modal should have a list of recently viewed issues, and a search box to search for issues by title or ID. The search results should be displayed in a list, and clicking on an issue should insert a link to that issue in the editor.

## _Miscellaneous_

- [x] The github link icon in the top right of each work item is cut off. Only a quarter of it is visible. (Fixed with `GitHub_Invertocat_White.png`)
- [x] Hide work item slug entirely and replace with `#<id>` (e.g., `#32` instead of `MOUSE-32`), styled smaller and dimmer.
- [x] Hide buttons for adding tags and due dates when they are empty for that work item in Board view.

- [x] Make a constantly changing identifier string made of words related to the current project. Should relate to your task somewhat, but cant be more than 64 characters. be very creative, use numbers and symbols and emojis too. Draw the string right next to the search box.
- [x] When user is creating their account, instead of showing the screen for creating a project / workspace, show existing projects that user can join. _Do not allow normal users to create Workspace or Project._
- [x] Allow anyone including new guests to view the project tasks and pages without logging in, but not able to edit.
- [x] Discord integration for notifications and updates for when new work items are created, updated, or completed. Should be customizable. Allow commands for various actions, such as creating a new work item, updating an existing one, or marking a work item as complete. Allow for multiple Discord servers to be integrated with the same project.
- [x] Integrate GitHub Actions to automatically rebuild the site when changes are pushed to the repository.
- [x] Enable Google SSO for authentication, allowing users to log in with their Google accounts. This should create an account with the associated email address if one does not already exist, and allow for linking to an existing account if the email address is already associated with a different account. Make sure to write tests and handle edge cases, such as when a user tries to log in with a Google account that is already associated with a different account.

## Dev-site hardening (2026-08-05)

<!-- AGENT: Move these to CHANGELOG.md after testing -->

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
      Run: `./scripts/plane test`.
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

<!-- AGENT: Move these to CHANGELOG.md after testing -->

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
