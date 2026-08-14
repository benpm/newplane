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
        "convert_markdown_to_page_formats",
        lambda md: {"description_html": f"<p>{md.strip()}</p>", "description_json": {}, "description_binary": None},
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
        assert env["github_sync"].last_sync_status.startswith("wiki success")

    def test_new_page_becomes_wiki_file_and_sidebar_regenerates(self, env):
        env["make_page"]("Release Notes")
        run_sync(env)

        remote = read_remote(env["bare"], env["tmp"], "check1")
        assert "Release-Notes.md" in remote
        assert remote["Release-Notes.md"].strip() == "page body"
        assert "[[Release-Notes]]" in remote["_Sidebar.md"]
        assert "[[Home]]" in remote["_Sidebar.md"]

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

        slugs = set(GithubWikiPageLink.objects.filter(github_sync=env["github_sync"]).values_list("wiki_slug", flat=True))
        assert "Home" in slugs
        assert "Home-2" in slugs

    def test_unreachable_wiki_records_error(self, env, monkeypatch):
        monkeypatch.setattr("plane.utils.github_wiki.wiki_remote_url", lambda _s: str(env["tmp"] / "missing.git"))

        run_sync(env)

        assert env["github_sync"].last_sync_status.startswith("wiki error")

    def test_sync_recovers_when_conversion_was_unavailable(self, env, monkeypatch):
        """A push that could not convert must be retried, not read as a deletion.

        The link row is written before the first push, so if the live markdown
        service is unreachable the pairing is recorded with no file behind it.
        Treating the missing file as a wiki-side deletion stranded the page
        forever: the link exists, so the "unlinked pages" pass skips it on every
        later run, and the page could never reach the wiki.
        """
        env["make_page"]("Stranded Page")

        # First run with conversion down: the link is created, no file written.
        monkeypatch.setattr(github_wiki_sync_task, "convert_html_to_markdown", lambda _html: None)
        run_sync(env)

        link = GithubWikiPageLink.objects.get(wiki_slug="Stranded-Page")
        assert link.wiki_content_hash is None
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
        link.refresh_from_db()
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

    def test_wiki_side_deletion_is_still_not_propagated(self, env):
        """The recovery path must not resurrect a genuinely deleted wiki file.

        Only links that never transferred anything are retried; one that has a
        recorded content hash represents a real deletion on the wiki side.
        """
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
