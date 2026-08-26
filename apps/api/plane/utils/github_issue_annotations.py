# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Attach a work item's GitHub link to issue querysets.

Three correlated subqueries rather than a prefetch or a per-row fetch: the badge
renders on every row of every layout, so anything per-row would be an N+1 across a
whole board. (There is already one of those in the fork --
ce/components/issues/spreadsheet/columns/reference-link-column.tsx fetches per row
behind an IntersectionObserver. Please don't copy it.)

The repository is carried per row even though it is a property of the project. It
costs ~20 characters and means workspace-level views, which span projects, can build
the issue URL without a second request or a new store keyed by project.

GithubIssueLink.objects is a soft-delete manager, so an unlinked-then-relinked work
item resolves to its live link and not a tombstone.
"""

from django.db.models import OuterRef, Subquery, Value
from django.db.models.functions import Concat

# Every place that lists issue fields explicitly has to include these, or the badge
# silently vanishes in that one view. See docs/features.md for the list of sites.
GITHUB_ISSUE_FIELDS = ["github_issue_number", "github_comment_count", "github_repository"]


def github_link_annotations():
    """Annotation kwargs for Issue querysets. Spread into .annotate()."""
    from plane.db.models import GithubIssueLink, ProjectGithubSync

    links = GithubIssueLink.objects.filter(issue_id=OuterRef("id"))
    syncs = ProjectGithubSync.objects.filter(
        project_id=OuterRef("project_id"), is_issue_sync_enabled=True
    ).annotate(full_name=Concat("repository_owner", Value("/"), "repository_name"))

    return {
        "github_issue_number": Subquery(links.values("github_issue_number")[:1]),
        "github_comment_count": Subquery(links.values("github_comment_count")[:1]),
        "github_repository": Subquery(syncs.values("full_name")[:1]),
    }
