# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Opening GitHub issues for Plane work items.

Reached two ways: the post_save fast path (so creating a work item visibly creates an
issue) and phase C of the reconcile sweep (which is what actually guarantees it, since
bulk_create never fires post_save). Both call create_github_issue_for, which is
idempotent, so the two racing on the same work item is safe.
"""

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from plane.utils.exception_logger import log_exception
from plane.utils.github_issue_content import (
    issue_content_hash,
    plane_issue_is_done,
    plane_issue_markdown,
)


def create_github_issue_for(github_sync, issue):
    """Create the GitHub issue mirroring this work item. Returns the link, or None."""
    from plane.db.models import GithubIssueLink, Issue
    from plane.utils.github_client import GITHUB_EXTERNAL_SOURCE, close_issue, create_issue

    existing = GithubIssueLink.objects.filter(issue_id=issue.id).first()
    if existing is not None:
        return existing

    markdown = plane_issue_markdown(issue)
    if markdown is None:
        return None  # live server down; the next sweep retries

    number = create_issue(github_sync.repository_owner, github_sync.repository_name, issue.name, markdown)

    with transaction.atomic():
        link = GithubIssueLink.objects.create(
            github_sync=github_sync,
            project=github_sync.project,
            issue=issue,
            github_issue_number=number,
            github_state="open",
            github_updated_at=timezone.now(),
            content_hash=issue_content_hash(issue.name, markdown),
            content_synced_at=timezone.now(),
        )
        # .update() rather than .save(): it bypasses post_save and, because auto_now
        # is not applied by a queryset update, leaves updated_at alone -- so the
        # content gate stays closed and this create does not read as an edit.
        #
        # external_id is written in the same transaction as the link so that losing
        # the link row still self-heals: the pull path re-links by external_id rather
        # than importing the issue as a second work item. A crash between GitHub's
        # 201 and this commit is the one remaining window, and it is milliseconds.
        Issue.objects.filter(pk=issue.pk).update(
            external_source=GITHUB_EXTERNAL_SOURCE, external_id=str(number)
        )

    if plane_issue_is_done(issue):
        # GitHub cannot create an issue closed, so mirror the state immediately.
        close_issue(github_sync.repository_owner, github_sync.repository_name, number)
        link.github_state = "closed"
        link.save(update_fields=["github_state"])
    return link


def create_missing_github_issues(github_sync, project, budget):
    """Phase C: every unlinked work item in the project. Returns (opened, capped)."""
    from plane.db.models import GithubIssueLink, Issue
    from plane.utils.github_client import GITHUB_EXTERNAL_SOURCE, GithubClientError

    if budget <= 0:
        return 0, False

    # Materialised through the model manager, NOT expressed as a join: a
    # `github_link__isnull=True` filter compiles to a raw LEFT JOIN that ignores the
    # soft-delete manager, so a soft-deleted link would make its work item look
    # linked and it would never be created on GitHub.
    linked_ids = set(GithubIssueLink.objects.filter(github_sync=github_sync).values_list("issue_id", flat=True))

    candidates = (
        Issue.objects.filter(project=project, is_draft=False, archived_at__isnull=True)
        .exclude(id__in=linked_ids)
        # Dedupe rail, not a filter: a work item that came from GitHub but lost its
        # link must be re-linked by phase A, never opened as a second issue.
        .exclude(external_source=GITHUB_EXTERNAL_SOURCE)
        # Parents first, so a sub-item can cite its parent's issue number. nulls_first
        # is required, not decorative: Postgres sorts NULLs last on ASC, so a plain
        # order_by("parent_id") puts every child *before* its parent and the reference
        # comes out empty.
        .order_by(F("parent_id").asc(nulls_first=True), "created_at")
    )

    opened = 0
    for issue in candidates[: budget + 1]:
        if opened >= budget:
            return opened, True
        try:
            if create_github_issue_for(github_sync, issue) is not None:
                opened += 1
        except GithubClientError as e:
            log_exception(e)
            break
    return opened, False
