# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""How the `gh` wrapper talks to GitHub. No subprocess is ever spawned here."""

import json
from unittest.mock import patch

import pytest

from plane.utils import github_client


@pytest.fixture(autouse=True)
def no_throttle(monkeypatch):
    """The real one sleeps a second before every mutation."""
    monkeypatch.setattr(github_client, "_throttle", lambda: None)


@pytest.mark.unit
class TestCreateIssue:
    def test_the_payload_goes_on_stdin_not_in_argv(self):
        """Bodies are arbitrary user text. run_gh puts its argv into the exception
        message, which is written to a status column rendered in project settings --
        so `-f body=...` would spill work item descriptions into the UI and the logs
        on any transient GitHub error. It would also hit the 128 KiB argv limit for
        long or non-Latin descriptions."""
        with patch.object(github_client, "run_gh", return_value='{"number": 7}') as mock_run:
            number = github_client.create_issue("acme", "widgets", "a title", "a body")

        assert number == 7
        args, kwargs = mock_run.call_args
        assert args[0][-2:] == ["--input", "-"]
        assert json.loads(kwargs["input_text"]) == {"title": "a title", "body": "a body"}
        # nothing user-authored may appear as a command-line argument
        assert not any("a body" in part for part in args[0])

    def test_a_missing_body_becomes_an_empty_string(self):
        with patch.object(github_client, "run_gh", return_value='{"number": 1}') as mock_run:
            github_client.create_issue("acme", "widgets", "t", None)
        assert json.loads(mock_run.call_args.kwargs["input_text"])["body"] == ""


@pytest.mark.unit
class TestUpdateIssue:
    def test_only_the_given_fields_are_sent(self):
        """Omitting a key is how a title is patched without touching the body -- and
        only JSON can express that, which -f cannot."""
        with patch.object(github_client, "run_gh", return_value="{}") as mock_run:
            github_client.update_issue("acme", "widgets", 3, title="new title")

        assert json.loads(mock_run.call_args.kwargs["input_text"]) == {"title": "new title"}

    def test_it_returns_githubs_own_timestamp(self):
        """Stored as the tie-break for both-sides-changed. Using our clock instead
        would pick a stable wrong winner whenever the container drifts."""
        with patch.object(github_client, "run_gh", return_value='{"updated_at": "2026-01-01T00:00:00Z"}'):
            assert github_client.update_issue("a", "b", 1, body="x") == "2026-01-01T00:00:00Z"

    def test_nothing_to_patch_makes_no_call(self):
        with patch.object(github_client, "run_gh") as mock_run:
            assert github_client.update_issue("acme", "widgets", 3) is None
        mock_run.assert_not_called()


@pytest.mark.unit
class TestFetchIssues:
    def test_raw_markdown_is_requested_not_rendered_html(self):
        """Markdown is the interchange format in both directions; hashing
        GitHub-rendered HTML against live-converted markdown would never agree."""
        with patch.object(github_client, "run_gh", return_value="[[]]") as mock_run:
            github_client.fetch_issues("acme", "widgets")

        assert not any("html+json" in part for part in mock_run.call_args[0][0])

    def test_pull_requests_are_filtered_out(self):
        payload = json.dumps([[{"number": 1}, {"number": 2, "pull_request": {}}]])
        with patch.object(github_client, "run_gh", return_value=payload):
            issues = github_client.fetch_issues("acme", "widgets")

        assert [i["number"] for i in issues] == [1]
