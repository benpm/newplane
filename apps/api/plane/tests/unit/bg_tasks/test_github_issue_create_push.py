# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Creating GitHub issues from Plane work items. All `gh` and live calls are mocked.

Covers the reconcile sweep (phase C) and the post_save fast path, plus the two rails
that stop it duplicating: the external_source dedupe and the soft-delete-aware link
lookup.
"""

from unittest.mock import patch

import pytest

from plane.bgtasks.github_issue_sync_task import (
    create_github_issue_for_work_item,
    sync_github_issues_to_project,
)
from plane.db.models import GithubIssueLink, Issue
from plane.utils.github_issue_content import PUSH_BUDGET_PER_RUN

# fixtures shared with the state-sync suite
from plane.tests.unit.bg_tasks.test_github_issue_sync_task import (  # noqa: F401
    env,
    gh_issue,
    stub_live_conversion,
)


def run_sync(env, payload=None, next_number=101):
    """Run one sweep with `create_issue` handing out sequential numbers."""
    with patch("plane.utils.github_client.fetch_issues") as mock_fetch:
        mock_fetch.return_value = payload or []
        with patch("plane.utils.github_client.create_issue") as mock_create:
            with patch("plane.utils.github_client.close_issue") as mock_close:
                mock_create.side_effect = [n for n in range(next_number, next_number + 200)]
                sync_github_issues_to_project(str(env["github_sync"].id))
                return mock_create, mock_close


def make_item(env, name="native work item", state=None, **kwargs):
    return Issue.objects.create(
        project=env["project"], name=name, state=state or env["backlog"], **kwargs
    )


@pytest.mark.unit
@pytest.mark.django_db
class TestCreateFromPlane:
    def test_an_unlinked_work_item_becomes_a_github_issue(self, env):
        issue = make_item(env)
        mock_create, _ = run_sync(env)

        mock_create.assert_called_once()
        assert mock_create.call_args[0][2] == "native work item"  # title
        link = GithubIssueLink.objects.get(issue=issue)
        assert link.github_issue_number == 101
        assert link.content_hash is not None
        issue.refresh_from_db()
        # external_id is written in the same transaction as the link, so a lost link
        # self-heals through the pull path instead of duplicating the work item
        assert issue.external_source == "github"
        assert issue.external_id == "101"

    def test_a_done_work_item_is_created_then_closed(self, env):
        """GitHub cannot open an issue in the closed state, so the sync mirrors it
        immediately after. This is the backfill's cancelled-work case."""
        make_item(env, name="already finished", state=env["done"])
        mock_create, mock_close = run_sync(env)

        mock_create.assert_called_once()
        mock_close.assert_called_once_with("acme", "widgets", 101)
        assert GithubIssueLink.objects.get(github_issue_number=101).github_state == "closed"

    def test_a_second_sweep_creates_nothing(self, env):
        make_item(env)
        run_sync(env)
        mock_create, _ = run_sync(env, next_number=999)
        mock_create.assert_not_called()

    def test_drafts_and_archived_items_are_never_pushed(self, env):
        from django.utils import timezone

        make_item(env, name="draft", is_draft=True)
        make_item(env, name="archived", archived_at=timezone.now().date())
        mock_create, _ = run_sync(env)
        mock_create.assert_not_called()

    def test_a_github_origin_item_without_a_link_is_not_recreated(self, env):
        """The dedupe rail. Without it, disconnecting and reconnecting a repository
        would open a second GitHub issue for every work item."""
        make_item(env, name="came from github", external_source="github", external_id="7")
        mock_create, _ = run_sync(env)
        mock_create.assert_not_called()

    def test_a_soft_deleted_link_does_not_make_an_item_look_linked(self, env):
        """Link lookups must go through the model manager. Expressed as a
        `github_link__isnull=True` join instead, the raw LEFT JOIN sees soft-deleted
        rows and the work item would be excluded from creation forever."""
        issue = make_item(env, name="unlinked again")
        link = GithubIssueLink.objects.create(
            github_sync=env["github_sync"],
            project=env["project"],
            issue=issue,
            github_issue_number=55,
            github_state="open",
        )
        link.delete()  # soft delete

        mock_create, _ = run_sync(env)
        mock_create.assert_called_once()

    def test_the_budget_caps_a_run_and_says_so(self, env):
        for i in range(PUSH_BUDGET_PER_RUN + 5):
            make_item(env, name=f"item {i}")

        mock_create, _ = run_sync(env)
        assert mock_create.call_count == PUSH_BUDGET_PER_RUN

        env["github_sync"].refresh_from_db()
        # a capped run must not read as a complete one
        assert "capped" in env["github_sync"].issue_sync_status

        mock_create, _ = run_sync(env, next_number=500)
        assert mock_create.call_count == 5


@pytest.mark.unit
@pytest.mark.django_db
class TestSubTasks:
    def test_a_sub_item_cites_its_parent_issue_number(self, env):
        parent = make_item(env, name="parent")
        make_item(env, name="child", parent=parent)

        mock_create, _ = run_sync(env)

        bodies = {call[0][2]: call[0][3] for call in mock_create.call_args_list}
        assert "Sub-task of #" in bodies["child"]
        # parents are created first, so the number it cites is the parent's
        parent_number = GithubIssueLink.objects.get(issue=parent).github_issue_number
        assert f"Sub-task of #{parent_number}" in bodies["child"]
        assert "Sub-task of #" not in bodies["parent"]

    def test_the_reference_is_stripped_on_the_way_back(self, env):
        """It is part of the pushed body and therefore part of the hash, but it must
        not accumulate in the work item across round trips."""
        parent = make_item(env, name="parent")
        child = make_item(env, name="child", parent=parent)
        run_sync(env)

        number = GithubIssueLink.objects.get(issue=child).github_issue_number
        parent_number = GithubIssueLink.objects.get(issue=parent).github_issue_number
        run_sync(
            env,
            payload=[
                gh_issue(
                    number,
                    title="child",
                    body=f"Sub-task of #{parent_number}\n\nedited on github",
                    updated_at="2099-01-01T00:00:00Z",
                )
            ],
            next_number=700,
        )

        child.refresh_from_db()
        assert "Sub-task of #" not in child.description_html
        assert "edited on github" in child.description_html


@pytest.mark.unit
@pytest.mark.django_db
class TestFastPath:
    def test_the_signal_task_creates_the_issue(self, env):
        issue = make_item(env)
        with patch("plane.utils.github_client.create_issue", return_value=42):
            create_github_issue_for_work_item(str(issue.id))

        assert GithubIssueLink.objects.get(issue=issue).github_issue_number == 42

    def test_racing_the_sweep_produces_exactly_one_issue(self, env):
        """Both paths call the same idempotent helper, so a fast path that has
        already run leaves the sweep with nothing to do."""
        issue = make_item(env)
        with patch("plane.utils.github_client.create_issue", return_value=42):
            create_github_issue_for_work_item(str(issue.id))

        mock_create, _ = run_sync(env, next_number=900)
        mock_create.assert_not_called()
        assert GithubIssueLink.objects.filter(issue=issue).count() == 1

    def test_a_project_with_no_connected_repo_is_skipped(self, env):
        env["github_sync"].delete()
        issue = make_item(env)
        with patch("plane.utils.github_client.create_issue") as mock_create:
            create_github_issue_for_work_item(str(issue.id))
        mock_create.assert_not_called()
