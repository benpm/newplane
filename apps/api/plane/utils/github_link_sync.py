# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Cross-link conversion between Plane and GitHub.

Converts links in markdown between:
- Plane page links (…/pages/<uuid>) <-> GitHub wiki pages
- Plane work item links (…/issues/<uuid>, …/browse/PROJ-123) <-> GitHub issues

so that after a sync, links on GitHub point at GitHub and links on Plane point
at Plane. Rules:
- Only verified pairings are followed — a sync's issue/wiki link rows, or a work
  item imported from this repository. Destinations are never guessed from titles.
- Every lookup is scoped to the sync's workspace and project, so a link into
  another workspace is never resolved (or its title leaked to GitHub).
- An outbound Plane link with no GitHub counterpart becomes plain text: its
  label is kept, the Plane hyperlink is dropped.
- Code spans and fenced code blocks are left untouched, as is any link carrying
  a #fragment: headings and comment anchors have no equivalent on the other side.
"""

import re

from plane.utils.github_wiki import title_from_slug

_UUID = r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}|[0-9a-fA-F]{32}"
_PLANE_PATH = r"(?:https?://[^\s\)/]+)?(?:/[^\s\)/#?]+)*"
_BARE_PATH = r"(?<![\(\w/])https?://[^\s\)/]+(?:/[^\s\)/#?]+)*"
# Query strings are dropped; a fragment is captured so the link can be left alone.
_TAIL_LINK = r"/?(?:\?[^\s\)#]*)?(?P<fragment>#[^\s\)]*)?"
_TAIL_BARE = r"/?(?:\?[^\s\)#]*)?(?P<fragment>#[^\s\)]*)?"
_FENCE_RE = re.compile(r"^\s*(```|~~~)")
_INLINE_CODE_RE = re.compile(r"(`[^`\n]*`)")
_REF_TEXT_RE = re.compile(r"^(#\d+|[A-Za-z0-9_]+-\d+)$")


def _link_and_bare(target):
    """A `[text](url)` pattern and a bare-URL pattern for the same Plane target."""
    return (
        re.compile(rf"\[(?P<text>[^\]]*)\]\({_PLANE_PATH}/{target}{_TAIL_LINK}\)"),
        re.compile(rf"{_BARE_PATH}/{target}{_TAIL_BARE}"),
    )


PLANE_PAGE_RES = _link_and_bare(rf"pages/(?P<page_id>{_UUID})")
PLANE_ISSUE_RES = _link_and_bare(rf"(?:issues|work-items)/(?P<issue_id>{_UUID})")
PLANE_BROWSE_RES = _link_and_bare(r"browse/(?P<identifier>[A-Za-z0-9_]+)-(?P<sequence_id>\d+)")


def _outside_code(markdown, convert):
    """Apply `convert` to the prose of a markdown document, never inside code."""
    out, prose, fence = [], [], None

    def flush():
        if prose:
            text = "".join(prose)
            parts = _INLINE_CODE_RE.split(text)
            out.append("".join(p if i % 2 else convert(p) for i, p in enumerate(parts)))
            prose.clear()

    for line in markdown.splitlines(keepends=True):
        marker = _FENCE_RE.match(line)
        if fence is None and marker:
            flush()
            fence = marker.group(1)
            out.append(line)
        elif fence is not None:
            out.append(line)
            if line.strip().startswith(fence):
                fence = None
        else:
            prose.append(line)
    flush()
    return "".join(out)


def _text(match):
    return match.groupdict().get("text")


def _has_fragment(match):
    return bool(match.groupdict().get("fragment"))


def _render(match, url, ref):
    """A converted link; reference-style text ("#12", "PROJ-12") follows the target."""
    text = _text(match)
    if text is None:
        return url
    return f"[{ref if _REF_TEXT_RE.match(text.strip()) else text}]({url})"


def _plain(match, label):
    """The unresolved-link fallback: keep the words, drop the Plane hyperlink."""
    text = _text(match)
    return text if text is not None else label


def transform_plane_links_to_github(markdown: str, github_sync, project=None) -> str:
    """Rewrite Plane page and work item links to native GitHub wiki / issue links."""
    if not markdown or not github_sync:
        return markdown

    from plane.db.models import GithubIssueLink, GithubWikiPageLink, Issue, Page

    project = project or github_sync.project
    base = f"https://github.com/{github_sync.repository_owner}/{github_sync.repository_name}"

    def github_number(issue):
        link = GithubIssueLink.objects.filter(github_sync=github_sync, issue=issue).first()
        if link:
            return link.github_issue_number
        # Imported from this repository before link rows existed.
        if issue.project_id == project.id and issue.external_source == "github" and issue.external_id:
            return issue.external_id
        return None

    def replace_issue_ref(match, issue):
        if issue is None or _has_fragment(match):
            return match.group(0)
        number = github_number(issue)
        if number is None:
            return _plain(match, f"{issue.project.identifier}-{issue.sequence_id}")
        return _render(match, f"{base}/issues/{number}", f"#{number}")

    def replace_page(match):
        page = Page.objects.filter(pk=match.group("page_id"), workspace_id=project.workspace_id).first()
        if page is None or _has_fragment(match):
            return match.group(0)
        link = GithubWikiPageLink.objects.filter(github_sync=github_sync, page=page).first()
        if link is None:
            return _plain(match, page.name or "Untitled")
        url = f"{base}/wiki/{link.wiki_slug}"
        text = _text(match)
        return url if text is None else f"[{text}]({url})"

    def replace_issue(match):
        issue = (
            Issue.objects.filter(pk=match.group("issue_id"), workspace_id=project.workspace_id)
            .select_related("project")
            .first()
        )
        return replace_issue_ref(match, issue)

    def replace_browse(match):
        issue = (
            Issue.objects.filter(
                workspace_id=project.workspace_id,
                project__identifier__iexact=match.group("identifier"),
                sequence_id=match.group("sequence_id"),
            )
            .select_related("project")
            .first()
        )
        return replace_issue_ref(match, issue)

    def convert(text):
        for patterns, replace in (
            (PLANE_PAGE_RES, replace_page),
            (PLANE_ISSUE_RES, replace_issue),
            (PLANE_BROWSE_RES, replace_browse),
        ):
            for pattern in patterns:
                text = pattern.sub(replace, text)
        return text

    return _outside_code(markdown, convert)


def transform_github_links_to_plane(markdown: str, github_sync, project=None) -> str:
    """Rewrite GitHub issue and wiki links to native Plane work item and page links.

    Unresolved GitHub links are kept: they still lead somewhere meaningful.
    """
    if not markdown or not github_sync:
        return markdown

    from plane.db.models import GithubIssueLink, GithubWikiPageLink, Issue

    project = project or github_sync.project
    plane_base = f"/{project.workspace.slug}/projects/{project.id}"
    repo = rf"https://github\.com/{re.escape(github_sync.repository_owner)}/{re.escape(github_sync.repository_name)}"

    wiki_res = (
        re.compile(rf"\[(?P<text>[^\]]*)\]\({repo}/wiki/(?P<slug>[A-Za-z0-9._-]+){_TAIL_LINK}\)"),
        re.compile(r"\[\[(?:(?P<text>[^\]|]+)\|)?(?P<slug>[^\]|#]+)\]\]"),  # gollum [[Page]] / [[Text|Page]]
        re.compile(rf"(?<![\(\w/]){repo}/wiki/(?P<slug>[A-Za-z0-9._-]+){_TAIL_BARE}"),
    )
    issue_res = (
        re.compile(rf"\[(?P<text>[^\]]*)\]\({repo}/issues/(?P<number>\d+){_TAIL_LINK}\)"),
        re.compile(rf"(?<![\(\w/]){repo}/issues/(?P<number>\d+){_TAIL_BARE}"),
    )

    def replace_wiki(match):
        if _has_fragment(match):
            return match.group(0)
        slug = match.group("slug").strip().replace(" ", "-")
        link = (
            GithubWikiPageLink.objects.filter(github_sync=github_sync, wiki_slug__iexact=slug)
            .select_related("page")
            .first()
        )
        if link is None or link.page is None:
            return match.group(0)
        label = _text(match) or link.page.name or title_from_slug(slug)
        return f"[{label}]({plane_base}/pages/{link.page_id})"

    def replace_issue(match):
        if _has_fragment(match):
            return match.group(0)
        number = int(match.group("number"))
        link = (
            GithubIssueLink.objects.filter(github_sync=github_sync, github_issue_number=number)
            .select_related("issue")
            .first()
        )
        issue = link.issue if link else None
        if issue is None:
            issue = Issue.objects.filter(project=project, external_source="github", external_id=str(number)).first()
        if issue is None:
            return match.group(0)
        ref = f"{project.identifier}-{issue.sequence_id}"
        text = _text(match)
        display = text if text and not _REF_TEXT_RE.match(text.strip()) else ref
        return f"[{display}](/{project.workspace.slug}/browse/{ref}/)"

    def convert(text):
        for pattern in wiki_res:
            text = pattern.sub(replace_wiki, text)
        for pattern in issue_res:
            text = pattern.sub(replace_issue, text)
        return text

    return _outside_code(markdown, convert)
