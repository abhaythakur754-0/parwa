"""
Tests for shared/utils/pagination.py

Tests pagination parameter parsing, max limit enforcement, page calculations.
Security: prevent DoS via extremely large page sizes.
"""

from shared.utils.pagination import (
    parse_pagination,
    get_next_offset,
    get_total_pages,
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    MAX_OFFSET,
)


class TestConstants:
    """Tests for pagination security constants."""

    def test_default_page_size_is_20(self):
        assert DEFAULT_PAGE_SIZE == 20

    def test_max_page_size_is_100(self):
        assert MAX_PAGE_SIZE == 100

    def test_max_offset_is_10000(self):
        assert MAX_OFFSET == 10000


class TestParsePagination:
    """Tests for parse_pagination() function."""

    def test_defaults(self):
        result = parse_pagination()
        assert result.offset == 0
        assert result.limit == 20

    def test_custom_offset_and_limit(self):
        result = parse_pagination(offset=50, limit=10)
        assert result.offset == 50
        assert result.limit == 10

    def test_negative_offset_becomes_zero(self):
        result = parse_pagination(offset=-5)
        assert result.offset == 0

    def test_negative_limit_becomes_default(self):
        result = parse_pagination(limit=-5)
        assert result.limit == 20

    def test_zero_limit_becomes_default(self):
        result = parse_pagination(limit=0)
        assert result.limit == 20

    def test_limit_exceeds_max_capped(self):
        result = parse_pagination(limit=999999)
        assert result.limit == 100

    def test_offset_exceeds_max_capped(self):
        result = parse_pagination(offset=999999)
        assert result.offset == 10000

    def test_limit_at_max_allowed(self):
        result = parse_pagination(limit=100)
        assert result.limit == 100

    def test_offset_at_max_allowed(self):
        result = parse_pagination(offset=10000)
        assert result.offset == 10000

    def test_limit_just_over_max_capped(self):
        result = parse_pagination(limit=101)
        assert result.limit == 100

    def test_offset_just_over_max_capped(self):
        result = parse_pagination(offset=10001)
        assert result.offset == 10000

    def test_non_integer_offset_becomes_zero(self):
        result = parse_pagination(offset="abc")
        assert result.offset == 0

    def test_non_integer_limit_becomes_default(self):
        result = parse_pagination(limit="abc")
        assert result.limit == 20

    def test_none_offset_becomes_zero(self):
        result = parse_pagination(offset=None)
        assert result.offset == 0

    def test_none_limit_becomes_default(self):
        result = parse_pagination(limit=None)
        assert result.limit == 20

    def test_custom_max_limit(self):
        result = parse_pagination(limit=50, max_limit=25)
        assert result.limit == 25

    def test_custom_max_offset(self):
        result = parse_pagination(offset=500, max_offset=100)
        assert result.offset == 100

    def test_returns_named_tuple(self):
        result = parse_pagination()
        assert isinstance(result, tuple)
        assert hasattr(result, "offset")
        assert hasattr(result, "limit")

    def test_float_offset_becomes_zero(self):
        result = parse_pagination(offset=1.5)
        assert result.offset == 0

    def test_float_limit_becomes_default(self):
        result = parse_pagination(limit=10.5)
        assert result.limit == 20


class TestGetNextOffset:
    """Tests for get_next_offset() function."""

    def test_basic_next_page(self):
        assert get_next_offset(0, 20, 100) == 20

    def test_second_page(self):
        assert get_next_offset(20, 20, 100) == 40

    def test_last_page_returns_current(self):
        assert get_next_offset(80, 20, 100) == 80

    def test_exact_boundary(self):
        assert get_next_offset(80, 20, 100) == 80

    def test_beyond_total_returns_current(self):
        assert get_next_offset(100, 20, 50) == 100

    def test_zero_total_returns_current(self):
        assert get_next_offset(0, 20, 0) == 0

    def test_one_result(self):
        assert get_next_offset(0, 20, 1) == 0

    def test_non_multiple_page_size(self):
        assert get_next_offset(0, 20, 25) == 20


class TestGetTotalPages:
    """Tests for get_total_pages() function."""

    def test_exact_division(self):
        assert get_total_pages(100, 20) == 5

    def test_round_up(self):
        assert get_total_pages(101, 20) == 6

    def test_one_page(self):
        assert get_total_pages(10, 20) == 1

    def test_zero_total(self):
        assert get_total_pages(0, 20) == 1

    def test_negative_total(self):
        assert get_total_pages(-5, 20) == 1

    def test_zero_page_size(self):
        assert get_total_pages(100, 0) == 1

    def test_negative_page_size(self):
        assert get_total_pages(100, -5) == 1

    def test_one_per_page(self):
        assert get_total_pages(5, 1) == 5

    def test_large_total(self):
        assert get_total_pages(1000, 100) == 10
