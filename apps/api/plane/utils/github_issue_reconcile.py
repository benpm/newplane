# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""The pull-side reconcile phases of one GitHub issue sync run.

  A  import_new_issues  unlinked GitHub issues become work items
  B  reconcile_link     a live link's state, then its content

Phase C (opening GitHub issues for unlinked work items) lives in
github_issue_create.py, content decisions in github_issue_content.py, and the Celery
entry points in bgtasks/github_issue_sync_task.py. The phase order is not
interchangeable -- see the task module docstring.
"""

from django.utils import timezone
from django.utils.dateparse import parse_datetime

from plane.utils.exception_logger import log_exception
from plane.utils.github_issue_content import (
    PLANE_DONE_GROUPS,
    apply_content_pull,
    apply_content_push,
    decide_content_direction,
    github_issue_markdown,
    plane_issue_is_done,
)


def target_state_for(project, done):
    """Pick the target state: first completed-group state when done, else a state
    that is definitively *not* done.

    The not-done branch cannot simply trust `project.default_state`. A project is
    free to nominate any state as its default, including one in PLANE_DONE_GROUPS
    -- and a project here really does default to "Cancelled". Honouring that put
    every open GitHub issue into a state this module then read back as done, which
    made the push path disagree with `link.github_state` and close the very issue
    that had just been imported as open. So the default is used only when it is
    genuinely not-done, and otherwise ignored.
    """
    from plane.db.models import State  # avoid circular imports

    states = State.objects.filter(project=project)
    if done:
        return states.filter(group="completed").order_by("sequence").first()

    not_done = states.exclude(group__in=PLANE_DONE_GROUPS)
    if project.default_state_id:
        default_state = not_done.filter(pk=project.default_state_id).first()
        if default_state is not None:
            return default_state
    return not_done.filter(group__in=["unstarted", "backlog"]).order_by("sequence").first() or (
        not_done.order_by("sequence").first()
    )


def import_new_issues(github_sync, gh_issues, project):
    """Phase A. Returns the number of work items created."""
    from plane.db.models import GithubIssueLink, Issue
    from plane.utils.github_client import GITHUB_EXTERNAL_SOURCE

    created = 0
    for gh_issue in gh_issues:
        try:
            number = gh_issue["number"]
            if GithubIssueLink.objects.filter(github_sync=github_sync, github_issue_number=number).exists():
                continue

            gh_state = gh_issue.get("state", "open")
            title = (gh_issue.get("title") or f"GitHub issue #{number}")[:255]

            # Re-link a work item imported earlier (or by another sync row) rather
            # than duplicating it.
            issue = Issue.objects.filter(
                project=project, external_source=GITHUB_EXTERNAL_SOURCE, external_id=str(number)
            ).first()
            if issue is None:
                issue = Issue.objects.create(
                    project=project,
                    name=title,
                    description_html="<p></p>",
                    state=target_state_for(project, done=gh_state == "closed"),
                    external_source=GITHUB_EXTERNAL_SOURCE,
                    external_id=str(number),
                )
                created += 1

            link = GithubIssueLink.objects.create(
                github_sync=github_sync,
                project=project,
                issue=issue,
                github_issue_number=number,
                github_state=gh_state,
                github_updated_at=parse_datetime(gh_issue.get("updated_at") or "") or timezone.now(),
                github_comment_count=gh_issue.get("comments") or 0,
            )
            # content_hash stays None if this fails, which forces a pull next run
            apply_content_pull(issue, link, title, github_issue_markdown(gh_issue))
        except Exception as e:
            log_exception(e)
    return created


def _reconcile_state(github_sync, link, gh_issue, project, budget):
    """State half of phase B. Returns budget spent."""
    from plane.utils.github_client import close_issue, reopen_issue

    issue = link.issue
    gh_state = gh_issue.get("state", "open")

    if link.github_state != gh_state:
        # Record the observed state BEFORE touching the Plane issue so the push
        # signal fired by issue.save() sees agreement and does nothing.
        link.github_state = gh_state
        link.save(update_fields=["github_state"])
        should_be_done = gh_state == "closed"
        if plane_issue_is_done(issue) != should_be_done:
            target_state = target_state_for(project, done=should_be_done)
            if target_state is not None:
                issue.state = target_state
                issue.save(update_fields=["state"])
        return 0

    if budget > 0 and plane_issue_is_done(issue) != (link.github_state == "closed"):
        # Self-heals a signal-fired state push that failed.
        done = plane_issue_is_done(issue)
        (close_issue if done else reopen_issue)(
            github_sync.repository_owner, github_sync.repository_name, link.github_issue_number
        )
        link.github_state = "closed" if done else "open"
        link.save(update_fields=["github_state"])
        return 1
    return 0


def reconcile_link(github_sync, link, gh_issue, project, budget):
    """Phase B for one link. Returns (pulled, pushed, budget_spent)."""
    from plane.utils.github_client import GithubClientError

    pulled = pushed = spent = 0
    issue = link.issue

    if gh_issue is not None:
        comment_count = gh_issue.get("comments") or 0
        if comment_count != link.github_comment_count:
            link.github_comment_count = comment_count
            link.save(update_fields=["github_comment_count"])
        spent += _reconcile_state(github_sync, link, gh_issue, project, budget)
        budget -= spent

    gh_title = (gh_issue or {}).get("title") or issue.name
    gh_markdown = github_issue_markdown(gh_issue or {})
    gh_updated_at = parse_datetime((gh_issue or {}).get("updated_at") or "")

    direction, plane_markdown = decide_content_direction(issue, link, gh_title, gh_markdown, gh_updated_at)
    if direction == "pull" and gh_issue is not None:
        if apply_content_pull(issue, link, gh_title, gh_markdown, gh_updated_at):
            pulled += 1
    elif direction == "push" and budget > 0:
        try:
            if apply_content_push(github_sync, issue, link, plane_markdown):
                pushed += 1
                spent += 1
        except GithubClientError as e:
            log_exception(e)
    return pulled, pushed, spent
