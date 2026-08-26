# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""
GitHub issue <-> Plane work item sync. All `gh` calls are mocked; no network involved.

  pull   -> GH issues become work items (open -> default state, closed -> completed)
  pull   -> idempotent: a second run over the same payload creates nothing new
  pull   -> GH close moves the linked work item to a completed state
  push   -> completing a linked work item closes the GH issue exactly once
  push   -> unlinked issues never invoke gh
  loop   -> a pull-applied close leaves the push a no-op (states agree)
"""

from unittest.mock import patch

import pytest

from plane.bgtasks.github_issue_sync_task import (
    PLANE_DONE_GROUPS,
    push_issue_state_to_github,
    sync_github_issues_to_project,
)
from plane.db.models import GithubIssueLink, Issue, ProjectGithubSync, State
from plane.utils import github_issue_content
from plane.tests.factories import ProjectFactory, UserFactory, WorkspaceFactory, WorkspaceMemberFactory


def gh_issue(number, state="open", title=None, body="from github", updated_at="2026-08-01T00:00:00Z"):
    """GitHub's issues payload as this sync consumes it: raw markdown `body`, not
    rendered `body_html`. Markdown is the interchange format in both directions so
    the two sides can be compared by hashing."""
    return {
        "number": number,
        "state": state,
        "title": title or f"GH issue {number}",
        "body": body,
        "comments": 0,
        "updated_at": updated_at,
    }


@pytest.fixture(autouse=True)
def stub_live_conversion(monkeypatch):
    """Deterministic stand-ins for the live server's markdown endpoints, patched on
    github_issues because that is the namespace the callers resolve them in."""
    monkeypatch.setattr(
        github_issue_content,
        "convert_markdown_to_formats",
        lambda md, variant="rich": {
            "description_html": f"<p>{md.strip()}</p>",
            "description_json": {},
            "description_binary": None,
        },
    )
    monkeypatch.setattr(
        github_issue_content,
        "convert_html_to_markdown",
        lambda html: (html or "").replace("<p>", "").replace("</p>", "").strip(),
    )


@pytest.fixture
def env(db):
    owner = UserFactory()
    workspace = WorkspaceFactory(owner=owner)
    WorkspaceMemberFactory(workspace=workspace, member=owner, role=20)
    project = ProjectFactory(workspace=workspace)
    backlog = State.objects.create(project=project, name="Backlog", group="backlog", color="#111", sequence=1)
    done = State.objects.create(project=project, name="Done", group="completed", color="#222", sequence=2)
    github_sync = ProjectGithubSync.objects.create(
        project=project, repository_owner="acme", repository_name="widgets"
    )
    return {
        "project": project,
        "backlog": backlog,
        "done": done,
        "github_sync": github_sync,
        "workspace": workspace,
    }


@pytest.mark.unit
@pytest.mark.django_db
class TestGithubIssuePull:
    def test_open_issue_becomes_work_item_in_default_state(self, env):
        with patch("plane.utils.github_client.fetch_issues") as mock_fetch:
            mock_fetch.return_value = [gh_issue(1)]
            sync_github_issues_to_project(str(env["github_sync"].id))

        issue = Issue.objects.get(project=env["project"], external_source="github", external_id="1")
        assert issue.name == "GH issue 1"
        assert issue.description_html == "<p>from github</p>"
        # not merely "not completed": cancelled is a done group too, and asserting
        # only against "completed" is what let the default-state bug below survive.
        assert issue.state.group not in PLANE_DONE_GROUPS
        link = GithubIssueLink.objects.get(issue=issue)
        assert link.github_issue_number == 1
        assert link.github_state == "open"

    def test_open_issue_is_not_imported_as_done_when_the_default_state_is(self, env):
        """A project may nominate a done-group state as its default -- production
        does exactly this with "Cancelled". An open GitHub issue must still land in
        a not-done state, or the push path reads it back as done and closes the
        issue it just imported."""
        project = env["project"]
        cancelled = State.objects.create(
            project=project, name="Cancelled", group="cancelled", color="#333", sequence=3
        )
        project.default_state = cancelled
        project.save(update_fields=["default_state"])

        with patch("plane.utils.github_client.fetch_issues") as mock_fetch:
            mock_fetch.return_value = [gh_issue(11)]
            sync_github_issues_to_project(str(env["github_sync"].id))

        issue = Issue.objects.get(project=project, external_id="11")
        assert issue.state.group not in PLANE_DONE_GROUPS
        # the done default is ignored entirely, not merely nudged
        assert issue.state != cancelled
        assert issue.state.name == "Backlog"  # lowest-sequence not-done state

    def test_closed_issue_lands_in_completed_state(self, env):
        with patch("plane.utils.github_client.fetch_issues") as mock_fetch:
            mock_fetch.return_value = [gh_issue(2, state="closed")]
            sync_github_issues_to_project(str(env["github_sync"].id))

        issue = Issue.objects.get(project=env["project"], external_id="2")
        assert issue.state.group == "completed"

    def test_second_run_is_idempotent(self, env):
        with patch("plane.utils.github_client.fetch_issues") as mock_fetch:
            mock_fetch.return_value = [gh_issue(3)]
            sync_github_issues_to_project(str(env["github_sync"].id))
            sync_github_issues_to_project(str(env["github_sync"].id))

        assert Issue.objects.filter(project=env["project"], external_id="3").count() == 1
        assert GithubIssueLink.objects.filter(github_sync=env["github_sync"], github_issue_number=3).count() == 1

    def test_github_close_moves_linked_issue_to_completed(self, env):
        with patch("plane.utils.github_client.fetch_issues") as mock_fetch:
            mock_fetch.return_value = [gh_issue(4)]
            sync_github_issues_to_project(str(env["github_sync"].id))
            mock_fetch.return_value = [gh_issue(4, state="closed")]
            sync_github_issues_to_project(str(env["github_sync"].id))

        issue = Issue.objects.get(project=env["project"], external_id="4")
        assert issue.state.group == "completed"
        assert GithubIssueLink.objects.get(issue=issue).github_state == "closed"

    def test_cursor_and_status_are_updated(self, env):
        with patch("plane.utils.github_client.fetch_issues") as mock_fetch:
            mock_fetch.return_value = []
            sync_github_issues_to_project(str(env["github_sync"].id))

        env["github_sync"].refresh_from_db()
        assert env["github_sync"].issues_cursor_at is not None
        assert env["github_sync"].issue_sync_status.startswith("success")
        # the wiki sync owns its own field and must not be spoken for
        assert env["github_sync"].wiki_sync_status is None


@pytest.mark.unit
@pytest.mark.django_db
class TestGithubIssuePush:
    def make_linked_issue(self, env, github_state="open", plane_state=None):
        issue = Issue.objects.create(
            project=env["project"],
            name="linked",
            state=plane_state or env["backlog"],
            external_source="github",
            external_id="10",
        )
        link = GithubIssueLink.objects.create(
            github_sync=env["github_sync"],
            project=env["project"],
            issue=issue,
            github_issue_number=10,
            github_state=github_state,
        )
        return issue, link

    def test_completing_linked_issue_closes_github_issue(self, env):
        issue, link = self.make_linked_issue(env)
        issue.state = env["done"]
        issue.save(update_fields=["state"])

        with patch("plane.utils.github_client.close_issue") as mock_close:
            push_issue_state_to_github(str(issue.id))

        mock_close.assert_called_once_with("acme", "widgets", 10)
        link.refresh_from_db()
        assert link.github_state == "closed"

    def test_reopening_linked_issue_reopens_github_issue(self, env):
        issue, link = self.make_linked_issue(env, github_state="closed", plane_state=env["backlog"])

        with patch("plane.utils.github_client.reopen_issue") as mock_reopen:
            push_issue_state_to_github(str(issue.id))

        mock_reopen.assert_called_once_with("acme", "widgets", 10)
        link.refresh_from_db()
        assert link.github_state == "open"

    def test_agreeing_states_push_nothing(self, env):
        issue, _ = self.make_linked_issue(env, github_state="open", plane_state=env["backlog"])

        with (
            patch("plane.utils.github_client.close_issue") as mock_close,
            patch("plane.utils.github_client.reopen_issue") as mock_reopen,
        ):
            push_issue_state_to_github(str(issue.id))

        mock_close.assert_not_called()
        mock_reopen.assert_not_called()

    def test_unlinked_issue_pushes_nothing(self, env):
        issue = Issue.objects.create(project=env["project"], name="unlinked", state=env["done"])

        with (
            patch("plane.utils.github_client.close_issue") as mock_close,
            patch("plane.utils.github_client.reopen_issue") as mock_reopen,
        ):
            push_issue_state_to_github(str(issue.id))

        mock_close.assert_not_called()
        mock_reopen.assert_not_called()

    def test_pull_applied_close_makes_push_a_noop(self, env):
        """The loop-suppression contract: after the pull sync applies a GitHub-side
        close, the push task sees agreeing states and never calls gh."""
        issue, _ = self.make_linked_issue(env)

        with patch("plane.utils.github_client.fetch_issues") as mock_fetch:
            mock_fetch.return_value = [
                {**gh_issue(10, state="closed"), "title": "linked"},
            ]
            sync_github_issues_to_project(str(env["github_sync"].id))

        with (
            patch("plane.utils.github_client.close_issue") as mock_close,
            patch("plane.utils.github_client.reopen_issue") as mock_reopen,
        ):
            push_issue_state_to_github(str(issue.id))

        mock_close.assert_not_called()
        mock_reopen.assert_not_called()


@pytest.mark.unit
@pytest.mark.django_db
class TestGithubSyncEndpoint:
    @pytest.fixture(autouse=True)
    def client(self, env):
        from rest_framework.test import APIClient

        from plane.db.models import ProjectMember

        owner = env["workspace"].owner
        ProjectMember.objects.get_or_create(
            project=env["project"], member=owner, defaults={"role": 20, "workspace": env["workspace"]}
        )
        api_client = APIClient()
        api_client.force_authenticate(user=owner)
        self.api = api_client
        self.url = f"/api/workspaces/{env['workspace'].slug}/projects/{env['project'].id}/github-sync/"

    def test_post_rejects_malformed_repository(self, env):
        response = self.api.post(self.url, {"repository": "not-a-repo"}, format="json")
        assert response.status_code == 400

    def test_post_connects_repository(self, env):
        env["github_sync"].delete(soft=False)
        response = self.api.post(self.url, {"repository": "octo/hello"}, format="json")
        assert response.status_code == 201
        assert response.data["repository"] == "octo/hello"

    def test_sync_now_enqueues(self, env):
        with patch("plane.app.views.project.github_sync.sync_github_issues_to_project") as mock_task:
            response = self.api.post(self.url + "sync-now/")
        assert response.status_code == 202
        mock_task.delay.assert_called_once_with(str(env["github_sync"].id))
