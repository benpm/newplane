# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Two-way content sync: title and description. All `gh` and live calls are mocked.

The test that matters most is test_a_state_only_save_pushes_nothing. Issue.updated_at
moves on every full save, so any implementation that infers "the content changed"
from the timestamp will push stale text over a genuine GitHub edit. That one asserts
it does not.
"""

from unittest.mock import patch

import pytest

from plane.bgtasks.github_issue_sync_task import sync_github_issues_to_project
from plane.db.models import GithubIssueLink, Issue
from plane.utils import github_issue_content

# fixtures shared with the state-sync suite
from plane.tests.unit.bg_tasks.test_github_issue_sync_task import (  # noqa: F401
    env,
    gh_issue,
    stub_live_conversion,
)


def run_sync(env, payload):
    with patch("plane.utils.github_client.fetch_issues") as mock_fetch:
        mock_fetch.return_value = payload
        sync_github_issues_to_project(str(env["github_sync"].id))


@pytest.fixture
def linked(env):
    """One work item linked to GitHub issue #1, with content already transferred."""
    run_sync(env, [gh_issue(1, body="original body")])
    issue = Issue.objects.get(project=env["project"], external_id="1")
    return issue, GithubIssueLink.objects.get(issue=issue)


@pytest.mark.unit
@pytest.mark.django_db
class TestContentPull:
    def test_first_sync_transfers_the_body(self, linked):
        issue, link = linked
        assert issue.description_html == "<p>original body</p>"
        assert link.content_hash is not None
        assert link.content_synced_at is not None

    def test_a_github_body_edit_updates_the_work_item(self, env, linked):
        run_sync(env, [gh_issue(1, body="edited on github", updated_at="2026-08-02T00:00:00Z")])
        issue, _ = linked
        issue.refresh_from_db()
        assert issue.description_html == "<p>edited on github</p>"

    def test_a_github_title_edit_updates_the_name(self, env, linked):
        run_sync(env, [gh_issue(1, title="renamed", updated_at="2026-08-02T00:00:00Z")])
        issue, _ = linked
        issue.refresh_from_db()
        assert issue.name == "renamed"

    def test_an_unchanged_second_run_converts_nothing(self, env, linked):
        """Proves the gate is closed, not merely that the hashes matched: a repeat run
        must not even ask the live server to convert."""
        with patch.object(github_issue_content, "convert_html_to_markdown") as mock_convert:
            run_sync(env, [gh_issue(1, body="original body")])
        mock_convert.assert_not_called()


@pytest.mark.unit
@pytest.mark.django_db
class TestContentPush:
    def test_a_plane_description_edit_pushes(self, env, linked):
        issue, _ = linked
        issue.description_html = "<p>edited in plane</p>"
        issue.save()

        with patch("plane.utils.github_client.update_issue") as mock_update:
            mock_update.return_value = "2026-08-03T00:00:00Z"
            run_sync(env, [gh_issue(1, body="original body")])

        mock_update.assert_called_once()
        assert mock_update.call_args.kwargs["body"] == "edited in plane"

    def test_a_plane_title_edit_pushes(self, env, linked):
        issue, _ = linked
        issue.name = "renamed in plane"
        issue.save()

        with patch("plane.utils.github_client.update_issue") as mock_update:
            mock_update.return_value = None
            run_sync(env, [gh_issue(1, body="original body")])

        assert mock_update.call_args.kwargs["title"] == "renamed in plane"

    def test_a_state_only_save_pushes_nothing(self, env, linked):
        """The trap. Moving a work item to Done is a full save, so updated_at moves
        and the gate opens -- but the content is byte-identical, so nothing may be
        pushed. An implementation that trusts the timestamp fails here."""
        issue, _ = linked
        issue.state = env["done"]
        issue.save()  # full save, not update_fields: updated_at moves

        with patch("plane.utils.github_client.update_issue") as mock_update:
            run_sync(env, [gh_issue(1, body="original body", state="closed")])

        mock_update.assert_not_called()

    def test_nothing_is_pushed_when_the_live_server_cannot_convert(self, env, linked):
        issue, _ = linked
        issue.description_html = "<p>edited in plane</p>"
        issue.save()

        with patch.object(github_issue_content, "convert_html_to_markdown", return_value=None):
            with patch("plane.utils.github_client.update_issue") as mock_update:
                run_sync(env, [gh_issue(1, body="original body")])

        mock_update.assert_not_called()


@pytest.mark.unit
@pytest.mark.django_db
class TestBothSidesChanged:
    def edit_both(self, linked):
        issue, link = linked
        issue.description_html = "<p>plane wins</p>"
        issue.save()
        return issue, link

    def test_github_newer_wins(self, env, linked):
        issue, _ = self.edit_both(linked)
        # far in the future, so GitHub is unambiguously the later edit
        with patch("plane.utils.github_client.update_issue") as mock_update:
            run_sync(env, [gh_issue(1, body="github wins", updated_at="2099-01-01T00:00:00Z")])

        mock_update.assert_not_called()
        issue.refresh_from_db()
        assert issue.description_html == "<p>github wins</p>"

    def test_plane_newer_wins(self, env, linked):
        issue, _ = self.edit_both(linked)
        with patch("plane.utils.github_client.update_issue") as mock_update:
            mock_update.return_value = None
            run_sync(env, [gh_issue(1, body="github loses", updated_at="2000-01-01T00:00:00Z")])

        assert mock_update.call_args.kwargs["body"] == "plane wins"
        issue.refresh_from_db()
        assert issue.description_html == "<p>plane wins</p>"

    def test_a_live_outage_pulls_rather_than_guessing(self, env, linked):
        """With the Plane side unverifiable, pushing would be a guess. Pulling is
        still safe because GitHub demonstrably changed."""
        self.edit_both(linked)
        with patch.object(github_issue_content, "convert_html_to_markdown", return_value=None):
            with patch("plane.utils.github_client.update_issue") as mock_update:
                run_sync(env, [gh_issue(1, body="github changed", updated_at="2026-08-05T00:00:00Z")])

        mock_update.assert_not_called()
        issue, _ = linked
        issue.refresh_from_db()
        assert issue.description_html == "<p>github changed</p>"
