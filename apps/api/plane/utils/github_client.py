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
import threading
import time

from django.conf import settings

GH_TIMEOUT_SECONDS = 120
GITHUB_EXTERNAL_SOURCE = "github"

# GitHub asks for roughly a second between content-creating requests (its secondary
# limits are 80/minute and 500/hour). Enforced here because this module is the single
# place GitHub traffic passes through. Honest limitation: a Celery worker is one
# process, so this bounds one worker rather than the instance. With a handful of
# connected repos that is enough; the fix at real scale is a dedicated queue with
# concurrency=1, which is a config change, not a rewrite. Please don't reinvent a
# distributed limiter here.
MUTATION_MIN_INTERVAL = 1.0
_mutation_lock = threading.Lock()
_last_mutation_at = 0.0


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


def _throttle():
    """Space out mutating calls. See MUTATION_MIN_INTERVAL."""
    global _last_mutation_at
    with _mutation_lock:
        wait = MUTATION_MIN_INTERVAL - (time.monotonic() - _last_mutation_at)
        if wait > 0:
            time.sleep(wait)
        _last_mutation_at = time.monotonic()


def _run_gh_json(args, payload):
    """Send `payload` as a JSON document on stdin rather than as -f flags.

    Not a style preference. Four concrete reasons, in order of weight:

    1. run_gh puts its argv into the exception message, which is written to
       ProjectGithubSync.issue_sync_status and rendered in project settings. With
       `-f body=<the work item description>` any transient GitHub 500 would spill
       user-authored content into a status column and the logs.
    2. Linux caps a single argv entry at 128 KiB. GitHub allows a 65,536-character
       body, which in UTF-8 with CJK or emoji exceeds that -- so `-f` would fail with
       E2BIG only for the people who write long or non-Latin descriptions.
    3. gh interprets -f/-F values: a leading @ means "read this file", and booleans
       and integers get coerced. JSON is transported verbatim.
    4. Only JSON can omit a key, which is how update_issue patches the title without
       touching the body.
    """
    _throttle()
    return run_gh([*args, "--input", "-"], input_text=json.dumps(payload))


def fetch_issues(owner, repo, since=None):
    """All issues (open and closed, PRs excluded) of a repo, optionally updated since a cursor.

    Returns the parsed JSON list from the GitHub REST API. Each item carries the raw
    markdown `body`, deliberately not the rendered `body_html`: content sync compares
    the two systems by hashing, and hashing GitHub-rendered HTML against
    live-converted markdown would never agree, so markdown is the one interchange
    format in both directions.
    """
    args = [
        "api",
        f"repos/{owner}/{repo}/issues",
        "--paginate",
        "-X",
        "GET",
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


def fetch_issue(owner, repo, number):
    """One issue by number, for links stranded outside the `since` window."""
    return json.loads(run_gh(["api", f"repos/{owner}/{repo}/issues/{number}"]) or "{}")


def create_issue(owner, repo, title, body):
    """POST a new issue; returns its number."""
    out = _run_gh_json(
        ["api", f"repos/{owner}/{repo}/issues", "-X", "POST"],
        {"title": title, "body": body or ""},
    )
    return json.loads(out)["number"]


def update_issue(owner, repo, number, title=None, body=None):
    """PATCH title and/or body; returns GitHub's new updated_at, or None if nothing to send.

    The returned timestamp is GitHub's own clock, and the caller stores it. Stamping
    our clock instead would make the both-sides-changed tie-break wrong in a stable
    direction whenever the container drifts from GitHub.
    """
    payload = {k: v for k, v in (("title", title), ("body", body)) if v is not None}
    if not payload:
        return None
    out = _run_gh_json(["api", f"repos/{owner}/{repo}/issues/{number}", "-X", "PATCH"], payload)
    return json.loads(out).get("updated_at")


def close_issue(owner, repo, number):
    _throttle()
    run_gh(["api", f"repos/{owner}/{repo}/issues/{number}", "-X", "PATCH", "-f", "state=closed"])


def reopen_issue(owner, repo, number):
    _throttle()
    run_gh(["api", f"repos/{owner}/{repo}/issues/{number}", "-X", "PATCH", "-f", "state=open"])
