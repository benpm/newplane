# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Bidirectional sync between a project's pages and its GitHub repository wiki.

The wiki is cloned fresh per run (stateless workers). Files are flat .md documents;
the page tree is encoded in a generated _Sidebar.md manifest. Conflicts resolve by
newest-timestamp-wins: GithubWikiPageLink records the content hash and moment of the
last sync, so each side's "changed since" is computable, and when both sides changed
the newer edit (wiki commit time vs page.updated_at) overwrites the older one.

Markdown conversion is delegated to the live server's /convert-markdown/ endpoint so
GFM handling stays single-sourced in the tested TypeScript pipeline.

Deletions deliberately do not propagate: a deleted page leaves its wiki file, a
deleted wiki file leaves its page.
"""

import base64
import hashlib
import shutil
import tempfile
from pathlib import Path

import requests
from celery import shared_task
from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from plane.utils.exception_logger import log_exception
from plane.utils.url import normalize_url_path


def _hash(markdown):
    return hashlib.sha256(markdown.encode("utf-8")).hexdigest()


def convert_markdown_to_page_formats(markdown):
    """markdown -> {description_html, description_json, description_binary(b64)} via live."""
    if not settings.LIVE_URL:
        return None
    url = normalize_url_path(f"{settings.LIVE_URL}/convert-markdown/")
    try:
        response = requests.post(url, json={"markdown": markdown, "variant": "document"}, timeout=60)
        if response.status_code == 200:
            return response.json()
    except requests.RequestException as e:
        log_exception(e)
    return None


def convert_html_to_markdown(description_html):
    """description_html -> markdown via live."""
    if not settings.LIVE_URL:
        return None
    url = normalize_url_path(f"{settings.LIVE_URL}/convert-markdown/")
    try:
        response = requests.post(url, json={"description_html": description_html or "<p></p>"}, timeout=60)
        if response.status_code == 200:
            return response.json().get("markdown")
    except requests.RequestException as e:
        log_exception(e)
    return None


def _apply_pull(page, markdown, link):
    """Write wiki content into a page. The binary is replaced too, so open editors
    reload the new document; if live returned nothing, fall back to clearing the
    binary and letting live rebuild it from HTML on next open."""
    formats = convert_markdown_to_page_formats(markdown)
    if formats is None:
        return False
    page.description_html = formats.get("description_html") or "<p></p>"
    page.description_json = formats.get("description_json") or {}
    binary = formats.get("description_binary")
    page.description_binary = base64.b64decode(binary) if binary else None
    page.save()
    link.wiki_content_hash = _hash(markdown)
    link.last_synced_at = timezone.now()  # after page.save(): page.updated_at <= last_synced_at
    link.save(update_fields=["wiki_content_hash", "last_synced_at"])
    return True


def _apply_push(page, wiki_dir, link):
    markdown = convert_html_to_markdown(page.description_html)
    if markdown is None:
        return False
    (Path(wiki_dir) / f"{link.wiki_slug}.md").write_text(markdown, encoding="utf-8")
    link.wiki_content_hash = _hash(markdown)
    link.last_synced_at = timezone.now()
    link.save(update_fields=["wiki_content_hash", "last_synced_at"])
    return True


def _wiki_file_commit_time(wiki_dir, filename):
    from plane.utils.github_wiki import run_git

    output = run_git(["log", "-1", "--format=%cI", "--", filename], cwd=wiki_dir).strip()
    return parse_datetime(output) if output else None


@shared_task
def schedule_github_wiki_syncs():
    from plane.db.models import ProjectGithubSync

    sync_ids = ProjectGithubSync.objects.filter(is_wiki_sync_enabled=True).values_list("id", flat=True)
    for sync_id in sync_ids:
        sync_github_wiki.delay(str(sync_id))


@shared_task
def sync_github_wiki(github_sync_id):
    from plane.db.models import GithubWikiPageLink, Page, ProjectGithubSync, ProjectPage
    from plane.utils.github_client import GithubClientError
    from plane.utils.github_wiki import (
        RESERVED_WIKI_FILES,
        generate_sidebar,
        parse_sidebar,
        run_git,
        slugify_page_name,
        title_from_slug,
        wiki_remote_url,
    )

    github_sync = ProjectGithubSync.objects.filter(pk=github_sync_id).first()
    if github_sync is None or not github_sync.is_wiki_sync_enabled:
        return

    project = github_sync.project
    wiki_dir = tempfile.mkdtemp(prefix="plane-wiki-")

    try:
        try:
            run_git(["clone", "--depth", "50", wiki_remote_url(github_sync), wiki_dir], cwd=tempfile.gettempdir())
        except GithubClientError as e:
            github_sync.last_sync_status = f"wiki error: {e}"[:255]
            github_sync.last_synced_at = timezone.now()
            github_sync.save(update_fields=["last_sync_status", "last_synced_at"])
            log_exception(e)
            return

        run_git(["config", "user.email", "sync@plane.local"], cwd=wiki_dir)
        run_git(["config", "user.name", "Plane Wiki Sync"], cwd=wiki_dir)

        wiki_root = Path(wiki_dir)
        wiki_files = {
            path.stem: path.read_text(encoding="utf-8", errors="replace")
            for path in wiki_root.glob("*.md")
            if path.name not in RESERVED_WIKI_FILES
        }
        sidebar_parents = parse_sidebar(
            (wiki_root / "_Sidebar.md").read_text(encoding="utf-8") if (wiki_root / "_Sidebar.md").exists() else ""
        )

        links = {link.wiki_slug: link for link in GithubWikiPageLink.objects.filter(github_sync=github_sync)}
        pages = list(
            Page.objects.filter(
                projects__id=project.id,
                access=0,
                archived_at__isnull=True,
                project_pages__deleted_at__isnull=True,
            ).distinct()
        )
        pages_by_id = {page.id: page for page in pages}
        linked_page_ids = {link.page_id for link in links.values()}
        pulled = pushed = created_pages = created_files = 0

        # --- linked pairs: decide direction ---------------------------------------
        for slug, link in links.items():
            page = pages_by_id.get(link.page_id)
            if page is None or slug not in wiki_files:
                continue  # deletion on either side: do not propagate
            markdown = wiki_files[slug]
            wiki_changed = _hash(markdown) != link.wiki_content_hash
            page_changed = link.last_synced_at is None or page.updated_at > link.last_synced_at

            direction = None
            if wiki_changed and not page_changed:
                direction = "pull"
            elif page_changed and not wiki_changed:
                direction = "push"
            elif wiki_changed and page_changed:
                commit_time = _wiki_file_commit_time(wiki_dir, f"{slug}.md")
                direction = "pull" if commit_time and commit_time > page.updated_at else "push"

            if direction == "pull" and _apply_pull(page, markdown, link):
                pulled += 1
            elif direction == "push" and _apply_push(page, wiki_dir, link):
                pushed += 1

        # --- unlinked wiki files -> new pages --------------------------------------
        owner = project.created_by or project.workspace.owner
        for slug, markdown in wiki_files.items():
            if slug in links:
                continue
            page = Page.objects.create(
                workspace=project.workspace,
                name=title_from_slug(slug),
                owned_by=owner,
                access=0,
            )
            ProjectPage.objects.create(workspace=project.workspace, project=project, page=page)
            link = GithubWikiPageLink.objects.create(
                github_sync=github_sync, project=project, page=page, wiki_slug=slug
            )
            if _apply_pull(page, markdown, link):
                created_pages += 1
            links[slug] = link
            pages_by_id[page.id] = page

        # --- unlinked pages -> new wiki files ---------------------------------------
        for page in pages:
            if page.id in linked_page_ids:
                continue
            slug = slugify_page_name(page.name, taken=set(links.keys()) | set(wiki_files.keys()))
            link = GithubWikiPageLink.objects.create(
                github_sync=github_sync, project=project, page=page, wiki_slug=slug
            )
            if _apply_push(page, wiki_dir, link):
                created_files += 1
            links[slug] = link

        # --- hierarchy: pulled pages follow the sidebar manifest ---------------------
        pages_by_slug = {slug: pages_by_id.get(link.page_id) for slug, link in links.items()}
        for slug, parent_slug in sidebar_parents.items():
            page = pages_by_slug.get(slug)
            if page is None:
                continue
            parent_page = pages_by_slug.get(parent_slug) if parent_slug else None
            parent_id = parent_page.id if parent_page else None
            if page.parent_id != parent_id and page.id != parent_id:
                page.parent_id = parent_id
                page.save(update_fields=["parent"])

        # --- regenerate the sidebar from the final page tree -------------------------
        slug_by_page_id = {link.page_id: slug for slug, link in links.items()}

        def subtree(parent_id):
            nodes = []
            children = sorted(
                (p for p in pages_by_id.values() if p.parent_id == parent_id and p.id in slug_by_page_id),
                key=lambda p: (p.name or "").lower(),
            )
            for child in children:
                nodes.append((slug_by_page_id[child.id], subtree(child.id)))
            return nodes

        roots = subtree(None) + [
            (slug_by_page_id[p.id], subtree(p.id))
            for p in sorted(pages_by_id.values(), key=lambda p: (p.name or "").lower())
            if p.id in slug_by_page_id and p.parent_id is not None and p.parent_id not in pages_by_id
        ]
        (wiki_root / "_Sidebar.md").write_text(generate_sidebar(roots), encoding="utf-8")

        # --- commit + push when anything changed -------------------------------------
        if run_git(["status", "--porcelain"], cwd=wiki_dir).strip():
            run_git(["add", "-A"], cwd=wiki_dir)
            run_git(["commit", "-m", "Sync from Plane"], cwd=wiki_dir)
            run_git(["push"], cwd=wiki_dir)

        github_sync.last_synced_at = timezone.now()
        github_sync.last_sync_status = (
            f"wiki success: {pulled} pulled, {pushed} pushed, {created_pages} pages, {created_files} files"
        )[:255]
        github_sync.save(update_fields=["last_synced_at", "last_sync_status"])
    except Exception as e:
        github_sync.last_sync_status = f"wiki error: {e}"[:255]
        github_sync.save(update_fields=["last_sync_status"])
        log_exception(e)
    finally:
        shutil.rmtree(wiki_dir, ignore_errors=True)
