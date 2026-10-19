# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import pytest

from plane.tests.factories import IssueFactory
from plane.utils.checkbox import extract_checkbox_counts


def task(checked, text="x"):
    state = "true" if checked else "false"
    return f'<li data-type="taskItem" data-checked="{state}"><p>{text}</p></li>'


@pytest.mark.unit
class TestExtractCheckboxCounts:
    @pytest.mark.parametrize("html", [None, "", "<p></p>", "<ul><li>plain</li></ul>"])
    def test_no_checkboxes(self, html):
        assert extract_checkbox_counts(html) == (0, 0)

    def test_editor_task_list(self):
        html = f'<ul data-type="taskList">{task(True)}{task(False)}{task(False)}</ul>'
        assert extract_checkbox_counts(html) == (3, 1)

    def test_nested_items_count_once_each(self):
        inner = f'<ul data-type="taskList">{task(True)}</ul>'
        html = f'<ul data-type="taskList"><li data-type="taskItem" data-checked="false"><p>a</p>{inner}</li></ul>'
        assert extract_checkbox_counts(html) == (2, 1)

    def test_all_completed(self):
        assert extract_checkbox_counts(task(True) + task(True)) == (2, 2)

    def test_imported_checkbox_inputs(self):
        html = '<input type="checkbox" checked><input type="checkbox"><input type="text">'
        assert extract_checkbox_counts(html) == (2, 1)

    def test_markdown_checkboxes(self):
        assert extract_checkbox_counts("- [x] done\n- [ ] todo\n* [X] also") == (3, 2)

    def test_code_examples_are_ignored(self):
        html = f"<pre><code>- [ ] not a task\n{task(True)}</code></pre>{task(False)}"
        assert extract_checkbox_counts(html) == (1, 0)


@pytest.mark.unit
@pytest.mark.django_db
def test_issue_save_keeps_counts_current():
    issue = IssueFactory(description_html=task(True) + task(False))
    assert (issue.checkbox_total, issue.checkbox_completed) == (2, 1)

    issue.description_html = task(True) + task(True)
    issue.save(update_fields=["description_html"])
    issue.refresh_from_db()
    assert (issue.checkbox_total, issue.checkbox_completed) == (2, 2)
