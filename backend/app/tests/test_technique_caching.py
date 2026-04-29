"""
Tests for TechniqueCache (Week 10 Day 3)

Comprehensive unit tests covering:
- Basic set/get operations
- TTL expiry
- LRU eviction
- Per-company isolation
- Cache hit/miss stats
- Cache invalidation
- Cache warming
- Cache cleanup
- Cache resize
- Concurrent access thread safety
- Edge cases (empty cache, non-existent keys)
"""

import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest

from app.core.technique_caching import (
    CacheEntry,
    TechniqueCache,
    DEFAULT_MAX_SIZE,
    DEFAULT_TTL_BY_TIER,
    DEFAULT_TTL_SECONDS,
)
from app.core.technique_router import TechniqueID


# ── Fixtures ──────────────────────────────────────────────────────


@pytest.fixture
def cache():
    """Fresh cache for each test."""
    return TechniqueCache(max_size=100)


@pytest.fixture
def populated_cache(cache):
    """Cache with sample entries."""
    cache.set(
        technique_id="clara",
        query_hash="q1",
        signals_hash="s1",
        company_id="company_a",
        result={"answer": "hello"},
    )
    cache.set(
        technique_id="clara",
        query_hash="q2",
        signals_hash="s2",
        company_id="company_a",
        result={"answer": "world"},
    )
    cache.set(
        technique_id="clara",
        query_hash="q1",
        signals_hash="s1",
        company_id="company_b",
        result={"answer": "different"},
    )
    cache.set(
        technique_id="chain_of_thought",
        query_hash="q3",
        signals_hash="s3",
        company_id="company_a",
        result={"answer": "step1"},
    )
    return cache


# ── 1. Basic Set/Get Operations ──────────────────────────────────


class TestBasicSetGet:
    """Tests for fundamental set/get operations."""

    def test_set_and_get(self, cache):
        cache.set(
            technique_id="clara",
            query_hash="q1",
            signals_hash="s1",
            company_id="co1",
            result={"data": "test"},
        )
        result = cache.get(
            technique_id="clara",
            query_hash="q1",
            signals_hash="s1",
            company_id="co1",
        )
        assert result == {"data": "test"}

    def test_get_miss(self, cache):
        result = cache.get(
            technique_id="clara",
            query_hash="nonexistent",
            signals_hash="s1",
            company_id="co1",
        )
        assert result is None

    def test_set_returns_true(self, cache):
        ok = cache.set(
            technique_id="clara",
            query_hash="q1",
            signals_hash="s1",
            company_id="co1",
            result="result",
        )
        assert ok is True

    def test_set_overwrites(self, cache):
        cache.set(
            technique_id="clara",
            query_hash="q1",
            signals_hash="s1",
            company_id="co1",
            result="v1",
        )
        cache.set(
            technique_id="clara",
            query_hash="q1",
            signals_hash="s1",
            company_id="co1",
            result="v2",
        )
        result = cache.get(
            technique_id="clara",
            query_hash="q1",
            signals_hash="s1",
            company_id="co1",
        )
        assert result == "v2"

    def test_different_keys_different_results(self, cache):
        cache.set("clara", "q1", "s1", "co1", "result_a")
        cache.set("clara", "q2", "s1", "co1", "result_b")
        a = cache.get("clara", "q1", "s1", "co1")
        b = cache.get("clara", "q2", "s1", "co1")
        assert a == "result_a"
        assert b == "result_b"

    def test_set_with_technique_id_enum(self, cache):
        cache.set(
            technique_id=TechniqueID.GST,
            query_hash="q1",
            signals_hash="s1",
            company_id="co1",
            result="gst_result",
        )
        result = cache.get(
            technique_id=TechniqueID.GST,
            query_hash="q1",
            signals_hash="s1",
            company_id="co1",
        )
        assert result == "gst_result"

    def test_get_with_technique_id_enum(self, cache):
        cache.set(
            technique_id=TechniqueID.CLARA,
            query_hash="q1",
            signals_hash="s1",
            company_id="co1",
            result="result",
        )
        result = cache.get(
            technique_id=TechniqueID.CLARA,
            query_hash="q1",
            signals_hash="s1",
            company_id="co1",
        )
        assert result == "result"

    def test_cache_key_deterministic(self, cache):
        key1 = TechniqueCache.make_cache_key(
            "clara", "q1", "s1", "co1",
        )
        key2 = TechniqueCache.make_cache_key(
            "clara", "q1", "s1", "co1",
        )
        assert key1 == key2
        assert len(key1) == 64  # SHA-256 hex digest

    def test_cache_key_different_inputs(self, cache):
        key1 = TechniqueCache.make_cache_key(
            "clara", "q1", "s1", "co1",
        )
        key2 = TechniqueCache.make_cache_key(
            "clara", "q2", "s1", "co1",
        )
        assert key1 != key2

    def test_none_result_storable(self, cache):
        cache.set("clara", "q1", "s1", "co1", None)
        result = cache.get("clara", "q1", "s1", "co1")
        assert result is None


# ── 2. TTL Expiry ────────────────────────────────────────────────


class TestTTLExpiry:
    """Tests for TTL-based expiry."""

    def test_entry_not_expired_immediately(self, cache):
        cache.set(
            "clara", "q1", "s1", "co1",
            "result", ttl_seconds=10,
        )
        result = cache.get("clara", "q1", "s1", "co1")
        assert result == "result"

    def test_entry_expired_after_ttl(self, cache):
        cache.set(
            "clara", "q1", "s1", "co1",
            "result", ttl_seconds=0,
        )
        # Even with 0 TTL, the entry is set but expires
        # immediately on next get
        time.sleep(0.01)
        result = cache.get("clara", "q1", "s1", "co1")
        assert result is None

    def test_expired_entry_removed_on_get(self, cache):
        cache.set(
            "clara", "q1", "s1", "co1",
            "result", ttl_seconds=0,
        )
        time.sleep(0.01)
        cache.get("clara", "q1", "s1", "co1")  # triggers removal
        stats = cache.get_stats()
        assert stats.size == 0

    def test_custom_ttl_override(self, cache):
        cache.set(
            "clara", "q1", "s1", "co1",
            "result", ttl_seconds=1,
        )
        time.sleep(0.05)
        result = cache.get("clara", "q1", "s1", "co1")
        assert result == "result"  # Still within 1s

    def test_tier_based_ttl(self, cache):
        # Tier 1 technique should use tier_1 TTL
        cache.set(
            TechniqueID.CLARA.value, "q1", "s1", "co1",
            "result",
        )
        # Verify the entry was created
        result = cache.get(
            TechniqueID.CLARA.value, "q1", "s1", "co1",
        )
        assert result == "result"

    def test_set_technique_ttl(self, cache):
        cache.set_technique_ttl("clara", 1)
        cache.set("clara", "q1", "s1", "co1", "result")
        time.sleep(0.05)
        result = cache.get("clara", "q1", "s1", "co1")
        assert result == "result"

    def test_get_technique_ttl(self, cache):
        assert cache.get_technique_ttl("clara") is None
        cache.set_technique_ttl("clara", 300)
        assert cache.get_technique_ttl("clara") == 300

    def test_set_technique_ttl_with_enum(self, cache):
        cache.set_technique_ttl(TechniqueID.GST, 500)
        assert cache.get_technique_ttl(TechniqueID.GST) == 500


# ── 3. LRU Eviction ──────────────────────────────────────────────


class TestLRUEviction:
    """Tests for LRU eviction policy."""

    def test_eviction_at_max_size(self):
        cache = TechniqueCache(max_size=3)
        for i in range(5):
            cache.set(
                "clara", f"q{i}", "s1", "co1",
                f"result_{i}",
            )
        stats = cache.get_stats()
        assert stats.size == 3
        assert stats.evictions == 2

    def test_lru_order_accessed_entry_kept(self):
        cache = TechniqueCache(max_size=3)
        cache.set("clara", "q1", "s1", "co1", "r1")
        cache.set("clara", "q2", "s1", "co1", "r2")
        cache.set("clara", "q3", "s1", "co1", "r3")

        # Access q1 to make it recently used
        cache.get("clara", "q1", "s1", "co1")

        # Add new entry — should evict q2 (LRU), not q1
        cache.set("clara", "q4", "s1", "co1", "r4")

        assert cache.get("clara", "q1", "s1", "co1") == "r1"
        assert cache.get("clara", "q2", "s1", "co1") is None
        assert cache.get("clara", "q3", "s1", "co1") == "r3"
        assert cache.get("clara", "q4", "s1", "co1") == "r4"

    def test_eviction_count_in_stats(self):
        cache = TechniqueCache(max_size=2)
        cache.set("clara", "q1", "s1", "co1", "r1")
        cache.set("clara", "q2", "s1", "co1", "r2")
        cache.set("clara", "q3", "s1", "co1", "r3")
        stats = cache.get_stats()
        assert stats.evictions == 1


# ── 4. Per-Company Isolation ─────────────────────────────────────


class TestCompanyIsolation:
    """Tests for per-company cache isolation."""

    def test_different_company_different_result(
        self, populated_cache,
    ):
        r_a = populated_cache.get(
            "clara", "q1", "s1", "company_a",
        )
        r_b = populated_cache.get(
            "clara", "q1", "s1", "company_b",
        )
        assert r_a == {"answer": "hello"}
        assert r_b == {"answer": "different"}

    def test_invalidate_single_company(self, populated_cache):
        removed = populated_cache.invalidate(
            company_id="company_b",
        )
        assert removed >= 1

        r_b = populated_cache.get(
            "clara", "q1", "s1", "company_b",
        )
        assert r_b is None

        r_a = populated_cache.get(
            "clara", "q1", "s1", "company_a",
        )
        assert r_a is not None

    def test_invalidate_preserves_other_company(
        self, populated_cache,
    ):
        populated_cache.invalidate(company_id="company_b")
        stats = populated_cache.get_stats()
        assert "company_a" in stats.company_counts

    def test_company_counts_in_stats(self, populated_cache):
        stats = populated_cache.get_stats()
        assert stats.company_counts["company_a"] == 3
        assert stats.company_counts["company_b"] == 1


# ── 5. Cache Hit/Miss Stats ──────────────────────────────────────


class TestHitMissStats:
    """Tests for cache hit/miss tracking."""

    def test_miss_on_empty(self, cache):
        cache.get("clara", "q1", "s1", "co1")
        stats = cache.get_stats()
        assert stats.misses == 1
        assert stats.hits == 0

    def test_hit_after_set(self, cache):
        cache.set("clara", "q1", "s1", "co1", "result")
        cache.get("clara", "q1", "s1", "co1")
        stats = cache.get_stats()
        assert stats.hits == 1
        assert stats.misses == 0

    def test_hit_rate(self, cache):
        cache.set("clara", "q1", "s1", "co1", "result")
        cache.get("clara", "q1", "s1", "co1")  # hit
        cache.get("clara", "q2", "s1", "co1")  # miss
        stats = cache.get_stats()
        assert stats.hit_rate == 0.5
        assert stats.miss_rate == 0.5

    def test_hit_rate_zero_requests(self, cache):
        stats = cache.get_stats()
        assert stats.hit_rate == 0.0
        assert stats.miss_rate == 0.0

    def test_total_requests(self, cache):
        cache.get("clara", "q1", "s1", "co1")  # miss
        cache.get("clara", "q1", "s1", "co1")  # miss again
        stats = cache.get_stats()
        assert stats.total_requests == 2

    def test_expired_counts_as_miss(self, cache):
        cache.set(
            "clara", "q1", "s1", "co1",
            "result", ttl_seconds=0,
        )
        time.sleep(0.01)
        cache.get("clara", "q1", "s1", "co1")
        stats = cache.get_stats()
        assert stats.misses == 1
        assert stats.expired_cleanups == 1

    def test_reset_stats(self, cache):
        cache.get("clara", "q1", "s1", "co1")
        cache.reset_stats()
        stats = cache.get_stats()
        assert stats.hits == 0
        assert stats.misses == 0
        assert stats.evictions == 0


# ── 6. Cache Invalidation ────────────────────────────────────────


class TestInvalidation:
    """Tests for cache invalidation."""

    def test_invalidate_all(self, populated_cache):
        removed = populated_cache.invalidate()
        assert removed == 4
        stats = populated_cache.get_stats()
        assert stats.size == 0

    def test_invalidate_by_technique(self, populated_cache):
        removed = populated_cache.invalidate(
            technique_id="clara",
        )
        assert removed == 3
        # CoT entry should remain
        result = populated_cache.get(
            "chain_of_thought", "q3", "s3", "company_a",
        )
        assert result == {"answer": "step1"}

    def test_invalidate_by_company(self, populated_cache):
        removed = populated_cache.invalidate(
            company_id="company_a",
        )
        assert removed == 3

    def test_invalidate_by_technique_and_company(
        self, populated_cache,
    ):
        removed = populated_cache.invalidate(
            technique_id="clara",
            company_id="company_a",
        )
        assert removed == 2
        # Company B clara should remain
        result = populated_cache.get(
            "clara", "q1", "s1", "company_b",
        )
        assert result is not None

    def test_invalidate_nonexistent(self, cache):
        removed = cache.invalidate(
            technique_id="nonexistent",
        )
        assert removed == 0

    def test_invalidate_with_technique_id_enum(
        self, populated_cache,
    ):
        removed = populated_cache.invalidate(
            technique_id=TechniqueID.CLARA,
        )
        assert removed == 3

    def test_invalidate_pattern_by_company(self, populated_cache):
        removed = populated_cache.invalidate_pattern(
            company_id="company_a",
        )
        assert removed == 3

    def test_invalidate_pattern_with_prefix(self, populated_cache):
        # clara starts with "cla"
        removed = populated_cache.invalidate_pattern(
            company_id="company_a",
            technique_prefix="cla",
        )
        assert removed == 2


# ── 7. Cache Warming ─────────────────────────────────────────────


class TestCacheWarming:
    """Tests for cache warming/preloading."""

    def test_warm_basic(self, cache):
        entries = [
            {
                "query_hash": "q1",
                "signals_hash": "s1",
                "result": "result_1",
            },
            {
                "query_hash": "q2",
                "signals_hash": "s2",
                "result": "result_2",
            },
        ]
        loaded = cache.warm("clara", "co1", entries)
        assert loaded == 2

        r1 = cache.get("clara", "q1", "s1", "co1")
        assert r1 == "result_1"

    def test_warm_with_custom_ttl(self, cache):
        entries = [
            {
                "query_hash": "q1",
                "signals_hash": "s1",
                "result": "result",
                "ttl_seconds": 1,
            },
        ]
        cache.warm("clara", "co1", entries)
        result = cache.get("clara", "q1", "s1", "co1")
        assert result == "result"

    def test_warm_skips_none_result(self, cache):
        entries = [
            {
                "query_hash": "q1",
                "signals_hash": "s1",
                "result": None,
            },
        ]
        loaded = cache.warm("clara", "co1", entries)
        assert loaded == 0

    def test_warm_empty_list(self, cache):
        loaded = cache.warm("clara", "co1", [])
        assert loaded == 0

    def test_warm_with_technique_id_enum(self, cache):
        entries = [
            {
                "query_hash": "q1",
                "signals_hash": "s1",
                "result": "result",
            },
        ]
        loaded = cache.warm(TechniqueID.GST, "co1", entries)
        assert loaded == 1


# ── 8. Cache Cleanup ─────────────────────────────────────────────


class TestCleanup:
    """Tests for cache cleanup operations."""

    def test_cleanup_expired(self, cache):
        cache.set(
            "clara", "q1", "s1", "co1",
            "result", ttl_seconds=0,
        )
        cache.set(
            "clara", "q2", "s1", "co1",
            "result", ttl_seconds=300,
        )
        time.sleep(0.01)

        removed = cache.cleanup()
        assert removed == 1

        stats = cache.get_stats()
        assert stats.size == 1

    def test_cleanup_no_expired(self, cache):
        cache.set("clara", "q1", "s1", "co1", "result")
        removed = cache.cleanup()
        assert removed == 0

    def test_cleanup_empty_cache(self, cache):
        removed = cache.cleanup()
        assert removed == 0

    def test_clear_all(self, populated_cache):
        populated_cache.clear()
        stats = populated_cache.get_stats()
        assert stats.size == 0
        assert stats.hits == 0
        assert stats.misses == 0


# ── 9. Cache Resize ──────────────────────────────────────────────


class TestResize:
    """Tests for cache resizing."""

    def test_resize_down_evicts(self, cache):
        for i in range(5):
            cache.set(
                "clara", f"q{i}", "s1", "co1", f"r{i}",
            )
        evicted = cache.resize(max_size=2)
        assert evicted == 3
        stats = cache.get_stats()
        assert stats.size == 2
        assert stats.max_size == 2

    def test_resize_up(self):
        cache = TechniqueCache(max_size=2)
        cache.set("clara", "q1", "s1", "co1", "r1")
        evicted = cache.resize(max_size=10)
        assert evicted == 0
        assert cache.get_max_size() == 10

    def test_resize_to_minimum(self, cache):
        for i in range(5):
            cache.set(
                "clara", f"q{i}", "s1", "co1", f"r{i}",
            )
        evicted = cache.resize(max_size=0)
        assert cache.get_max_size() == 1
        assert cache.get_size() <= 1

    def test_resize_same_size(self, cache):
        cache.set("clara", "q1", "s1", "co1", "r1")
        evicted = cache.resize(max_size=100)
        assert evicted == 0
        assert cache.get_size() == 1


# ── 10. Concurrent Access ────────────────────────────────────────


class TestConcurrency:
    """Tests for thread safety."""

    def test_concurrent_writes(self, cache):
        errors = []

        def write_batch(start):
            try:
                for i in range(50):
                    cache.set(
                        "clara",
                        f"q_{start}_{i}",
                        "s1",
                        f"co_{start % 3}",
                        f"result_{i}",
                    )
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=write_batch, args=(t,))
            for t in range(10)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert cache.get_size() <= 100  # max_size

    def test_concurrent_reads(self, populated_cache):
        errors = []

        def read_many():
            try:
                for _ in range(100):
                    populated_cache.get(
                        "clara", "q1", "s1", "company_a",
                    )
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=read_many) for _ in range(5)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0

    def test_concurrent_read_write(self, populated_cache):
        errors = []

        def writer():
            try:
                for i in range(50):
                    populated_cache.set(
                        "clara", f"qw_{i}", "s1", "co1",
                        f"result_{i}",
                    )
            except Exception as e:
                errors.append(e)

        def reader():
            try:
                for _ in range(50):
                    populated_cache.get(
                        "clara", "q1", "s1", "company_a",
                    )
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=writer),
            threading.Thread(target=reader),
            threading.Thread(target=reader),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0

    def test_concurrent_invalidation(self, populated_cache):
        errors = []

        def invalidator():
            try:
                for _ in range(10):
                    populated_cache.invalidate()
                    populated_cache.set(
                        "clara", "q_new", "s1", "co1", "r",
                    )
            except Exception as e:
                errors.append(e)

        with ThreadPoolExecutor(max_workers=3) as executor:
            futs = [
                executor.submit(invalidator) for _ in range(3)
            ]
            for f in as_completed(futs):
                f.result()

        assert len(errors) == 0


# ── 11. Monitoring ───────────────────────────────────────────────


class TestMonitoring:
    """Tests for cache monitoring methods."""

    def test_get_size(self, populated_cache):
        assert populated_cache.get_size() == 4

    def test_get_max_size(self, cache):
        assert cache.get_max_size() == 100

    def test_get_entry_count_by_company(
        self, populated_cache,
    ):
        count = populated_cache.get_entry_count_by_company(
            "company_a",
        )
        assert count == 3

    def test_get_entry_count_by_unknown_company(self, cache):
        count = cache.get_entry_count_by_company("unknown")
        assert count == 0

    def test_get_oldest_entry_age(self, populated_cache):
        age = populated_cache.get_oldest_entry_age()
        assert age is not None
        assert age < 1.0  # Less than 1 second old

    def test_get_oldest_entry_age_empty(self, cache):
        assert cache.get_oldest_entry_age() is None

    def test_get_newest_entry_age(self, populated_cache):
        age = populated_cache.get_newest_entry_age()
        assert age is not None
        assert age < 1.0

    def test_get_newest_entry_age_empty(self, cache):
        assert cache.get_newest_entry_age() is None

    def test_stats_utilization(self, populated_cache):
        stats = populated_cache.get_stats()
        assert 0.0 <= stats.utilization <= 1.0

    def test_stats_technique_counts(self, populated_cache):
        stats = populated_cache.get_stats()
        assert stats.technique_counts["clara"] == 3
        assert stats.technique_counts["chain_of_thought"] == 1


# ── 12. Edge Cases ───────────────────────────────────────────────


class TestEdgeCases:
    """Tests for edge cases."""

    def test_empty_cache_stats(self, cache):
        stats = cache.get_stats()
        assert stats.hits == 0
        assert stats.misses == 0
        assert stats.evictions == 0
        assert stats.size == 0
        assert stats.hit_rate == 0.0

    def test_get_from_empty_cache(self, cache):
        result = cache.get("clara", "q1", "s1", "co1")
        assert result is None

    def test_invalidate_empty_cache(self, cache):
        removed = cache.invalidate()
        assert removed == 0

    def test_cleanup_empty_cache(self, cache):
        removed = cache.cleanup()
        assert removed == 0

    def test_warm_into_full_cache(self, cache):
        cache = TechniqueCache(max_size=2)
        cache.set("clara", "q1", "s1", "co1", "r1")
        cache.set("clara", "q2", "s1", "co1", "r2")
        entries = [
            {"query_hash": "q3", "signals_hash": "s3",
             "result": "r3"},
            {"query_hash": "q4", "signals_hash": "s4",
             "result": "r4"},
            {"query_hash": "q5", "signals_hash": "s5",
             "result": "r5"},
        ]
        loaded = cache.warm("clara", "co1", entries)
        assert loaded == 3
        assert cache.get_size() == 2

    def test_large_result_value(self, cache):
        big = "x" * 100000
        cache.set("clara", "q1", "s1", "co1", big)
        result = cache.get("clara", "q1", "s1", "co1")
        assert result == big

    def test_empty_string_keys(self, cache):
        cache.set("clara", "", "", "co1", "result")
        result = cache.get("clara", "", "", "co1")
        assert result == "result"

    def test_default_ttl_constant(self):
        assert DEFAULT_TTL_SECONDS == 600

    def test_default_max_size_constant(self):
        assert DEFAULT_MAX_SIZE == 1000

    def test_default_ttl_by_tier(self):
        assert DEFAULT_TTL_BY_TIER["tier_1"] == 300
        assert DEFAULT_TTL_BY_TIER["tier_2"] == 600
        assert DEFAULT_TTL_BY_TIER["tier_3"] == 1200


# ── 13. CacheEntry Dataclass ─────────────────────────────────────


class TestCacheEntry:
    """Tests for CacheEntry dataclass."""

    def test_entry_not_expired_initially(self):
        entry = CacheEntry(
            key="k", technique_id="clara",
            company_id="co1", result="data",
            ttl_seconds=300,
        )
        assert not entry.is_expired

    def test_entry_expired_after_ttl(self):
        entry = CacheEntry(
            key="k", technique_id="clara",
            company_id="co1", result="data",
            ttl_seconds=0,
            created_at=time.time() - 1,
        )
        assert entry.is_expired

    def test_touch_updates_access(self):
        entry = CacheEntry(
            key="k", technique_id="clara",
            company_id="co1", result="data",
        )
        assert entry.access_count == 0
        entry.touch()
        assert entry.access_count == 1

    def test_age_seconds(self):
        entry = CacheEntry(
            key="k", technique_id="clara",
            company_id="co1", result="data",
            created_at=time.time() - 10,
        )
        assert 9.9 < entry.age_seconds < 10.1
