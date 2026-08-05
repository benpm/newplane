# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Unit tests for the legacy -> rich filter converter.

Saved views and older clients still send the flat legacy filter shape, and this
translates it into the rich filter tree the filterset understands. It is the
compatibility seam: dropping a value here silently widens a saved view, and
mistranslating an operator silently narrows one, neither of which surfaces as
an error to the user.
"""

import uuid

import pytest

from plane.utils.filters.converters import LegacyToRichFiltersConverter

UUID_A = str(uuid.uuid4())
UUID_B = str(uuid.uuid4())


@pytest.fixture
def converter():
    return LegacyToRichFiltersConverter()


@pytest.mark.unit
class TestConfiguration:
    def test_defaults_are_loaded(self, converter):
        assert converter.FIELD_MAPPINGS["state"] == "state_id"
        assert "assignee_id" in converter.UUID_FIELDS
        assert "urgent" in converter.VALID_CHOICES["priority"]
        assert "target_date" in converter.DATE_FIELDS

    def test_custom_config_extends_defaults_by_default(self):
        c = LegacyToRichFiltersConverter(field_mappings={"custom": "custom_id"})
        assert c.FIELD_MAPPINGS["custom"] == "custom_id"
        assert c.FIELD_MAPPINGS["state"] == "state_id"

    def test_extend_defaults_false_replaces_them(self):
        c = LegacyToRichFiltersConverter(field_mappings={"state": "status_id"}, extend_defaults=False)
        assert c.FIELD_MAPPINGS == {"state": "status_id"}
        assert c.UUID_FIELDS == set()
        assert c.VALID_CHOICES == {}
        assert c.DATE_FIELDS == set()

    def test_custom_choices_override_the_default_list(self):
        c = LegacyToRichFiltersConverter(valid_choices={"priority": ["critical"]})
        assert c.VALID_CHOICES["priority"] == ["critical"]

    def test_incremental_registration_helpers(self, converter):
        converter.add_field_mapping("epic", "epic_id")
        converter.add_uuid_field("epic_id")
        converter.add_choice_field("severity", ["sev1"])
        converter.add_date_field("shipped_at")

        assert converter.FIELD_MAPPINGS["epic"] == "epic_id"
        assert "epic_id" in converter.UUID_FIELDS
        assert converter.VALID_CHOICES["severity"] == ["sev1"]
        assert "shipped_at" in converter.DATE_FIELDS

    def test_update_mappings_applies_several_at_once(self, converter):
        converter.update_mappings(
            field_mappings={"epic": "epic_id"},
            uuid_fields={"epic_id"},
            valid_choices={"severity": ["sev1"]},
            date_fields={"shipped_at"},
        )
        assert converter.FIELD_MAPPINGS["epic"] == "epic_id"
        assert "epic_id" in converter.UUID_FIELDS


@pytest.mark.unit
class TestValueValidation:
    def test_uuid_fields_accept_only_uuids(self, converter):
        assert converter._validate_value("assignee_id", UUID_A) is True
        assert converter._validate_value("assignee_id", "not-a-uuid") is False

    def test_choice_fields_accept_only_known_choices(self, converter):
        assert converter._validate_value("priority", "urgent") is True
        assert converter._validate_value("priority", "spicy") is False

    def test_unconstrained_fields_accept_anything(self, converter):
        assert converter._validate_value("unmapped_field", "whatever") is True

    def test_invalid_values_are_dropped_from_a_list(self, converter):
        assert converter._filter_valid_values("assignee_id", [UUID_A, "bad"]) == [UUID_A]


@pytest.mark.unit
class TestConvert:
    def test_single_filter_returns_a_leaf_node(self, converter):
        assert converter.convert({"priority": "urgent"}) == {"priority__exact": "urgent"}

    def test_list_values_use_the_in_operator_joined_as_a_string(self, converter):
        # in/range values are flattened to a comma-separated string, which is
        # what the filterset parses on the other side.
        assert converter.convert({"priority": ["urgent", "high"]}) == {
            "priority__in": "urgent,high"
        }

    def test_multiple_filters_are_wrapped_in_and(self, converter):
        result = converter.convert({"priority": ["urgent"], "state_group": ["backlog"]})
        assert set(result) == {"and"}
        assert {"priority__in": "urgent"} in result["and"]
        assert {"state_group__in": "backlog"} in result["and"]

    def test_legacy_keys_are_renamed_to_rich_fields(self, converter):
        assert converter.convert({"assignees": [UUID_A]}) == {"assignee_id__in": UUID_A}

    def test_empty_input_produces_no_filters(self, converter):
        assert converter.convert({}) == {}

    def test_none_and_empty_list_values_are_skipped(self, converter):
        assert converter.convert({"priority": None, "labels": []}) == {}

    def test_unsupported_keys_are_ignored_when_lenient(self, converter):
        assert converter.convert({"not_a_filter": "x"}) == {}

    def test_invalid_values_are_dropped_when_lenient(self, converter):
        assert converter.convert({"assignees": [UUID_A, "bad"]}) == {"assignee_id__in": UUID_A}

    def test_a_wholly_invalid_list_yields_no_filter(self, converter):
        assert converter.convert({"assignees": ["bad"]}) == {}

    def test_invalid_single_value_yields_no_filter(self, converter):
        assert converter.convert({"priority": "spicy"}) == {}


@pytest.mark.unit
class TestStrictMode:
    """Strict mode is for callers that must not silently lose a constraint."""

    def test_unsupported_key_raises(self, converter):
        with pytest.raises(ValueError, match="Unsupported filter key"):
            converter.convert({"not_a_filter": "x"}, strict=True)

    def test_partially_invalid_list_raises(self, converter):
        with pytest.raises(ValueError, match="Invalid values"):
            converter.convert({"assignees": [UUID_A, "bad"]}, strict=True)

    def test_wholly_invalid_list_raises(self, converter):
        with pytest.raises(ValueError, match="No valid values"):
            converter.convert({"assignees": ["bad"]}, strict=True)

    def test_invalid_single_value_raises(self, converter):
        with pytest.raises(ValueError, match="Invalid value"):
            converter.convert({"priority": "spicy"}, strict=True)

    def test_valid_input_passes_strict_unchanged(self, converter):
        assert converter.convert({"priority": "urgent"}, strict=True) == {"priority__exact": "urgent"}


@pytest.mark.unit
class TestDateFields:
    def test_plain_date_becomes_an_exact_match(self, converter):
        assert converter.convert({"target_date": ["2026-01-01"]}) == {
            "target_date__exact": "2026-01-01"
        }

    def test_a_bounded_pair_becomes_a_range(self, converter):
        assert converter.convert({"target_date": ["2026-01-01;after", "2026-12-31;before"]}) == {
            "target_date__range": "2026-01-01,2026-12-31"
        }

    def test_a_half_open_bound_is_not_representable_and_is_dropped(self, converter):
        """The rich format has no one-sided date lookup, so a lone bound is skipped."""
        assert converter.convert({"target_date": ["2026-01-01;after"]}) == {}

    def test_relative_windows_are_skipped(self, converter):
        """Relative windows stay in the legacy path; the converter declines them."""
        assert converter.convert({"target_date": ["1_weeks;after;fromnow"]}) == {}

    def test_unparseable_date_is_dropped_when_lenient(self, converter):
        assert converter.convert({"target_date": ["not-a-date"]}) == {}


def _leaf_keys(rich_filter):
    """Flatten a rich filter tree down to its leaf lookup names."""
    if "and" in rich_filter:
        return [key for node in rich_filter["and"] for key in node]
    return list(rich_filter)
