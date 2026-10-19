# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Checkbox extraction utilities for work item descriptions."""

import re

_CODE_BLOCK_RE = re.compile(r"<pre\b.*?</pre>", re.IGNORECASE | re.DOTALL)


def extract_checkbox_counts(html: str) -> tuple[int, int]:
    """Extract (total, completed) checkbox counts from an issue description HTML/markdown string.

    Returns:
        tuple[int, int]: (total_checkboxes, completed_checkboxes)
    """
    if not html:
        return 0, 0

    # Checkbox syntax quoted in a code block is an example, not a task.
    html = _CODE_BLOCK_RE.sub("", html)

    # 1. TipTap taskItem <li> tags:
    # <li data-type="taskItem" data-checked="true"> or <li class="..." data-checked="false" data-type="taskItem">
    task_items = re.findall(
        r"<li\b[^>]*(?:data-type=[\"']taskItem[\"']|data-checked=[\"'](?:true|false)[\"'])[^>]*>",
        html,
        re.IGNORECASE,
    )
    if task_items:
        total = len(task_items)
        completed = sum(
            1 for item in task_items if re.search(r"data-checked=[\"']true[\"']", item, re.IGNORECASE)
        )
        return total, completed

    # 2. Standalone checkbox input elements: <input type="checkbox" ...>
    inputs = re.findall(r"<input\b[^>]*type=[\"']checkbox[\"'][^>]*>", html, re.IGNORECASE)
    if inputs:
        total = len(inputs)
        completed = sum(1 for item in inputs if re.search(r"\bchecked\b", item, re.IGNORECASE))
        return total, completed

    # 3. Markdown checkboxes: - [ ] or - [x] / - [X]
    md_matches = re.findall(r"^[ \t]*[-*+][ \t]+\[([ xX])\]", html, re.MULTILINE)
    if md_matches:
        total = len(md_matches)
        completed = sum(1 for m in md_matches if m in ("x", "X"))
        return total, completed

    return 0, 0
