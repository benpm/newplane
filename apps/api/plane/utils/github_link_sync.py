# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Cross-link conversion between Plane and GitHub.

Converts links in markdown descriptions between:
- Plane page links (e.g. /workspace/projects/pid/pages/page_id) <-> GitHub wiki / issue links
- Plane issue links (e.g. /workspace/projects/pid/issues/issue_id) <-> GitHub issue links
- Plane browse links (e.g. /browse/PROJ-123) <-> GitHub issue links

Ensures that when syncing between Plane and GitHub, there is no unintentional cross-linking:
- On GitHub, links point to GitHub issues and GitHub wiki pages.
- On Plane, links point to Plane work items and Plane wiki pages.
"""

import re
from plane.utils.github_wiki import slugify_page_name, title_from_slug

# Regex for Plane page links:
# Matches [Text](.../pages/<uuid>)
PLANE_PAGE_LINK_RE = re.compile(
    r"\[(?P<text>[^\]]*)\]\((?P<url>(?:https?://[^\s\)/]+)?(?:/[^\s\)/]+)*/pages/(?P<page_id>[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}|[0-9a-fA-F]{32})(?:[/?#][^)]*)?)\)"
)

# Regex for bare Plane page links:
PLANE_PAGE_BARE_RE = re.compile(
    r"(?<!\()https?://[^\s\)/]+(?:/[^\s\)/]+)*/pages/(?P<page_id>[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}|[0-9a-fA-F]{32})(?:[/?#][^\s\)]*)?"
)

# Regex for Plane issue links:
# Matches [Text](.../issues/<uuid>)
PLANE_ISSUE_LINK_RE = re.compile(
    r"\[(?P<text>[^\]]*)\]\((?P<url>(?:https?://[^\s\)/]+)?(?:/[^\s\)/]+)*/issues/(?P<issue_id>[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}|[0-9a-fA-F]{32})(?:[/?#][^)]*)?)\)"
)

# Regex for bare Plane issue links:
PLANE_ISSUE_BARE_RE = re.compile(
    r"(?<!\()https?://[^\s\)/]+(?:/[^\s\)/]+)*/issues/(?P<issue_id>[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}|[0-9a-fA-F]{32})(?:[/?#][^\s\)]*)?"
)

# Regex for Plane browse links:
# Matches [Text](.../browse/<identifier>-<seq>)
PLANE_BROWSE_LINK_RE = re.compile(
    r"\[(?P<text>[^\]]*)\]\((?P<url>(?:https?://[^\s\)/]+)?(?:/[^\s\)/]+)*/browse/(?P<identifier>[A-Za-z0-9_]+)-(?P<sequence_id>\d+)(?:[/?#][^)]*)?)\)"
)

# Regex for bare Plane browse links:
PLANE_BROWSE_BARE_RE = re.compile(
    r"(?<!\()https?://[^\s\)/]+(?:/[^\s\)/]+)*/browse/(?P<identifier>[A-Za-z0-9_]+)-(?P<sequence_id>\d+)(?:[/?#][^\s\)]*)?"
)


def transform_plane_links_to_github(markdown: str, github_sync, project=None) -> str:
    """Rewrite Plane page and issue links to native GitHub wiki / issue links."""
    if not markdown or not github_sync:
        return markdown

    from plane.db.models import GithubIssueLink, GithubWikiPageLink, Issue, Page

    owner = github_sync.repository_owner
    repo = github_sync.repository_name
    project = project or github_sync.project

    def replace_page_link(match):
        text = match.group("text") if "text" in match.groupdict() else None
        page_id = match.group("page_id")

        # 1. Check if page has a wiki link
        wiki_link = GithubWikiPageLink.objects.filter(github_sync=github_sync, page_id=page_id).first()
        if wiki_link:
            gh_url = f"https://github.com/{owner}/{repo}/wiki/{wiki_link.wiki_slug}"
            return f"[{text}]({gh_url})" if text is not None else gh_url

        # 2. Check if page exists
        page = Page.objects.filter(pk=page_id).first()
        if page:
            # Check if there is an issue with the same name that is synced
            issue_link = GithubIssueLink.objects.filter(
                github_sync=github_sync, issue__name=page.name
            ).first()
            if issue_link:
                gh_url = f"https://github.com/{owner}/{repo}/issues/{issue_link.github_issue_number}"
                return f"[{text}]({gh_url})" if text is not None else gh_url

            # Otherwise, use the wiki slug for this page
            slug = slugify_page_name(page.name, set())
            gh_url = f"https://github.com/{owner}/{repo}/wiki/{slug}"
            return f"[{text}]({gh_url})" if text is not None else gh_url

        return match.group(0)

    def replace_issue_link(match):
        text = match.group("text") if "text" in match.groupdict() else None
        issue_id = match.group("issue_id")

        issue_link = GithubIssueLink.objects.filter(github_sync=github_sync, issue_id=issue_id).first()
        if issue_link:
            gh_num = issue_link.github_issue_number
            gh_url = f"https://github.com/{owner}/{repo}/issues/{gh_num}"
            if text is None:
                return gh_url
            display_text = (
                f"#{gh_num}"
                if re.match(r"^(#\d+|[A-Za-z0-9_]+-\d+)$", text.strip())
                else text
            )
            return f"[{display_text}]({gh_url})"

        issue = Issue.objects.filter(pk=issue_id).first()
        if issue and issue.external_source == "github" and issue.external_id:
            gh_num = issue.external_id
            gh_url = f"https://github.com/{owner}/{repo}/issues/{gh_num}"
            if text is None:
                return gh_url
            display_text = (
                f"#{gh_num}"
                if re.match(r"^(#\d+|[A-Za-z0-9_]+-\d+)$", text.strip())
                else text
            )
            return f"[{display_text}]({gh_url})"

        return match.group(0)

    def replace_browse_link(match):
        text = match.group("text") if "text" in match.groupdict() else None
        identifier = match.group("identifier")
        seq_id = match.group("sequence_id")

        issue = Issue.objects.filter(project__identifier=identifier, sequence_id=seq_id).first()
        if issue:
            issue_link = GithubIssueLink.objects.filter(github_sync=github_sync, issue=issue).first()
            if issue_link:
                gh_num = issue_link.github_issue_number
                gh_url = f"https://github.com/{owner}/{repo}/issues/{gh_num}"
                if text is None:
                    return gh_url
                display_text = (
                    f"#{gh_num}"
                    if re.match(r"^(#\d+|[A-Za-z0-9_]+-\d+)$", text.strip())
                    else text
                )
                return f"[{display_text}]({gh_url})"
            elif issue.external_source == "github" and issue.external_id:
                gh_num = issue.external_id
                gh_url = f"https://github.com/{owner}/{repo}/issues/{gh_num}"
                if text is None:
                    return gh_url
                display_text = (
                    f"#{gh_num}"
                    if re.match(r"^(#\d+|[A-Za-z0-9_]+-\d+)$", text.strip())
                    else text
                )
                return f"[{display_text}]({gh_url})"

        return match.group(0)

    # 1. Replace markdown links [Text](URL)
    result = PLANE_PAGE_LINK_RE.sub(replace_page_link, markdown)
    result = PLANE_ISSUE_LINK_RE.sub(replace_issue_link, result)
    result = PLANE_BROWSE_LINK_RE.sub(replace_browse_link, result)

    # 2. Replace bare URLs
    result = PLANE_PAGE_BARE_RE.sub(replace_page_link, result)
    result = PLANE_ISSUE_BARE_RE.sub(replace_issue_link, result)
    result = PLANE_BROWSE_BARE_RE.sub(replace_browse_link, result)

    return result


def transform_github_links_to_plane(markdown: str, github_sync, project=None) -> str:
    """Rewrite GitHub issue and wiki links to native Plane work item and page links."""
    if not markdown or not github_sync:
        return markdown

    from plane.db.models import GithubIssueLink, GithubWikiPageLink, Issue, Page

    owner = re.escape(github_sync.repository_owner)
    repo = re.escape(github_sync.repository_name)
    project = project or github_sync.project
    workspace_slug = project.workspace.slug
    project_id = str(project.id)

    # Regex for GitHub wiki links:
    # https://github.com/owner/repo/wiki/<slug>
    GH_WIKI_LINK_RE = re.compile(
        rf"\[(?P<text>[^\]]*)\]\(https://github\.com/{owner}/{repo}/wiki/(?P<slug>[A-Za-z0-9._-]+)(?:[#?][^\s\)]*)?\)"
    )
    GH_WIKI_BARE_RE = re.compile(
        rf"(?<!\()https://github\.com/{owner}/{repo}/wiki/(?P<slug>[A-Za-z0-9._-]+)(?:[#?][^\s\)]*)?"
    )
    GH_WIKI_BRACKET_RE = re.compile(r"\[\[(?:(?P<text>[^\]|]+)\|)?(?P<slug>[^\]]+)\]\]")

    # Regex for GitHub issue links:
    # https://github.com/owner/repo/issues/<number>
    GH_ISSUE_LINK_RE = re.compile(
        rf"\[(?P<text>[^\]]*)\]\(https://github\.com/{owner}/{repo}/issues/(?P<number>\d+)(?:[#?][^\s\)]*)?\)"
    )
    GH_ISSUE_BARE_RE = re.compile(
        rf"(?<!\()https://github\.com/{owner}/{repo}/issues/(?P<number>\d+)(?:[#?][^\s\)]*)?"
    )

    def replace_gh_wiki(match):
        slug = match.group("slug").strip().replace(" ", "-")
        text = match.group("text") if "text" in match.groupdict() and match.group("text") else None

        wiki_link = GithubWikiPageLink.objects.filter(github_sync=github_sync, wiki_slug__iexact=slug).first()
        if wiki_link:
            plane_url = f"/{workspace_slug}/projects/{project_id}/pages/{wiki_link.page_id}"
            display_text = text or (wiki_link.page.name if wiki_link.page else None) or title_from_slug(slug)
            return f"[{display_text}]({plane_url})"

        # Check if page with matching name exists in project
        page = Page.objects.filter(projects=project, name__iexact=title_from_slug(slug)).first()
        if page:
            plane_url = f"/{workspace_slug}/projects/{project_id}/pages/{page.id}"
            display_text = text or page.name
            return f"[{display_text}]({plane_url})"

        return match.group(0)

    def replace_gh_issue(match):
        text = match.group("text") if "text" in match.groupdict() and match.group("text") else None
        number = int(match.group("number"))

        issue_link = (
            GithubIssueLink.objects.filter(github_sync=github_sync, github_issue_number=number)
            .select_related("issue")
            .first()
        )

        if issue_link:
            plane_issue = issue_link.issue
            plane_url = f"/{workspace_slug}/projects/{project_id}/issues/{plane_issue.id}"
            display_text = (
                f"#{plane_issue.sequence_id}"
                if (text and re.match(r"^#\d+$", text.strip()))
                else (text or f"#{plane_issue.sequence_id}")
            )
            return f"[{display_text}]({plane_url})"

        issue = Issue.objects.filter(project=project, external_source="github", external_id=str(number)).first()
        if issue:
            plane_url = f"/{workspace_slug}/projects/{project_id}/issues/{issue.id}"
            display_text = (
                f"#{issue.sequence_id}"
                if (text and re.match(r"^#\d+$", text.strip()))
                else (text or f"#{issue.sequence_id}")
            )
            return f"[{display_text}]({plane_url})"

        return match.group(0)

    result = GH_WIKI_LINK_RE.sub(replace_gh_wiki, markdown)
    result = GH_WIKI_BRACKET_RE.sub(replace_gh_wiki, result)
    result = GH_WIKI_BARE_RE.sub(replace_gh_wiki, result)
    result = GH_ISSUE_LINK_RE.sub(replace_gh_issue, result)
    result = GH_ISSUE_BARE_RE.sub(replace_gh_issue, result)

    return result
