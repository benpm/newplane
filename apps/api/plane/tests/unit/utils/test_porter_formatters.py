# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Unit tests for the import/export porter formatters.

Unlike the one-way export formatters, these round-trip: data leaves as a file
and comes back through the same class on import. That makes the encode/decode
pair the real contract — pretty headers must normalise back to field names, and
nested structures must survive flattening and unflattening, or a re-import
quietly reshapes the caller's data.
"""

import csv
import io
import json

import pytest
from openpyxl import Workbook

from plane.utils.porters.formatters import (
    BaseFormatter,
    CSVFormatter,
    JSONFormatter,
    XLSXFormatter,
)

NESTED = [
    {"email": "a@plane.so", "display_name": "Ada", "profile": {"role": "admin"}, "tags": ["x", "y"]},
    {"email": "b@plane.so", "display_name": "Bob", "profile": {"role": "member"}, "tags": []},
]


@pytest.mark.unit
class TestBaseFormatter:
    def test_cannot_be_instantiated(self):
        with pytest.raises(TypeError):
            BaseFormatter()


@pytest.mark.unit
class TestJSONFormatter:
    def test_round_trip_preserves_structure(self):
        formatter = JSONFormatter()
        assert formatter.decode(formatter.encode(NESTED)) == NESTED

    def test_extension(self):
        assert JSONFormatter().extension == "json"

    def test_indent_is_configurable(self):
        assert "\n" in JSONFormatter(indent=2).encode(NESTED)
        assert "\n" not in JSONFormatter(indent=None).encode(NESTED)


@pytest.mark.unit
class TestCSVFormatter:
    def _rows(self, content):
        return list(csv.reader(io.StringIO(content)))

    def test_extension(self):
        assert CSVFormatter().extension == "csv"

    def test_no_rows_encodes_to_an_empty_string(self):
        assert CSVFormatter().encode([]) == ""

    def test_headers_are_prettified_by_default(self):
        content = CSVFormatter().encode(NESTED)
        assert self._rows(content)[0][:2] == ["Email", "Display Name"]

    def test_raw_headers_when_prettifying_is_off(self):
        content = CSVFormatter(prettify_headers=False).encode(NESTED)
        assert self._rows(content)[0][:2] == ["email", "display_name"]

    def test_nested_dicts_are_flattened_into_dunder_columns(self):
        content = CSVFormatter().encode(NESTED)
        assert "Profile  Role" in self._rows(content)[0] or "Profile Role" in self._rows(content)[0]

    def test_lists_are_stored_as_json(self):
        content = CSVFormatter().encode(NESTED)
        header, first = self._rows(content)[0], self._rows(content)[1]
        assert json.loads(first[header.index("Tags")]) == ["x", "y"]

    def test_delimiter_is_configurable(self):
        content = CSVFormatter(delimiter=";").encode(NESTED)
        assert ";" in content.splitlines()[0]

    def test_round_trip_restores_field_names_and_nesting(self):
        formatter = CSVFormatter()
        decoded = formatter.decode(formatter.encode(NESTED))
        assert decoded[0]["email"] == "a@plane.so"
        assert decoded[0]["profile"] == {"role": "admin"}
        assert decoded[0]["tags"] == ["x", "y"]

    def test_decode_can_keep_headers_verbatim(self):
        formatter = CSVFormatter(flatten=False)
        decoded = formatter.decode("Display Name\nAda\n", normalize_headers=False)
        assert decoded == [{"Display Name": "Ada"}]

    def test_rows_with_differing_keys_produce_a_union_of_columns(self):
        content = CSVFormatter(flatten=False).encode([{"a": 1}, {"b": 2}])
        assert self._rows(content)[0] == ["A", "B"]

    def test_missing_values_become_empty_cells(self):
        content = CSVFormatter(flatten=False).encode([{"a": 1}, {"b": 2}])
        assert self._rows(content)[1] == ["1", ""]

    def test_formula_injection_is_neutralised(self):
        content = CSVFormatter(flatten=False).encode([{"a": "=cmd()"}])
        assert not self._rows(content)[1][0].startswith("=")

    def test_formula_injection_is_neutralised_without_pretty_headers(self):
        content = CSVFormatter(flatten=False, prettify_headers=False).encode([{"a": "=cmd()"}])
        assert not self._rows(content)[1][0].startswith("=")


@pytest.mark.unit
class TestXLSXFormatter:
    def test_extension(self):
        assert XLSXFormatter().extension == "xlsx"

    def test_round_trip_restores_field_names(self):
        formatter = XLSXFormatter()
        decoded = formatter.decode(formatter.encode(NESTED))
        assert decoded[0]["email"] == "a@plane.so"
        assert decoded[0]["display_name"] == "Ada"

    def test_lists_are_joined_with_the_configured_separator(self):
        formatter = XLSXFormatter(list_joiner=" | ")
        decoded = formatter.decode(formatter.encode([{"tags": ["x", "y"]}]))
        assert decoded[0]["tags"] == "x | y"

    def test_dicts_are_serialised_and_parsed_back(self):
        formatter = XLSXFormatter()
        decoded = formatter.decode(formatter.encode([{"profile": {"role": "admin"}}]))
        assert decoded[0]["profile"] == {"role": "admin"}

    def test_none_becomes_an_empty_cell(self):
        formatter = XLSXFormatter()
        decoded = formatter.decode(formatter.encode([{"name": None}]))
        assert decoded[0]["name"] in ("", None)

    def test_empty_input_still_encodes_to_a_readable_workbook(self):
        formatter = XLSXFormatter()
        assert formatter.decode(formatter.encode([])) == []

    def test_decoding_an_empty_sheet_yields_no_rows(self):
        workbook = Workbook()
        buffer = io.BytesIO()
        workbook.save(buffer)
        assert XLSXFormatter().decode(buffer.getvalue()) == []

    def test_headers_can_be_kept_verbatim_on_decode(self):
        formatter = XLSXFormatter()
        decoded = formatter.decode(formatter.encode([{"display_name": "Ada"}]), normalize_headers=False)
        assert list(decoded[0]) == ["Display Name"]
