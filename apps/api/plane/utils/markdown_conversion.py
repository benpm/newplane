# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Markdown conversion and normalisation shared by the GitHub syncs.

Markdown is the interchange format for everything that crosses between Plane and
GitHub -- wiki pages and, since content sync, work item descriptions. Conversion is
delegated to the live server's /convert-markdown/ endpoint so GFM handling stays
single-sourced in the tested TypeScript pipeline rather than being reimplemented
against a Python markdown library that would drift from it.

Deliberately not placed in plane/utils/markdown.py: that module holds a mistune
instance bound to the name `markdown`, which would shadow the parameter of the same
name here and leave readers unsure which engine is authoritative.

The normalisation helpers exist so hashes survive round trips. Two systems that
disagree about line endings or trailing whitespace will report a change on every
comparison forever, which for a newest-wins sync means an endless push/pull loop.
"""

import hashlib
import json

import requests
from django.conf import settings

from plane.utils.exception_logger import log_exception
from plane.utils.url import normalize_url_path

LIVE_CONVERSION_TIMEOUT = 60


def convert_markdown_to_formats(markdown, variant="document"):
    """markdown -> {description_html, description_json, description_binary(b64)} via live.

    `variant` selects the editor the binary is built for: "document" for pages,
    "rich" for work item descriptions. Passing the wrong one yields a binary the
    editor cannot open.
    """
    if not settings.LIVE_URL:
        return None
    url = normalize_url_path(f"{settings.LIVE_URL}/convert-markdown/")
    try:
        response = requests.post(
            url, json={"markdown": markdown, "variant": variant}, timeout=LIVE_CONVERSION_TIMEOUT
        )
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
        response = requests.post(
            url,
            json={"description_html": description_html or "<p></p>"},
            timeout=LIVE_CONVERSION_TIMEOUT,
        )
        if response.status_code == 200:
            return response.json().get("markdown")
    except requests.RequestException as e:
        log_exception(e)
    return None


def content_hash(text):
    """sha256 of a single string.

    Byte-identical to the hash the wiki sync has always used. It must stay that way:
    GithubWikiPageLink rows carry hashes computed by the old implementation, and
    changing the shape would make every existing page look changed and trigger a
    full resync under newest-wins. Callers needing to hash several fields together
    should compose their own canonical form and pass one string.
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def normalize_markdown(markdown):
    """Collapse the differences that are not edits.

    GitHub normalises line endings on its side, so without this any body authored
    on Windows hashes differently every run and reads as a permanent remote change.
    """
    if not markdown:
        return ""
    text = markdown.replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(line.rstrip() for line in text.split("\n")).strip("\n")


def normalize_title(title):
    """Trim, then truncate to what Plane can actually store.

    Issue.name is 255 characters and GitHub allows 256. Truncating on both sides of
    the comparison is what stops an over-long title becoming an unresolvable
    conflict that pushes and pulls forever.
    """
    return (title or "").strip()[:255]


def canonical_content(title, body_markdown):
    """The single string that represents an issue's content for hashing.

    JSON rather than concatenation because ("a\\n\\nb", "") and ("a", "b") must not
    collide -- an f-string joined on a blank line makes them identical.
    """
    return json.dumps([normalize_title(title), normalize_markdown(body_markdown)], ensure_ascii=False)
