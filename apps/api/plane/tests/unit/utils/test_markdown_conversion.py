# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Normalisation guards for the GitHub content hash.

Each of these protects against a specific way a hash-based bidirectional sync can
wedge itself: a difference that is not an edit reads as one on every run, so the
two sides push and pull at each other forever without ever converging.
"""

import hashlib

import pytest

from plane.utils.markdown_conversion import (
    canonical_content,
    content_hash,
    normalize_markdown,
    normalize_title,
)


@pytest.mark.unit
class TestContentHash:
    def test_hash_is_a_plain_sha256_of_the_string(self):
        """GithubWikiPageLink rows hold hashes written by the original
        implementation. If this ever stops matching, every existing wiki page looks
        changed at once and resyncs under newest-wins."""
        assert content_hash("hello") == hashlib.sha256(b"hello").hexdigest()


@pytest.mark.unit
class TestNormalisation:
    @pytest.mark.parametrize(
        "a,b",
        [
            ("line one\r\nline two", "line one\nline two"),  # CRLF from a Windows author
            ("line one\rline two", "line one\nline two"),  # bare CR
            ("trailing   \nspace  ", "trailing\nspace"),  # per-line trailing whitespace
            ("\n\nbody\n\n", "body"),  # leading/trailing blank lines
        ],
    )
    def test_differences_that_are_not_edits_normalise_away(self, a, b):
        assert normalize_markdown(a) == normalize_markdown(b)

    def test_real_edits_still_differ(self):
        assert normalize_markdown("body") != normalize_markdown("body edited")

    def test_blank_input_is_the_empty_string(self):
        assert normalize_markdown(None) == ""
        assert normalize_markdown("") == ""

    def test_title_is_truncated_on_both_sides_of_the_comparison(self):
        """Issue.name stores 255 chars, GitHub allows 256. Without truncating here
        the stored title can never hash equal to the one we sent, and the conflict
        is unresolvable rather than merely wrong once."""
        long_title = "x" * 300
        assert normalize_title(long_title) == normalize_title(long_title[:255])
        assert len(normalize_title(long_title)) == 255

    def test_title_is_stripped(self):
        assert normalize_title("  spaced  ") == "spaced"
        assert normalize_title(None) == ""


@pytest.mark.unit
class TestCanonicalContent:
    def test_the_title_body_boundary_is_unambiguous(self):
        """Joining with a blank line would make these two identical, so a title edit
        could be silently cancelled out by a matching body edit."""
        assert canonical_content("a\n\nb", "") != canonical_content("a", "b")

    def test_equal_content_is_equal_regardless_of_line_endings(self):
        assert canonical_content("Title", "a\r\nb") == canonical_content("Title", "a\nb")

    def test_non_ascii_survives(self):
        assert "日本語" in canonical_content("日本語", "")
