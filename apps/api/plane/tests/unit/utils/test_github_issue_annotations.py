# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""The GitHub link annotations that feed the work item badge.

The failure mode these guard against is silent: a view that annotates but forgets to
list the fields (or vice versa) simply renders no badge in that one layout, with no
error anywhere.
"""

import pytest

from plane.db.models import GithubIssueLink, Issue, ProjectGithubSync, State
from plane.tests.factories import ProjectFactory, UserFactory, WorkspaceFactory, WorkspaceMemberFactory
from plane.utils.github_issue_annotations import GITHUB_ISSUE_FIELDS, github_link_annotations


@pytest.fixture
def env(db):
    owner = UserFactory()
    workspace = WorkspaceFactory(owner=owner)
    WorkspaceMemberFactory(workspace=workspace, member=owner, role=20)
    project = ProjectFactory(workspace=workspace)
    backlog = State.objects.create(project=project, name="Backlog", group="backlog", color="#111", sequence=1)
    github_sync = ProjectGithubSync.objects.create(
        project=project, repository_owner="acme", repository_name="widgets"
    )
    return {"project": project, "backlog": backlog, "github_sync": github_sync}


def annotated(project):
    return Issue.objects.filter(project=project).annotate(**github_link_annotations()).values(
        "id", *GITHUB_ISSUE_FIELDS
    )


@pytest.mark.unit
@pytest.mark.django_db
class TestGithubLinkAnnotations:
    def make(self, env, name="work item"):
        return Issue.objects.create(project=env["project"], name=name, state=env["backlog"])

    def test_a_linked_item_carries_its_number_repository_and_comment_count(self, env):
        issue = self.make(env)
        GithubIssueLink.objects.create(
            github_sync=env["github_sync"],
            project=env["project"],
            issue=issue,
            github_issue_number=12,
            github_state="open",
            github_comment_count=3,
        )

        row = annotated(env["project"]).get(id=issue.id)
        assert row["github_issue_number"] == 12
        assert row["github_comment_count"] == 3
        # carried per row so workspace views, which span projects, can build the URL
        assert row["github_repository"] == "acme/widgets"

    def test_an_unlinked_item_has_a_null_number(self, env):
        """MobX writes partial work items optimistically, so a freshly created one
        must render no badge rather than a broken one."""
        issue = self.make(env)
        row = annotated(env["project"]).get(id=issue.id)
        assert row["github_issue_number"] is None

    def test_a_soft_deleted_link_is_not_resolved(self, env):
        issue = self.make(env)
        link = GithubIssueLink.objects.create(
            github_sync=env["github_sync"],
            project=env["project"],
            issue=issue,
            github_issue_number=12,
            github_state="open",
        )
        link.delete()

        assert annotated(env["project"]).get(id=issue.id)["github_issue_number"] is None

    def test_one_query_regardless_of_row_count(self, django_assert_num_queries):
        """Correlated subqueries, not a per-row fetch: the badge is on every row of
        every layout, so an N+1 here is an N+1 across a whole board."""
        owner = UserFactory()
        workspace = WorkspaceFactory(owner=owner)
        WorkspaceMemberFactory(workspace=workspace, member=owner, role=20)
        project = ProjectFactory(workspace=workspace)
        state = State.objects.create(project=project, name="B", group="backlog", color="#111", sequence=1)
        sync = ProjectGithubSync.objects.create(
            project=project, repository_owner="acme", repository_name="widgets"
        )
        for i in range(10):
            issue = Issue.objects.create(project=project, name=f"item {i}", state=state)
            GithubIssueLink.objects.create(
                github_sync=sync, project=project, issue=issue, github_issue_number=i, github_state="open"
            )

        with django_assert_num_queries(1):
            rows = list(annotated(project))
        assert len(rows) == 10
        assert all(r["github_repository"] == "acme/widgets" for r in rows)
