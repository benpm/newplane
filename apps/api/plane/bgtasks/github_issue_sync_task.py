# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Bidirectional GitHub issue <-> Plane work item sync.

Everything except comments mirrors both ways: issues and work items are created on
both sides, and title, description and open/closed state converge.

One run does three phases, in this order for reasons that are not interchangeable:

  A  unlinked GitHub issues become work items, and are immediately content-filled
  B  every live link reconciles state, then content
  C  unlinked work items become GitHub issues, budget permitting

A precedes B so a link created this run is populated this run. C is last so an issue
created here cannot be seen by the fetch that already happened, which would otherwise
look like an unlinked remote issue and be imported straight back.

State pushes are immediate, fired by a post_save signal on Issue. Creation has a fast
path on that same signal and this sweep as its backstop; content is reconciled only
here, because doing it on the signal reintroduces the echo loop the hashes exist to
prevent.

Loop suppression: GithubIssueLink.github_state for state, GithubIssueLink.content_hash
for content. See the model docstring -- the hash decides *whether* a side changed, the
timestamp only gates and tie-breaks.

The phases live in plane/utils/github_issue_reconcile.py and the content decisions in
plane/utils/github_issue_content.py. This module stays the Celery surface: its task
names are referenced by the beat schedule and by messages already queued in Redis, so
they must not move.
"""

from celery import shared_task
from django.utils import timezone

from plane.utils.exception_logger import log_exception
from plane.utils.github_issue_content import (
    CURSOR_OVERLAP,
    PLANE_DONE_GROUPS,
    PUSH_BUDGET_PER_RUN,
    plane_issue_is_done,
)
from plane.utils.github_issue_create import create_github_issue_for, create_missing_github_issues
from plane.utils.github_issue_reconcile import import_new_issues, reconcile_link, target_state_for

__all__ = [
    "PLANE_DONE_GROUPS",
    "schedule_github_issue_syncs",
    "sync_github_issues_to_project",
    "push_issue_state_to_github",
    "create_github_issue_for_work_item",
    "target_state_for",
]


@shared_task
def schedule_github_issue_syncs():
    """Beat entry point: fan out one sync task per enabled project association."""
    from plane.db.models import ProjectGithubSync

    sync_ids = ProjectGithubSync.objects.filter(is_issue_sync_enabled=True).values_list("id", flat=True)
    for sync_id in sync_ids:
        sync_github_issues_to_project.delay(str(sync_id))


@shared_task
def sync_github_issues_to_project(github_sync_id):
    """One reconcile run for one project<->repo association."""
    from plane.db.models import GithubIssueLink, ProjectGithubSync
    from plane.utils.github_client import GithubClientError, fetch_issues

    github_sync = ProjectGithubSync.objects.filter(pk=github_sync_id).first()
    if github_sync is None or not github_sync.is_issue_sync_enabled:
        return

    started_at = timezone.now()
    cursor = github_sync.issues_cursor_at
    since = (cursor - CURSOR_OVERLAP).isoformat() if cursor else None

    try:
        gh_issues = fetch_issues(github_sync.repository_owner, github_sync.repository_name, since=since)
    except GithubClientError as e:
        github_sync.issue_sync_status = f"error: {e}"[:255]
        github_sync.issue_synced_at = started_at
        # the cursor deliberately does NOT advance: a failed fetch must not skip the
        # window it never managed to read
        github_sync.save(update_fields=["issue_sync_status", "issue_synced_at"])
        log_exception(e)
        return

    project = github_sync.project
    created = import_new_issues(github_sync, gh_issues, project)

    by_number = {gh_issue["number"]: gh_issue for gh_issue in gh_issues}
    budget = PUSH_BUDGET_PER_RUN
    pulled = pushed = 0
    links = GithubIssueLink.objects.filter(github_sync=github_sync).select_related("issue__state")
    for link in links:
        try:
            one_pulled, one_pushed, spent = reconcile_link(
                github_sync, link, by_number.get(link.github_issue_number), project, budget
            )
            pulled += one_pulled
            pushed += one_pushed
            budget -= spent
        except Exception as e:
            log_exception(e)

    opened, capped = create_missing_github_issues(github_sync, project, budget)

    github_sync.issues_cursor_at = started_at
    github_sync.issue_synced_at = timezone.now()
    status = f"success: {created} created, {pulled} pulled, {pushed} pushed, {opened} on github"
    if capped:
        # never truncate silently -- a capped run reads as a complete one otherwise
        status += f" (capped at {PUSH_BUDGET_PER_RUN}, rest next run)"
    github_sync.issue_sync_status = status[:255]
    github_sync.save(update_fields=["issues_cursor_at", "issue_synced_at", "issue_sync_status"])


@shared_task
def create_github_issue_for_work_item(issue_id):
    """Fast path for creation, enqueued by the post_save signal with a short delay.

    The sweep would get here within five minutes anyway; this exists so that creating
    a work item visibly creates a GitHub issue. Idempotent, so racing the sweep is
    safe.
    """
    from plane.db.models import Issue, ProjectGithubSync
    from plane.utils.github_client import GithubClientError

    issue = Issue.objects.filter(pk=issue_id, is_draft=False, archived_at__isnull=True).first()
    if issue is None:
        return
    github_sync = ProjectGithubSync.objects.filter(
        project_id=issue.project_id, is_issue_sync_enabled=True
    ).first()
    if github_sync is None:
        return
    try:
        create_github_issue_for(github_sync, issue)
    except GithubClientError as e:
        log_exception(e)  # the next sweep retries


@shared_task
def push_issue_state_to_github(issue_id):
    """Push direction: close/reopen the linked GitHub issue when Plane's state moved."""
    from plane.db.models import GithubIssueLink
    from plane.utils.github_client import GithubClientError, close_issue, reopen_issue

    link = (
        GithubIssueLink.objects.filter(issue_id=issue_id)
        .select_related("issue__state", "github_sync")
        .first()
    )
    if link is None or not link.github_sync.is_issue_sync_enabled:
        return

    done = plane_issue_is_done(link.issue)
    target_gh_state = "closed" if done else "open"
    if link.github_state == target_gh_state:
        return  # states agree — nothing to push (this is the echo suppression)

    github_sync = link.github_sync
    try:
        if done:
            close_issue(github_sync.repository_owner, github_sync.repository_name, link.github_issue_number)
        else:
            reopen_issue(github_sync.repository_owner, github_sync.repository_name, link.github_issue_number)
    except GithubClientError as e:
        log_exception(e)
        return

    link.github_state = target_gh_state
    link.github_updated_at = timezone.now()
    link.save(update_fields=["github_state", "github_updated_at"])
