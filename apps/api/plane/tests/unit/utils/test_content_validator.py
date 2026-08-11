# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Unit tests for user-content validation.

This is the boundary that stops stored XSS: rich-text descriptions arrive as
HTML from the editor and are sanitised before they are persisted and later
rendered on the app's own origin. The binary validator guards the collaborative
document blobs against the same content smuggled through a different field.
Both return tuples rather than raising, so a caller that ignores the flag would
silently store unsanitised input — worth pinning down precisely.
"""

import base64

import pytest

from plane.utils.content_validator import (
    MAX_SIZE,
    _compute_html_sanitization_diff,
    validate_binary_data,
    validate_html_content,
)


@pytest.mark.unit
class TestValidateBinaryData:
    def test_empty_input_is_accepted(self):
        assert validate_binary_data(None) == (True, None)
        assert validate_binary_data(b"") == (True, None)

    def test_valid_binary_passes(self):
        assert validate_binary_data(b"\x00\x01\x02\x03rest of document") == (True, None)

    def test_base64_string_is_decoded_before_checking(self):
        payload = base64.b64encode(b"\x00\x01\x02\x03some document body").decode()
        assert validate_binary_data(payload) == (True, None)

    def test_undecodable_base64_is_rejected(self):
        is_valid, error = validate_binary_data("not!valid!base64!")
        assert is_valid is False
        assert "base64" in error

    def test_too_short_to_be_a_document(self):
        is_valid, error = validate_binary_data(b"ab")
        assert is_valid is False
        assert "too short" in error

    def test_oversized_payload_is_rejected(self):
        is_valid, error = validate_binary_data(b"\x00" * (MAX_SIZE + 1))
        assert is_valid is False
        assert "maximum size" in error

    @pytest.mark.parametrize(
        "payload",
        [
            b"<html><body>hi</body></html>",
            b"<!DOCTYPE html><p>x</p>",
            b"<script>alert(1)</script>",
            b"click javascript:alert(1)",
            b"<iframe src=x></iframe>",
            b"data:text/html;base64,AAAA",
        ],
    )
    def test_markup_smuggled_into_a_binary_field_is_rejected(self, payload):
        is_valid, error = validate_binary_data(payload)
        assert is_valid is False
        assert "suspicious" in error

    def test_pattern_check_is_case_insensitive(self):
        is_valid, _ = validate_binary_data(b"<SCRIPT>alert(1)</SCRIPT>")
        assert is_valid is False

    def test_only_the_head_of_the_payload_is_scanned(self):
        """The scan is bounded, so markup past the window is not detected here."""
        payload = b"\x00\x01\x02\x03" + b"A" * 400 + b"<script>alert(1)</script>"
        assert validate_binary_data(payload) == (True, None)

    def test_undecodable_bytes_do_not_raise(self):
        assert validate_binary_data(b"\xff\xfe\xfd\xfc\x80\x81") == (True, None)


@pytest.mark.unit
class TestValidateHtmlContent:
    def test_empty_input_short_circuits(self):
        assert validate_html_content("") == (True, None, None)
        assert validate_html_content(None) == (True, None, None)

    def test_safe_markup_survives(self):
        is_valid, error, clean = validate_html_content("<p>hello <strong>world</strong></p>")
        assert (is_valid, error) == (True, None)
        assert "<strong>" in clean

    def test_script_tags_are_stripped(self):
        _, _, clean = validate_html_content("<p>ok</p><script>alert(1)</script>")
        assert "<script>" not in clean
        assert "<p>ok</p>" in clean

    def test_inline_event_handlers_are_stripped(self):
        _, _, clean = validate_html_content('<p onclick="steal()">text</p>')
        assert "onclick" not in clean

    def test_javascript_urls_are_not_kept_as_links(self):
        _, _, clean = validate_html_content('<a href="javascript:alert(1)">x</a>')
        assert "javascript:" not in clean

    def test_safe_protocols_survive(self):
        for url in ("https://example.com", "mailto:a@b.c", "tel:+15551234"):
            _, _, clean = validate_html_content(f'<a href="{url}">x</a>')
            assert url in clean

    def test_editor_components_are_allowed_through(self):
        """Custom editor nodes must not be stripped or documents lose content."""
        _, _, clean = validate_html_content('<mention-component id="1"></mention-component>')
        assert "mention-component" in clean

    def test_oversized_html_is_rejected(self):
        oversized = "a" * (MAX_SIZE + 1)
        is_valid, error, clean = validate_html_content(oversized)
        assert (is_valid, clean) == (False, None)
        assert "maximum size" in error

    def test_size_limit_counts_encoded_bytes_not_characters(self):
        """Multi-byte characters must count for their real weight."""
        # Each of these is 3 bytes in UTF-8, so this is over the limit despite
        # being under it by character count.
        payload = "中" * (MAX_SIZE // 2)
        is_valid, error, _ = validate_html_content(payload)
        assert is_valid is False
        assert "maximum size" in error


@pytest.mark.unit
class TestSanitizationDiff:
    def test_reports_tags_that_were_removed(self):
        diff = _compute_html_sanitization_diff("<p>a</p><script>x</script>", "<p>a</p>")
        assert diff["removed_tags"].get("script") == 1

    def test_reports_attributes_that_were_removed(self):
        diff = _compute_html_sanitization_diff('<p onclick="x">a</p>', "<p>a</p>")
        assert "onclick" in diff["removed_attributes"].get("p", [])

    def test_identical_input_and_output_reports_nothing(self):
        diff = _compute_html_sanitization_diff("<p>a</p>", "<p>a</p>")
        assert not diff.get("removed_tags")
        assert not diff.get("removed_attributes")

    def test_malformed_input_does_not_raise(self):
        assert isinstance(_compute_html_sanitization_diff("<p><<>", ""), dict)
