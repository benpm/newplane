# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Git plumbing and file-layout helpers for GitHub wiki sync.

A GitHub wiki is a plain git repository at github.com/{owner}/{repo}.wiki.git holding
flat .md files. Page hierarchy is encoded in a generated _Sidebar.md manifest (a nested
list of [[slug]] links), which GitHub also renders as wiki navigation.
"""

import re
import subprocess

from plane.utils.github_client import GithubClientError, _get_token

GIT_TIMEOUT_SECONDS = 180
RESERVED_WIKI_FILES = {"_Sidebar.md", "_Footer.md", "_Header.md"}


def wiki_remote_url(github_sync):
    """Token-embedded clone URL. Factored out so tests can point it at a local bare repo."""
    token = _get_token()
    return f"https://x-access-token:{token}@github.com/{github_sync.repository_owner}/{github_sync.repository_name}.wiki.git"


def run_git(args, cwd):
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as e:
        raise GithubClientError(f"`git {' '.join(args)}` timed out") from e

    if result.returncode != 0:
        # Never leak the token embedded in remote URLs into logs or status fields.
        stderr = re.sub(r"x-access-token:[^@]+@", "x-access-token:***@", result.stderr.strip())
        raise GithubClientError(f"`git {args[0]}` failed: {stderr[:500]}")
    return result.stdout


def slugify_page_name(name, taken):
    """GitHub-wiki-safe file slug for a page name, unique against `taken` (a set)."""
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", (name or "Untitled").strip()).strip("-") or "Untitled"
    candidate = slug
    counter = 2
    while candidate.lower() in {t.lower() for t in taken}:
        candidate = f"{slug}-{counter}"
        counter += 1
    return candidate


def title_from_slug(slug):
    return slug.replace("-", " ").strip() or "Untitled"


def generate_sidebar(tree):
    """Render the page tree as a _Sidebar.md manifest.

    `tree` is a list of (slug, children) tuples, children in the same shape.
    """
    lines = []

    def walk(nodes, depth):
        for slug, children in nodes:
            lines.append(f"{'  ' * depth}- [[{slug}]]")
            walk(children, depth + 1)

    walk(tree, 0)
    return "\n".join(lines) + ("\n" if lines else "")


SIDEBAR_LINE = re.compile(r"^(?P<indent>\s*)-\s*\[\[(?P<slug>[^\]]+)\]\]\s*$")


def parse_sidebar(content):
    """Parse a _Sidebar.md manifest into {slug: parent_slug_or_None}.

    Tolerates hand edits: lines that don't match the list shape are ignored, and a
    malformed indent falls back to the nearest shallower ancestor.
    """
    parents = {}
    stack = []  # (indent_width, slug)
    for line in (content or "").splitlines():
        match = SIDEBAR_LINE.match(line)
        if not match:
            continue
        indent = len(match.group("indent").replace("\t", "  "))
        slug = match.group("slug").strip()
        while stack and stack[-1][0] >= indent:
            stack.pop()
        parents[slug] = stack[-1][1] if stack else None
        stack.append((indent, slug))
    return parents
