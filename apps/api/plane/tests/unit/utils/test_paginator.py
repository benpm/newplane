# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Unit tests for cursor pagination.

Cursors are serialised into URLs, so their string form is a wire format: a
change to it silently breaks every client holding a page link. The paginator
also decides how many rows a page really returns and whether a next page is
advertised, which is exactly where off-by-one errors hide.
"""

import pytest

from plane.utils.paginator import (
    BadPaginationError,
    Cursor,
    CursorResult,
    OffsetPaginator,
)


@pytest.mark.unit
class TestCursor:
    def test_string_form_is_value_offset_isprev(self):
        assert str(Cursor(100, 2, True)) == "100:2:1"
        assert str(Cursor(100, 0, False)) == "100:0:0"

    def test_round_trips_through_from_string(self):
        assert Cursor.from_string(str(Cursor(50, 3, True))) == Cursor(50, 3, True)

    def test_from_string_keeps_floats_as_floats(self):
        assert Cursor.from_string("1.5:0:0").value == 1.5

    @pytest.mark.parametrize("bad", ["", "1:2", "1:2:3:4", "a:2:0", "1:b:0"])
    def test_from_string_rejects_malformed_input(self, bad):
        with pytest.raises(ValueError):
            Cursor.from_string(bad)

    def test_truthiness_reflects_has_results_only(self):
        assert bool(Cursor(0, 0, False, has_results=True)) is True
        # A non-zero value must not make an empty cursor look populated.
        assert bool(Cursor(100, 5, False, has_results=False)) is False
        assert bool(Cursor(100, 5, False)) is False

    def test_equality_covers_has_results(self):
        assert Cursor(1, 2, True, True) == Cursor(1, 2, True, True)
        assert not Cursor(1, 2, True, True) == Cursor(1, 2, True, False)

    def test_repr_mentions_the_parts(self):
        text = repr(Cursor(7, 1, True))
        assert "value=7" in text and "offset=1" in text


@pytest.mark.unit
class TestCursorResult:
    def test_behaves_like_the_sequence_it_wraps(self):
        result = CursorResult(["a", "b"], next=Cursor(1, 1), prev=Cursor(1, 0), hits=2, max_hits=1)
        assert len(result) == 2
        assert result[0] == "a"
        assert list(result) == ["a", "b"]
        assert "CursorResult" in repr(result)


class _FakeQuerySet:
    """Minimal queryset stand-in: enough slicing and counting for the paginator.

    Using a list keeps these tests free of the database while still exercising
    the offset arithmetic, which is the part that actually goes wrong.
    """

    def __init__(self, items):
        self._items = list(items)

    def order_by(self, *args, **kwargs):
        return self

    def values(self, *fields):
        return self

    def count(self):
        return len(self._items)

    def __getitem__(self, key):
        return _FakeQuerySet(self._items[key]) if isinstance(key, slice) else self._items[key]

    def __iter__(self):
        return iter(self._items)

    def __len__(self):
        return len(self._items)

    def __eq__(self, other):
        return isinstance(other, _FakeQuerySet) and self._items == other._items


@pytest.mark.unit
class TestOffsetPaginator:
    def _paginator(self, count=25, **kwargs):
        return OffsetPaginator(_FakeQuerySet(range(count)), **kwargs)

    def test_order_by_strips_the_descending_marker(self):
        paginator = OffsetPaginator(_FakeQuerySet([]), order_by="-created_at")
        assert paginator.key == ("created_at",)
        assert paginator.desc is True

    def test_ascending_order_by_is_kept_as_is(self):
        paginator = OffsetPaginator(_FakeQuerySet([]), order_by="name")
        assert paginator.key == ("name",)
        assert paginator.desc is False

    def test_sequence_order_by_is_passed_through(self):
        paginator = OffsetPaginator(_FakeQuerySet([]), order_by=["a", "b"])
        assert paginator.key == ["a", "b"]

    def test_first_page_reports_a_next_and_no_previous(self):
        result = self._paginator(count=25).get_result(limit=10)
        assert len(result) == 10
        assert bool(result.next) is True
        assert bool(result.prev) is False

    def test_last_page_reports_no_next_and_a_previous(self):
        result = self._paginator(count=25).get_result(limit=10, cursor=Cursor(10, 2, False))
        assert len(result) == 5
        assert bool(result.next) is False
        assert bool(result.prev) is True

    def test_exactly_full_page_does_not_advertise_a_next(self):
        """The extra row fetched to probe for a next page must not be counted."""
        result = self._paginator(count=10).get_result(limit=10)
        assert len(result) == 10
        assert bool(result.next) is False

    def test_hits_and_max_hits_describe_the_whole_set(self):
        result = self._paginator(count=25).get_result(limit=10)
        assert result.hits == 25
        assert result.max_hits == 3

    def test_limit_is_capped_by_max_limit(self):
        result = OffsetPaginator(_FakeQuerySet(range(50)), max_limit=5).get_result(limit=1000)
        assert len(result) == 5

    def test_empty_queryset_yields_nothing(self):
        result = self._paginator(count=0).get_result(limit=10)
        assert len(result) == 0
        assert result.hits == 0
        assert bool(result.next) is False

    def test_offset_beyond_max_offset_is_rejected(self):
        paginator = OffsetPaginator(_FakeQuerySet(range(100)), max_offset=10)
        with pytest.raises(BadPaginationError):
            paginator.get_result(limit=10, cursor=Cursor(10, 5, False))

    def test_negative_offset_is_rejected(self):
        with pytest.raises(BadPaginationError):
            self._paginator().get_result(limit=10, cursor=Cursor(10, -1, False))

    def test_on_results_hook_transforms_the_page(self):
        paginator = OffsetPaginator(
            _FakeQuerySet(range(5)), on_results=lambda rows: [f"row-{value}" for value in rows]
        )
        assert paginator.get_result(limit=10)[0] == "row-0"

    def test_total_count_queryset_overrides_the_page_count(self):
        paginator = OffsetPaginator(
            _FakeQuerySet(range(5)), total_count_queryset=_FakeQuerySet(range(99))
        )
        assert paginator.get_result(limit=10).hits == 99

    def test_process_results_is_left_to_subclasses(self):
        """The base class deliberately refuses to guess a grouping strategy."""
        with pytest.raises(NotImplementedError):
            self._paginator().process_results(["a"])
