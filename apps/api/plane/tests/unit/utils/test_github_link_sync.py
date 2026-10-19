# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Plane <-> GitHub link rewriting: verified pairings only, never a guess."""

import pytest

from plane.db.models import GithubIssueLink, GithubWikiPageLink, Page, ProjectGithubSync, ProjectPage
from plane.tests.factories import IssueFactory, ProjectFactory, UserFactory, WorkspaceFactory
from plane.utils.github_link_sync import transform_github_links_to_plane, transform_plane_links_to_github

GH = "https://github.com/acme/widgets"


def make_page(project, name):
    page = Page.objects.create(workspace=project.workspace, name=name, owned_by=project.workspace.owner, access=0)
    ProjectPage.objects.create(workspace=project.workspace, project=project, page=page)
    return page


@pytest.fixture
def env(db):
    workspace = WorkspaceFactory(owner=UserFactory(), slug="ws")
    project = ProjectFactory(workspace=workspace, identifier="WID")
    sync = ProjectGithubSync.objects.create(project=project, repository_owner="acme", repository_name="widgets")
    linked_issue = IssueFactory(project=project, name="Linked")
    GithubIssueLink.objects.create(project=project, github_sync=sync, issue=linked_issue, github_issue_number=7)
    wiki_page = make_page(project, "Design Notes")
    GithubWikiPageLink.objects.create(project=project, github_sync=sync, page=wiki_page, wiki_slug="Design-Notes")
    return {
        "project": project,
        "sync": sync,
        "linked_issue": linked_issue,
        "local_issue": IssueFactory(project=project, name="Local only"),
        "wiki_page": wiki_page,
        "local_page": make_page(project, "Private Draft"),
        "foreign_issue": IssueFactory(project=ProjectFactory(identifier="WID2"), name="Elsewhere"),
    }


def out(env, md):
    return transform_plane_links_to_github(md, env["sync"], env["project"])


def inbound(env, md):
    return transform_github_links_to_plane(md, env["sync"], env["project"])


@pytest.mark.unit
class TestPlaneToGithub:
    def test_linked_issue_by_uuid(self, env):
        issue = env["linked_issue"]
        md = f"see [details](/ws/projects/{env['project'].id}/issues/{issue.id})"
        assert out(env, md) == f"see [details]({GH}/issues/7)"

    def test_reference_text_follows_the_target(self, env):
        seq = env["linked_issue"].sequence_id
        assert out(env, f"[WID-{seq}](https://plane.example/ws/browse/WID-{seq}/)") == f"[#7]({GH}/issues/7)"

    def test_bare_browse_url(self, env):
        seq = env["linked_issue"].sequence_id
        assert out(env, f"blocked by https://plane.example/ws/browse/WID-{seq}/ today") == (
            f"blocked by {GH}/issues/7 today"
        )

    def test_wiki_linked_page(self, env):
        md = f"[notes](/ws/projects/{env['project'].id}/pages/{env['wiki_page'].id})"
        assert out(env, md) == f"[notes]({GH}/wiki/Design-Notes)"

    def test_unsynced_issue_becomes_plain_text(self, env):
        issue = env["local_issue"]
        md = f"[the local one](/ws/projects/{env['project'].id}/issues/{issue.id})"
        assert out(env, md) == "the local one"
        assert out(env, f"https://plane.example/ws/browse/WID-{issue.sequence_id}") == f"WID-{issue.sequence_id}"

    def test_unsynced_page_becomes_plain_text_not_a_guessed_wiki_url(self, env):
        page = env["local_page"]
        assert out(env, f"[draft](/ws/projects/{env['project'].id}/pages/{page.id})") == "draft"

    def test_other_workspace_is_never_resolved(self, env):
        foreign = env["foreign_issue"]
        md = f"[x](/other/projects/{foreign.project_id}/issues/{foreign.id})"
        assert out(env, md) == md

    def test_code_is_left_alone(self, env):
        url = f"/ws/projects/{env['project'].id}/issues/{env['linked_issue'].id}"
        md = f"`[a]({url})`\n```\n[b]({url})\n```\n"
        assert out(env, md) == md

    def test_fragment_links_are_kept(self, env):
        md = f"[h](/ws/projects/{env['project'].id}/pages/{env['wiki_page'].id}#heading)"
        assert out(env, md) == md

    def test_external_links_untouched(self, env):
        md = "[docs](https://example.com/issues/12) and https://github.com/other/repo/issues/3"
        assert out(env, md) == md


@pytest.mark.unit
class TestGithubToPlane:
    def test_linked_issue(self, env):
        seq = env["linked_issue"].sequence_id
        assert inbound(env, f"[#7]({GH}/issues/7)") == f"[WID-{seq}](/ws/browse/WID-{seq}/)"
        assert inbound(env, f"see {GH}/issues/7") == f"see [WID-{seq}](/ws/browse/WID-{seq}/)"

    def test_wiki_page(self, env):
        page = env["wiki_page"]
        expected = f"[Design Notes](/ws/projects/{env['project'].id}/pages/{page.id})"
        assert inbound(env, f"{GH}/wiki/Design-Notes") == expected
        assert inbound(env, "[[Design Notes]]") == expected

    def test_unresolved_github_links_are_kept(self, env):
        md = f"[#99]({GH}/issues/99) and {GH}/wiki/Unknown and [[Nope]]"
        assert inbound(env, md) == md

    def test_comment_anchor_is_kept(self, env):
        md = f"{GH}/issues/7#issuecomment-123"
        assert inbound(env, md) == md

    def test_round_trip_is_stable(self, env):
        seq = env["linked_issue"].sequence_id
        plane = f"[WID-{seq}](/ws/browse/WID-{seq}/) and [Design Notes](/ws/projects/{env['project'].id}/pages/{env['wiki_page'].id})"
        github = out(env, plane)
        assert inbound(env, github) == plane
        assert out(env, inbound(env, github)) == github
