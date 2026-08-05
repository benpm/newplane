# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Bidirectional GitHub issue <-> Plane work item sync.

Pull: GitHub issues become work items; GitHub-side close/reopen moves the linked work
item between states. Runs from Celery beat every 5 minutes, cursored by `since`.

Push: completing/reopening a linked work item closes/reopens the GitHub issue. Fired
from a post_save signal on Issue.

Loop suppression lives in GithubIssueLink.github_state: the pull path records the
GitHub state before touching the Plane issue, and the push path only calls GitHub when
Plane's done-ness disagrees with that recorded state — so echoes converge.
"""

from celery import shared_task
from django.utils import timezone

from plane.utils.exception_logger import log_exception

PLANE_DONE_GROUPS = {"completed", "cancelled"}


def _plane_issue_is_done(issue):
    return issue.state is not None and issue.state.group in PLANE_DONE_GROUPS


def _state_for(project, done):
    """Pick the target state: first completed-group state when done, else the
    project default (falling back to the first backlog/unstarted state)."""
    from plane.db.models import State  # avoid circular imports

    states = State.objects.filter(project=project)
    if done:
        return states.filter(group="completed").order_by("sequence").first()
    if project.default_state_id:
        return states.filter(pk=project.default_state_id).first()
    return states.filter(group__in=["backlog", "unstarted"]).order_by("sequence").first()


@shared_task
def schedule_github_issue_syncs():
    """Beat entry point: fan out one sync task per enabled project association."""
    from plane.db.models import ProjectGithubSync

    sync_ids = ProjectGithubSync.objects.filter(is_issue_sync_enabled=True).values_list("id", flat=True)
    for sync_id in sync_ids:
        sync_github_issues_to_project.delay(str(sync_id))


@shared_task
def sync_github_issues_to_project(github_sync_id):
    """Pull direction: upsert work items from the associated repo's issues."""
    from plane.db.models import GithubIssueLink, Issue, ProjectGithubSync
    from plane.utils.github_client import GITHUB_EXTERNAL_SOURCE, GithubClientError, fetch_issues

    github_sync = ProjectGithubSync.objects.filter(pk=github_sync_id).first()
    if github_sync is None or not github_sync.is_issue_sync_enabled:
        return

    started_at = timezone.now()
    since = github_sync.issues_synced_at.isoformat() if github_sync.issues_synced_at else None

    try:
        gh_issues = fetch_issues(github_sync.repository_owner, github_sync.repository_name, since=since)
    except GithubClientError as e:
        github_sync.last_sync_status = f"error: {e}"[:255]
        github_sync.last_synced_at = started_at
        github_sync.save(update_fields=["last_sync_status", "last_synced_at"])
        log_exception(e)
        return

    project = github_sync.project
    created = updated = 0

    for gh_issue in gh_issues:
        try:
            number = gh_issue["number"]
            gh_state = gh_issue.get("state", "open")
            title = (gh_issue.get("title") or f"GitHub issue #{number}")[:255]
            body_html = gh_issue.get("body_html") or "<p></p>"
            gh_updated_at = gh_issue.get("updated_at")

            link = GithubIssueLink.objects.filter(github_sync=github_sync, github_issue_number=number).first()

            if link is None:
                # Re-link a work item imported earlier (or by another sync row) instead
                # of duplicating it.
                existing_issue = Issue.objects.filter(
                    project=project,
                    external_source=GITHUB_EXTERNAL_SOURCE,
                    external_id=str(number),
                ).first()

                if existing_issue is None:
                    issue = Issue.objects.create(
                        project=project,
                        name=title,
                        description_html=body_html,
                        state=_state_for(project, done=gh_state == "closed"),
                        external_source=GITHUB_EXTERNAL_SOURCE,
                        external_id=str(number),
                    )
                    created += 1
                else:
                    issue = existing_issue

                GithubIssueLink.objects.create(
                    github_sync=github_sync,
                    project=project,
                    issue=issue,
                    github_issue_number=number,
                    github_state=gh_state,
                    github_updated_at=gh_updated_at,
                )
                continue

            if link.github_state != gh_state:
                # Record the observed GitHub state BEFORE touching the Plane issue so the
                # push signal fired by issue.save() sees agreement and does nothing.
                link.github_state = gh_state
                link.github_updated_at = gh_updated_at
                link.save(update_fields=["github_state", "github_updated_at"])

                issue = link.issue
                should_be_done = gh_state == "closed"
                if _plane_issue_is_done(issue) != should_be_done:
                    target_state = _state_for(project, done=should_be_done)
                    if target_state is not None:
                        issue.state = target_state
                        issue.save(update_fields=["state"])
                        updated += 1
        except Exception as e:
            log_exception(e)

    github_sync.issues_synced_at = started_at
    github_sync.last_synced_at = started_at
    github_sync.last_sync_status = f"success: {created} created, {updated} updated"
    github_sync.save(update_fields=["issues_synced_at", "last_synced_at", "last_sync_status"])


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

    done = _plane_issue_is_done(link.issue)
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
