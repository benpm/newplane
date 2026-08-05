# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Thin wrapper around the GitHub CLI (`gh`).

All GitHub traffic (issue sync, wiki sync) goes through this module so there is a
single choke point for authentication, timeouts and error handling. Authentication is
instance-wide: the GITHUB_PERSONAL_ACCESS_TOKEN environment variable is handed to `gh`
as GH_TOKEN per invocation — no `gh auth login` state is required in the container.
"""

import json
import os
import subprocess

from django.conf import settings

GH_TIMEOUT_SECONDS = 120
GITHUB_EXTERNAL_SOURCE = "github"

# GitHub returns rendered HTML bodies with this media type, which drops straight into
# Issue.description_html without a server-side markdown pipeline.
HTML_ACCEPT_HEADER = "Accept: application/vnd.github.html+json"


class GithubClientError(Exception):
    """A `gh` invocation failed (non-zero exit, timeout, or missing binary/token)."""


def _get_token():
    token = getattr(settings, "GITHUB_PERSONAL_ACCESS_TOKEN", None) or os.environ.get("GITHUB_PERSONAL_ACCESS_TOKEN")
    if not token:
        raise GithubClientError("GITHUB_PERSONAL_ACCESS_TOKEN is not configured")
    return token


def run_gh(args, input_text=None):
    """Run `gh` with the instance token and return stdout as text."""
    env = {**os.environ, "GH_TOKEN": _get_token(), "GH_PROMPT_DISABLED": "1", "NO_COLOR": "1"}
    try:
        result = subprocess.run(
            ["gh", *args],
            input=input_text,
            capture_output=True,
            text=True,
            env=env,
            timeout=GH_TIMEOUT_SECONDS,
        )
    except FileNotFoundError as e:
        raise GithubClientError("The `gh` CLI is not installed in this environment") from e
    except subprocess.TimeoutExpired as e:
        raise GithubClientError(f"`gh {' '.join(args)}` timed out after {GH_TIMEOUT_SECONDS}s") from e

    if result.returncode != 0:
        raise GithubClientError(f"`gh {' '.join(args)}` failed: {result.stderr.strip()[:500]}")
    return result.stdout


def fetch_issues(owner, repo, since=None):
    """All issues (open and closed, PRs excluded) of a repo, optionally updated since a cursor.

    Returns the parsed JSON list from the GitHub REST API, each item carrying `body_html`.
    """
    args = [
        "api",
        f"repos/{owner}/{repo}/issues",
        "--paginate",
        "-X",
        "GET",
        "-H",
        HTML_ACCEPT_HEADER,
        "-f",
        "state=all",
        "-f",
        "per_page=100",
        # --paginate concatenates JSON arrays; --slurp wraps them into one array of arrays
        "--slurp",
    ]
    if since:
        args += ["-f", f"since={since}"]

    pages = json.loads(run_gh(args) or "[]")
    issues = [item for page in pages for item in page]
    # The issues endpoint also returns pull requests; those carry a pull_request key.
    return [issue for issue in issues if "pull_request" not in issue]


def close_issue(owner, repo, number):
    run_gh(["api", f"repos/{owner}/{repo}/issues/{number}", "-X", "PATCH", "-f", "state=closed"])


def reopen_issue(owner, repo, number):
    run_gh(["api", f"repos/{owner}/{repo}/issues/{number}", "-X", "PATCH", "-f", "state=open"])
