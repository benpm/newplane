# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Unit tests for the issue query-parameter filter builders.

These turn request query parameters into ORM lookup kwargs. Every builder has
two shapes — a comma-joined string on GET and an already-parsed list on other
methods — plus "null" sentinels the frontend sends for "no value". Getting any
of that wrong silently widens or narrows what a user sees, so the branches are
covered explicitly rather than through the endpoints.
"""

import uuid
from datetime import timedelta

import pytest
from django.utils import timezone

from plane.utils.issue_filters import (
    date_filter,
    filter_assignees,
    filter_created_by,
    filter_issue_state_type,
    filter_name,
    filter_priority,
    filter_start_target_date_issues,
    filter_state,
    filter_state_group,
    filter_sub_issue_toggle,
    filter_valid_uuids,
    issue_filters,
    string_date_filter,
)

UUID_A = "0f9b2b7e-4a1e-4f0a-9f5a-1c2d3e4f5a6b"
UUID_B = "1a2b3c4d-5e6f-4a1b-8c9d-0e1f2a3b4c5d"


@pytest.mark.unit
class TestFilterValidUuids:
    def test_keeps_only_parseable_uuids(self):
        assert filter_valid_uuids([UUID_A, "not-a-uuid", UUID_B]) == [
            uuid.UUID(UUID_A),
            uuid.UUID(UUID_B),
        ]

    def test_empty_and_all_invalid_yield_empty(self):
        assert filter_valid_uuids([]) == []
        assert filter_valid_uuids(["", "null", "12345"]) == []


@pytest.mark.unit
class TestStringDateFilter:
    """"2_weeks;after;fromnow" style relative windows."""

    @pytest.mark.parametrize(
        "term,subsequent,offset,expected_key,expected_delta",
        [
            ("weeks", "after", "fromnow", "target_date__gte", timedelta(weeks=2)),
            ("weeks", "after", "past", "target_date__gte", -timedelta(weeks=2)),
            ("weeks", "before", "fromnow", "target_date__lte", timedelta(weeks=2)),
            ("weeks", "before", "past", "target_date__lte", -timedelta(weeks=2)),
            ("months", "after", "fromnow", "target_date__gte", timedelta(days=60)),
            ("months", "after", "past", "target_date__gte", -timedelta(days=60)),
            ("months", "before", "fromnow", "target_date__lte", timedelta(days=60)),
            ("months", "before", "past", "target_date__lte", -timedelta(days=60)),
        ],
    )
    def test_direction_and_offset_combinations(
        self, term, subsequent, offset, expected_key, expected_delta
    ):
        issue_filter = {}
        string_date_filter(
            issue_filter=issue_filter,
            duration=2,
            subsequent=subsequent,
            term=term,
            date_filter="target_date",
            offset=offset,
        )
        assert issue_filter == {expected_key: timezone.now().date() + expected_delta}

    def test_unknown_term_sets_nothing(self):
        issue_filter = {}
        string_date_filter(
            issue_filter=issue_filter,
            duration=2,
            subsequent="after",
            term="days",
            date_filter="target_date",
            offset="fromnow",
        )
        assert issue_filter == {}


@pytest.mark.unit
class TestDateFilter:
    def test_relative_window_requires_all_three_parts(self):
        issue_filter = {}
        date_filter(issue_filter, "target_date", ["1_weeks;after;fromnow"])
        assert issue_filter == {"target_date__gte": timezone.now().date() + timedelta(weeks=1)}

    def test_relative_window_with_two_parts_is_ignored(self):
        """The pattern matches but the offset is missing, so nothing is applied."""
        issue_filter = {}
        date_filter(issue_filter, "target_date", ["1_weeks;after"])
        assert issue_filter == {}

    def test_absolute_after_and_before(self):
        after = {}
        date_filter(after, "target_date", ["2026-01-01;after"])
        assert after == {"target_date__gte": "2026-01-01"}

        before = {}
        date_filter(before, "target_date", ["2026-01-01;before"])
        assert before == {"target_date__lte": "2026-01-01"}

    def test_bare_date_becomes_a_contains_lookup(self):
        issue_filter = {}
        date_filter(issue_filter, "target_date", ["2026-01-01"])
        assert issue_filter == {"target_date__contains": "2026-01-01"}


@pytest.mark.unit
class TestValueFilters:
    def test_state_get_drops_null_and_invalid_uuids(self):
        issue_filter = filter_state({"state": f"{UUID_A},null,bogus"}, {}, "GET")
        assert issue_filter == {"state__in": [uuid.UUID(UUID_A)]}

    def test_state_get_with_only_null_sets_nothing(self):
        assert filter_state({"state": "null"}, {}, "GET") == {}

    def test_state_post_passes_the_list_through(self):
        assert filter_state({"state": [UUID_A]}, {}, "POST") == {"state__in": [UUID_A]}

    def test_state_post_ignores_the_null_sentinel(self):
        assert filter_state({"state": "null"}, {}, "POST") == {}

    def test_prefix_is_applied_to_the_lookup(self):
        issue_filter = filter_state({"state": UUID_A}, {}, "GET", prefix="issue__")
        assert issue_filter == {"issue__state__in": [uuid.UUID(UUID_A)]}

    def test_state_group_is_not_uuid_validated(self):
        assert filter_state_group({"state_group": "backlog,started"}, {}, "GET") == {
            "state__group__in": ["backlog", "started"]
        }

    def test_priority_get_and_post(self):
        assert filter_priority({"priority": "urgent,high"}, {}, "GET") == {
            "priority__in": ["urgent", "high"]
        }
        assert filter_priority({"priority": ["low"]}, {}, "POST") == {"priority__in": ["low"]}

    def test_assignees_validates_uuids_and_excludes_removed_assignments(self):
        # The soft-delete guard is unconditional: filtering by assignee must not
        # match rows whose assignment was removed.
        assert filter_assignees({"assignees": f"{UUID_A},nope"}, {}, "GET") == {
            "assignees__in": [uuid.UUID(UUID_A)],
            "issue_assignee__deleted_at__isnull": True,
        }

    def test_assignees_none_sentinel_means_unassigned(self):
        assert filter_assignees({"assignees": "None"}, {}, "GET") == {
            "assignees__isnull": True,
            "issue_assignee__deleted_at__isnull": True,
        }

    def test_created_by_validates_uuids(self):
        assert filter_created_by({"created_by": f"{UUID_B},nope"}, {}, "GET") == {
            "created_by__in": [uuid.UUID(UUID_B)]
        }

    def test_name_uses_a_case_insensitive_contains(self):
        assert filter_name({"name": "login bug"}, {}, "GET") == {"name__icontains": "login bug"}


@pytest.mark.unit
class TestToggleFilters:
    @pytest.mark.parametrize("method", ["GET", "POST"])
    def test_sub_issue_false_excludes_children(self, method):
        assert filter_sub_issue_toggle({"sub_issue": "false"}, {}, method) == {
            "parent__isnull": True
        }

    @pytest.mark.parametrize("method", ["GET", "POST"])
    def test_sub_issue_true_leaves_children_in(self, method):
        assert filter_sub_issue_toggle({"sub_issue": "true"}, {}, method) == {}

    def test_start_target_date_true_requires_both_dates(self):
        assert filter_start_target_date_issues({"start_target_date": "true"}, {}, "GET") == {
            "target_date__isnull": False,
            "start_date__isnull": False,
        }

    def test_start_target_date_false_sets_nothing(self):
        assert filter_start_target_date_issues({"start_target_date": "false"}, {}, "GET") == {}

    @pytest.mark.parametrize(
        "type_value,expected",
        [
            ("backlog", ["backlog"]),
            ("active", ["unstarted", "started"]),
            ("all", ["backlog", "unstarted", "started", "completed", "cancelled"]),
        ],
    )
    def test_state_type_groups(self, type_value, expected):
        assert filter_issue_state_type({"type": type_value}, {}, "GET") == {
            "state__group__in": expected
        }


@pytest.mark.unit
class TestIssueFiltersDispatcher:
    def test_only_supplied_keys_are_applied(self):
        result = issue_filters({"priority": "urgent", "sub_issue": "false"}, "GET")
        assert result == {"priority__in": ["urgent"], "parent__isnull": True}

    def test_unknown_keys_are_ignored(self):
        assert issue_filters({"not_a_filter": "x"}, "GET") == {}

    def test_no_params_produces_no_filters(self):
        assert issue_filters({}, "GET") == {}

    def test_prefix_reaches_every_builder(self):
        result = issue_filters({"priority": "urgent", "state_group": "backlog"}, "GET", prefix="issue__")
        assert result == {
            "issue__priority__in": ["urgent"],
            "issue__state__group__in": ["backlog"],
        }


@pytest.mark.unit
class TestRelationFilters:
    """The remaining builders share one shape, so sweep them uniformly.

    Each maps a comma-joined GET value onto an __in lookup and passes an
    already-parsed list straight through on other methods. Several also
    UUID-validate the values and add a soft-delete guard so a removed link
    cannot match, hence asserting on the key rather than the coerced value.
    """

    # (param name, builder name, primary lookup)
    CASES = [
        ("labels", "filter_labels", "labels__in"),
        ("mentions", "filter_mentions", "issue_mention__mention__id__in"),
        ("parent", "filter_parent", "parent__in"),
        ("project", "filter_project", "project__in"),
        ("cycle", "filter_cycle", "issue_cycle__cycle_id__in"),
        ("module", "filter_module", "issue_module__module_id__in"),
        ("subscriber", "filter_subscribed_issues", "issue_subscribers__subscriber_id__in"),
    ]

    @staticmethod
    def _builder(name):
        import plane.utils.issue_filters as module

        return getattr(module, name)

    @pytest.mark.parametrize("param,builder,lookup", CASES)
    def test_get_populates_the_primary_lookup(self, param, builder, lookup):
        result = self._builder(builder)({param: f"{UUID_A},{UUID_B}"}, {}, "GET")
        assert len(result[lookup]) == 2

    @pytest.mark.parametrize("param,builder,lookup", CASES)
    def test_get_drops_the_null_sentinel(self, param, builder, lookup):
        assert lookup not in self._builder(builder)({param: "null"}, {}, "GET")

    @pytest.mark.parametrize("param,builder,lookup", CASES)
    def test_non_get_passes_the_list_through(self, param, builder, lookup):
        result = self._builder(builder)({param: [UUID_A]}, {}, "POST")
        assert result[lookup] == [UUID_A]

    @pytest.mark.parametrize("param,builder,lookup", CASES)
    def test_prefix_reaches_the_primary_lookup(self, param, builder, lookup):
        result = self._builder(builder)({param: UUID_A}, {}, "GET", prefix="issue__")
        assert f"issue__{lookup}" in result

    @pytest.mark.parametrize(
        "param,builder,isnull_lookup",
        [
            ("labels", "filter_labels", "labels__isnull"),
            ("parent", "filter_parent", "parent__isnull"),
            ("cycle", "filter_cycle", "issue_cycle__cycle_id__isnull"),
            ("module", "filter_module", "issue_module__module_id__isnull"),
        ],
    )
    def test_none_sentinel_means_unlinked(self, param, builder, isnull_lookup):
        assert self._builder(builder)({param: "None"}, {}, "GET")[isnull_lookup] is True

    @pytest.mark.parametrize(
        "param,builder,lookup",
        [("intake_status", "filter_intake_status", "issue_intake__status__in")],
    )
    def test_plain_string_filters_are_not_uuid_validated(self, param, builder, lookup):
        result = self._builder(builder)({param: "pending,accepted"}, {}, "GET")
        assert result[lookup] == ["pending", "accepted"]


@pytest.mark.unit
class TestTimestampFilters:
    """created_at/updated_at/start_date/target_date share the date grammar."""

    # created_at/updated_at compare against the date part of a timestamp, so
    # they carry a __date suffix the plain date columns do not.
    @pytest.mark.parametrize(
        "param,builder,lookup",
        [
            ("created_at", "filter_created_at", "created_at__date"),
            ("updated_at", "filter_updated_at", "updated_at__date"),
            ("start_date", "filter_start_date", "start_date"),
            ("target_date", "filter_target_date", "target_date"),
        ],
    )
    def test_absolute_lower_bound(self, param, builder, lookup):
        import plane.utils.issue_filters as module

        result = getattr(module, builder)({param: "2026-01-01;after"}, {}, "GET")
        assert result.get(f"{lookup}__gte") == "2026-01-01"
