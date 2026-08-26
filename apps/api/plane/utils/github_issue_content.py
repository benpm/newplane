# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Content sync for GitHub issues <-> Plane work items.

Deciding whether a work item's title/description or the GitHub issue's is the newer
one, and applying whichever wins. The reconcile phases that call this live in
github_issue_reconcile.py; the Celery entry points in
bgtasks/github_issue_sync_task.py.

Conflict policy is newest-wins, per issue, as it already is per page for the wiki:
when both sides changed, the loser's title *and* body are overwritten wholesale.
Nothing is unrecoverable -- GitHub keeps issue edit history and Plane keeps
IssueDescriptionVersion -- but it is a real cost and callers should know it.
"""

import base64
import re
from datetime import timedelta

from django.utils import timezone

from plane.utils.markdown_conversion import (
    canonical_content,
    content_hash,
    convert_html_to_markdown,
    convert_markdown_to_formats,
)

PLANE_DONE_GROUPS = {"completed", "cancelled"}

# Mutating operations allowed per project per run, shared across creates, content
# updates and state pushes. Exceeding it is not an error: the sweep is idempotent, so
# a capped run and a crashed run leave the same recoverable state.
PUSH_BUDGET_PER_RUN = 20

# Re-fetch a little before the last cursor. Without the overlap a GitHub edit landing
# mid-run falls between "already fetched" and "before the new cursor" and is never
# seen again -- which for content sync means a silently lost body edit.
CURSOR_OVERLAP = timedelta(minutes=10)

# GitHub has no sub-issues in the classic API, so hierarchy is carried as a line of
# body text. It is part of what gets pushed and therefore part of the hash; it is
# stripped again on the way back so it cannot accumulate across round trips.
SUB_TASK_PREFIX = "Sub-task of #"
_SUB_TASK_RE = re.compile(rf"^{re.escape(SUB_TASK_PREFIX)}\d+\s*\n+", re.MULTILINE)


def plane_issue_is_done(issue):
    return issue.state is not None and issue.state.group in PLANE_DONE_GROUPS


def strip_sub_task_reference(markdown):
    return _SUB_TASK_RE.sub("", markdown or "", count=1)


def sub_task_reference(issue):
    """"Sub-task of #N\\n\\n" when the parent is itself linked, else ""."""
    from plane.db.models import GithubIssueLink

    if not issue.parent_id:
        return ""
    parent_number = (
        GithubIssueLink.objects.filter(issue_id=issue.parent_id)
        .values_list("github_issue_number", flat=True)
        .first()
    )
    return f"{SUB_TASK_PREFIX}{parent_number}\n\n" if parent_number else ""


def github_issue_markdown(gh_issue):
    return gh_issue.get("body") or ""


def plane_issue_markdown(issue):
    """The body Plane would send: converted description, plus any sub-task line.

    None when the live server could not convert -- the caller must treat that as
    "unknown", never as "empty".
    """
    markdown = convert_html_to_markdown(issue.description_html)
    if markdown is None:
        return None
    return f"{sub_task_reference(issue)}{markdown}"


def issue_content_hash(title, body_markdown):
    return content_hash(canonical_content(title, body_markdown))


def decide_content_direction(issue, link, gh_title, gh_markdown, gh_updated_at):
    """Return ("pull" | "push" | None, plane_markdown_or_None).

    A change is never inferred from a timestamp. `updated_at` is used only as a gate
    that can produce false positives but never false negatives, and as a tie-break
    once both sides are already proven changed by hash.
    """
    if link.content_hash is None:
        # Never transferred: GitHub is where the content came from, so it wins.
        return "pull", None

    github_changed = issue_content_hash(gh_title, gh_markdown) != link.content_hash

    # `not moved` PROVES the Plane content is untouched. `moved` proves nothing, so
    # the byte comparison below is what actually decides. This gate is a correctness
    # mechanism, not a cache: it is also what stops markdown round-trip drift after a
    # pull being mistaken for a user edit on the very next run.
    if link.content_synced_at is not None and issue.updated_at <= link.content_synced_at:
        return ("pull" if github_changed else None), None

    plane_markdown = plane_issue_markdown(issue)
    if plane_markdown is None:
        # Cannot verify the Plane side, so pushing would be a guess. Pulling is still
        # safe when GitHub demonstrably changed.
        return ("pull" if github_changed else None), None

    plane_changed = issue_content_hash(issue.name, plane_markdown) != link.content_hash

    if github_changed and not plane_changed:
        return "pull", plane_markdown
    if plane_changed and not github_changed:
        return "push", plane_markdown
    if plane_changed and github_changed:
        newer_on_github = gh_updated_at is not None and gh_updated_at > issue.updated_at
        return ("pull" if newer_on_github else "push"), plane_markdown
    return None, plane_markdown


def apply_content_pull(issue, link, gh_title, gh_markdown, gh_updated_at=None):
    """Write GitHub's content onto the work item. Returns whether anything was written."""
    body = strip_sub_task_reference(gh_markdown)
    formats = convert_markdown_to_formats(body, variant="rich")
    if formats is None:
        return False  # retried next run; content_hash is left alone on purpose

    issue.name = (gh_title or "").strip()[:255] or issue.name
    issue.description_html = formats.get("description_html") or "<p></p>"
    issue.description_json = formats.get("description_json") or {}
    binary = formats.get("description_binary")
    # Descriptions are collaborative Y.js documents. Writing HTML without replacing
    # the binary leaves an open editor showing the old text, and it would overwrite
    # this on its next save.
    issue.description_binary = base64.b64decode(binary) if binary else None
    issue.save()

    link.content_hash = issue_content_hash(gh_title, gh_markdown)
    # after issue.save(), so issue.updated_at <= content_synced_at and the gate closes
    link.content_synced_at = timezone.now()
    if gh_updated_at:
        link.github_updated_at = gh_updated_at
    link.save(update_fields=["content_hash", "content_synced_at", "github_updated_at"])
    return True


def apply_content_push(github_sync, issue, link, plane_markdown):
    """Send the work item's content to GitHub. Never touches the Plane issue."""
    from plane.utils.github_client import update_issue

    gh_updated_at = update_issue(
        github_sync.repository_owner,
        github_sync.repository_name,
        link.github_issue_number,
        title=issue.name,
        body=plane_markdown,
    )

    link.content_hash = issue_content_hash(issue.name, plane_markdown)
    link.content_synced_at = timezone.now()
    if gh_updated_at:
        link.github_updated_at = gh_updated_at
    link.save(update_fields=["content_hash", "content_synced_at", "github_updated_at"])
    return True
