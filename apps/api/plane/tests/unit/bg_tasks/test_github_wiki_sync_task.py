# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""
GitHub wiki <-> Plane pages sync, exercised against a REAL local git repository:
a bare repo stands in for github.com/{owner}/{repo}.wiki.git via a monkeypatched
wiki_remote_url. The live-server markdown conversion is replaced with trivial
deterministic converters — real GFM conversion is covered by the round-trip vitest
suite in @plane/utils.
"""

import subprocess
from pathlib import Path

import pytest

from plane.bgtasks import github_wiki_sync_task
from plane.db.models import GithubWikiPageLink, Page, ProjectGithubSync, ProjectPage
from plane.tests.factories import ProjectFactory, UserFactory, WorkspaceFactory, WorkspaceMemberFactory


def git(args, cwd):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def seed_wiki(bare_path, work_path, files):
    """Populate the bare 'wiki' remote with the given {name: content} .md files."""
    git(["clone", str(bare_path), str(work_path)], cwd=bare_path.parent)
    git(["config", "user.email", "t@t"], cwd=work_path)
    git(["config", "user.name", "t"], cwd=work_path)
    for name, content in files.items():
        (work_path / name).write_text(content, encoding="utf-8")
    git(["add", "-A"], cwd=work_path)
    git(["commit", "-m", "seed"], cwd=work_path)
    git(["push", "origin", "HEAD"], cwd=work_path)


def read_remote(bare_path, tmp_path, name="checkout"):
    """Clone the bare repo and return {filename: content}."""
    out = tmp_path / name
    git(["clone", str(bare_path), str(out)], cwd=tmp_path)
    return {p.name: p.read_text(encoding="utf-8") for p in out.glob("*.md")}


@pytest.fixture
def env(db, tmp_path, monkeypatch):
    owner = UserFactory()
    workspace = WorkspaceFactory(owner=owner)
    WorkspaceMemberFactory(workspace=workspace, member=owner, role=20)
    project = ProjectFactory(workspace=workspace)
    github_sync = ProjectGithubSync.objects.create(
        project=project,
        repository_owner="acme",
        repository_name="widgets",
        is_wiki_sync_enabled=True,
    )

    bare = tmp_path / "wiki.git"
    bare.mkdir()
    git(["init", "--bare", str(bare)], cwd=tmp_path)
    seed = tmp_path / "seed"
    seed_wiki(bare, seed, {"Home.md": "initial home\n"})

    monkeypatch.setattr("plane.utils.github_wiki.wiki_remote_url", lambda _sync: str(bare))
    # Deterministic stand-ins for the live server conversion endpoints.
    monkeypatch.setattr(
        github_wiki_sync_task,
        "convert_markdown_to_formats",
        lambda md, variant="document": {
            "description_html": f"<p>{md.strip()}</p>",
            "description_json": {},
            "description_binary": None,
        },
    )
    monkeypatch.setattr(
        github_wiki_sync_task,
        "convert_html_to_markdown",
        lambda html: (html or "").replace("<p>", "").replace("</p>", "").strip() + "\n",
    )

    def make_page(name, html="<p>page body</p>", parent=None):
        page = Page.objects.create(
            workspace=workspace, name=name, owned_by=owner, access=0, description_html=html, parent=parent
        )
        ProjectPage.objects.create(workspace=workspace, project=project, page=page)
        return page

    return {
        "project": project,
        "github_sync": github_sync,
        "bare": bare,
        "tmp": tmp_path,
        "make_page": make_page,
    }


def run_sync(env):
    github_wiki_sync_task.sync_github_wiki(str(env["github_sync"].id))
    env["github_sync"].refresh_from_db()


@pytest.mark.unit
@pytest.mark.django_db
class TestGithubWikiSync:
    def test_wiki_file_becomes_page(self, env):
        run_sync(env)

        page = Page.objects.get(github_wiki_link__wiki_slug="Home")
        assert page.description_html == "<p>initial home</p>"
        assert page.projects.filter(id=env["project"].id).exists()
        assert env["github_sync"].wiki_sync_status.startswith("success")
        assert env["github_sync"].issue_sync_status is None

    def test_new_page_becomes_wiki_file_and_sidebar_regenerates(self, env):
        env["make_page"]("Release Notes")
        run_sync(env)

        remote = read_remote(env["bare"], env["tmp"], "check1")
        assert "Release-Notes.md" in remote
        assert remote["Release-Notes.md"].strip() == "page body"
        assert "[[Release-Notes]]" in remote["_Sidebar.md"]
        assert "[[Home]]" in remote["_Sidebar.md"]

    def test_new_pages_linking_each_other_get_wiki_links_in_one_run(self, env):
        # Pairing happens before any push, so a link to a page exported in the
        # same run resolves instead of degrading to plain text.
        target = env["make_page"]("Zeta Target")
        project = env["project"]
        url = f"/{project.workspace.slug}/projects/{project.id}/pages/{target.id}"
        env["make_page"]("Alpha Source", html=f"<p>see [target]({url})</p>")
        run_sync(env)

        remote = read_remote(env["bare"], env["tmp"], "check-links")
        assert remote["Alpha-Source.md"].strip() == "see [target](https://github.com/acme/widgets/wiki/Zeta-Target)"

    def test_second_run_without_changes_commits_nothing(self, env):
        run_sync(env)

        head_before = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=env["bare"], check=True, capture_output=True, text=True
        ).stdout
        run_sync(env)
        head_after = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=env["bare"], check=True, capture_output=True, text=True
        ).stdout
        assert head_before == head_after

    def test_wiki_edit_pulls_into_page(self, env):
        run_sync(env)
        edit = env["tmp"] / "edit1"
        seed_wiki(env["bare"], edit, {"Home.md": "edited on wiki\n"})

        run_sync(env)

        page = Page.objects.get(github_wiki_link__wiki_slug="Home")
        assert page.description_html == "<p>edited on wiki</p>"

    def test_page_edit_pushes_to_wiki(self, env):
        run_sync(env)
        page = Page.objects.get(github_wiki_link__wiki_slug="Home")
        page.description_html = "<p>edited in plane</p>"
        page.save()

        run_sync(env)

        remote = read_remote(env["bare"], env["tmp"], "check2")
        assert remote["Home.md"].strip() == "edited in plane"

    def test_both_changed_newer_side_wins(self, env):
        """The wiki edit lands first, then the Plane edit — Plane's is newer and wins."""
        run_sync(env)
        edit = env["tmp"] / "edit2"
        seed_wiki(env["bare"], edit, {"Home.md": "older wiki edit\n"})
        page = Page.objects.get(github_wiki_link__wiki_slug="Home")
        page.description_html = "<p>newer plane edit</p>"
        page.save()  # updated_at is now > the wiki commit time

        run_sync(env)

        remote = read_remote(env["bare"], env["tmp"], "check3")
        assert remote["Home.md"].strip() == "newer plane edit"
        page.refresh_from_db()
        assert page.description_html == "<p>newer plane edit</p>"

    def test_sidebar_hierarchy_applies_to_pulled_pages(self, env):
        edit = env["tmp"] / "edit3"
        seed_wiki(
            env["bare"],
            edit,
            {
                "Parent.md": "parent\n",
                "Child.md": "child\n",
                "_Sidebar.md": "- [[Home]]\n- [[Parent]]\n  - [[Child]]\n",
            },
        )

        run_sync(env)

        parent = Page.objects.get(github_wiki_link__wiki_slug="Parent")
        child = Page.objects.get(github_wiki_link__wiki_slug="Child")
        assert child.parent_id == parent.id

    def test_slug_collision_gets_suffix(self, env):
        env["make_page"]("Home")  # collides with the existing wiki Home

        run_sync(env)

        slugs = set(
            GithubWikiPageLink.objects.filter(github_sync=env["github_sync"]).values_list("wiki_slug", flat=True)
        )
        assert "Home" in slugs
        assert "Home-2" in slugs

    def test_unreachable_wiki_records_error(self, env, monkeypatch):
        monkeypatch.setattr("plane.utils.github_wiki.wiki_remote_url", lambda _s: str(env["tmp"] / "missing.git"))

        run_sync(env)

        assert env["github_sync"].wiki_sync_status.startswith("error")

    def test_sync_recovers_when_conversion_was_unavailable(self, env, monkeypatch):
        """Conversion failure rolls back bookkeeping and retries on the next run."""
        env["make_page"]("Stranded Page")

        # Conversion failure must not mark content as synchronized.
        monkeypatch.setattr(github_wiki_sync_task, "convert_html_to_markdown", lambda _html: None)
        run_sync(env)

        assert env["github_sync"].wiki_sync_status.startswith("error")
        assert not GithubWikiPageLink.objects.filter(wiki_slug="Stranded-Page").exists()
        assert "Stranded-Page.md" not in read_remote(env["bare"], env["tmp"], "down")

        # Conversion recovers: the next run must push it rather than skip it.
        monkeypatch.setattr(
            github_wiki_sync_task,
            "convert_html_to_markdown",
            lambda html: (html or "").replace("<p>", "").replace("</p>", "").strip() + "\n",
        )
        run_sync(env)

        remote = read_remote(env["bare"], env["tmp"], "recovered")
        assert "Stranded-Page.md" in remote
        assert remote["Stranded-Page.md"].strip() == "page body"
        link = GithubWikiPageLink.objects.get(wiki_slug="Stranded-Page")
        assert link.wiki_content_hash is not None

    def test_a_soft_deleted_link_does_not_block_relinking(self, env):
        """Uniqueness must be scoped to live rows.

        These links used a OneToOneField, whose unconditional UNIQUE(page_id)
        stayed occupied by soft-deleted rows — so unlinking a page made it
        impossible to ever link again, and clearing one needed a hard DELETE
        against the table.
        """
        page = env["make_page"]("Relinkable")
        run_sync(env)
        link = GithubWikiPageLink.objects.get(wiki_slug="Relinkable")

        link.delete()  # soft delete: the row survives with deleted_at set
        assert not GithubWikiPageLink.objects.filter(page=page).exists()

        # Re-linking the same page must succeed rather than raise IntegrityError.
        recreated = GithubWikiPageLink.objects.create(
            github_sync=env["github_sync"],
            project=env["project"],
            page=page,
            wiki_slug="Relinkable-again",
        )
        assert recreated.pk is not None
        assert GithubWikiPageLink.objects.filter(page=page).count() == 1

    def test_two_live_links_to_one_page_are_still_rejected(self, env):
        """The partial constraint must still enforce one live link per page."""
        from django.db import IntegrityError, transaction

        page = env["make_page"]("Only Once")
        run_sync(env)

        with pytest.raises(IntegrityError), transaction.atomic():
            GithubWikiPageLink.objects.create(
                github_sync=env["github_sync"],
                project=env["project"],
                page=page,
                wiki_slug="Only-Once-duplicate",
            )

    def test_wiki_side_deletion_removes_page(self, env):
        """A previously synced wiki deletion also deletes its Plane page."""
        env["make_page"]("Doomed Page")
        run_sync(env)
        link = GithubWikiPageLink.objects.get(wiki_slug="Doomed-Page")
        assert link.wiki_content_hash is not None

        # Delete the file on the wiki side, as a person would.
        work = env["tmp"] / "deleter"
        git(["clone", str(env["bare"]), str(work)], cwd=env["tmp"])
        git(["rm", "Doomed-Page.md"], cwd=work)
        git(["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-m", "remove"], cwd=work)
        git(["push"], cwd=work)

        run_sync(env)

        assert "Doomed-Page.md" not in read_remote(env["bare"], env["tmp"], "after-delete")

        assert not Page.objects.filter(pk=link.page_id).exists()

    def test_deleted_page_removes_wiki_file_without_reimport(self, env):
        run_sync(env)
        page = Page.objects.get(github_wiki_link__wiki_slug="Home")
        page.delete()
        run_sync(env)
        run_sync(env)
        assert "Home.md" not in read_remote(env["bare"], env["tmp"], "deleted-page")
        assert not Page.objects.filter(projects=env["project"]).exists()

    def test_force_sync_removes_unmatched_files_and_overwrites_content(self, env):
        run_sync(env)
        page = Page.objects.get(github_wiki_link__wiki_slug="Home")
        seed_wiki(
            env["bare"],
            env["tmp"] / "force-edit",
            {
                "Home.md": "remote changes\n",
                "Unmatched.md": "wiki only\n",
            },
        )
        env["make_page"]("New Page")
        github_wiki_sync_task.sync_github_wiki(str(env["github_sync"].id), force=True)
        remote = read_remote(env["bare"], env["tmp"], "forced")
        assert remote["Home.md"] == "initial home\n"
        assert remote["New-Page.md"] == "page body\n"
        assert "Unmatched.md" not in remote
        page.refresh_from_db()
        assert page.description_html == "<p>initial home</p>"
        assert not Page.objects.filter(name="Unmatched").exists()

    def test_failed_push_keeps_baseline_and_retries_plane_edit(self, env, monkeypatch):
        from plane.utils import github_wiki

        run_sync(env)
        link = GithubWikiPageLink.objects.get(wiki_slug="Home")
        baseline = link.wiki_content_hash
        page = link.page
        page.description_html = "<p>must retry</p>"
        page.save()
        real_git = github_wiki.run_git

        def fail_push(args, cwd):
            if args[0] == "push":
                raise RuntimeError("push unavailable")
            return real_git(args, cwd)

        monkeypatch.setattr(github_wiki, "run_git", fail_push)
        run_sync(env)
        link.refresh_from_db()
        assert link.wiki_content_hash == baseline
        assert env["github_sync"].wiki_sync_status.startswith("error")
        monkeypatch.setattr(github_wiki, "run_git", real_git)
        run_sync(env)
        assert read_remote(env["bare"], env["tmp"], "retried")["Home.md"] == "must retry\n"

    def test_force_sync_preserves_plane_hierarchy(self, env):
        parent = env["make_page"]("Parent")
        child = env["make_page"]("Child", parent=parent)
        run_sync(env)
        seed_wiki(env["bare"], env["tmp"] / "sidebar-edit", {"_Sidebar.md": "- [[Child]]\n- [[Parent]]\n"})
        github_wiki_sync_task.sync_github_wiki(str(env["github_sync"].id), force=True)
        child.refresh_from_db()
        assert child.parent_id == parent.id
        assert "  - [[Child]]" in read_remote(env["bare"], env["tmp"], "tree")["_Sidebar.md"]

    def test_force_sync_recreates_missing_linked_file(self, env):
        page = env["make_page"]("Missing")
        GithubWikiPageLink.objects.create(
            github_sync=env["github_sync"],
            project=env["project"],
            page=page,
            wiki_slug="Missing",
            wiki_content_hash="previous-content",
        )
        github_wiki_sync_task.sync_github_wiki(str(env["github_sync"].id), force=True)
        assert Page.objects.filter(pk=page.id).exists()
        assert read_remote(env["bare"], env["tmp"], "restored")["Missing.md"] == "page body\n"

    def test_never_transferred_link_retries_missing_file(self, env):
        page = env["make_page"]("Pending")
        GithubWikiPageLink.objects.create(
            github_sync=env["github_sync"],
            project=env["project"],
            page=page,
            wiki_slug="Pending",
        )
        run_sync(env)
        assert read_remote(env["bare"], env["tmp"], "pending")["Pending.md"] == "page body\n"

    @pytest.mark.parametrize("force", [False, True])
    def test_sync_now_queues_wiki_with_requested_direction(self, env, monkeypatch, force):
        from types import SimpleNamespace
        from unittest.mock import Mock
        from plane.app.views.project.github_sync import ProjectGithubSyncNowEndpoint

        wiki = Mock()
        issues = Mock()
        monkeypatch.setattr("plane.app.views.project.github_sync.sync_github_wiki.delay", wiki)
        monkeypatch.setattr("plane.app.views.project.github_sync.sync_github_issues_to_project.delay", issues)
        response = ProjectGithubSyncNowEndpoint.post.__wrapped__(
            ProjectGithubSyncNowEndpoint(),
            SimpleNamespace(data={"force_wiki": force}),
            env["project"].workspace.slug,
            env["project"].id,
        )
        assert response.status_code == 202
        wiki.assert_called_once_with(str(env["github_sync"].id), force=force)
        assert issues.call_count == (0 if force else 1)

    def test_sidebar_only_edit_pulls_hierarchy(self, env, monkeypatch):
        from datetime import timedelta
        from django.utils import timezone

        parent = env["make_page"]("Parent")
        child = env["make_page"]("Child")
        run_sync(env)
        seed_wiki(
            env["bare"],
            env["tmp"] / "move-child",
            {
                "_Sidebar.md": "- [[Parent]]\n  - [[Child]]\n- [[Home]]\n",
            },
        )
        # Git commit timestamps have one-second precision.
        monkeypatch.setattr(
            github_wiki_sync_task, "_wiki_file_commit_time", lambda *_: timezone.now() + timedelta(seconds=1)
        )
        run_sync(env)
        child.refresh_from_db()
        assert child.parent_id == parent.id
