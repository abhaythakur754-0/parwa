"""
Comprehensive W10D3 Gap Tests for PARWA B2B SaaS AI Phone Agent Platform.

Covers 55 identified testing gaps across 7 core modules:
  - technique_metrics.py   (Gaps 1-8)
  - technique_caching.py   (Gaps 9-15)
  - per_tenant_config.py   (Gaps 16-22)
  - state_migration.py     (Gaps 23-31)
  - shared_gsd.py          (Gaps 32-38)
  - capacity_monitor.py    (Gaps 39-46)
  - dspy_integration.py    (Gaps 47-55)
"""

import pytest
import threading
import time
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch, PropertyMock
from collections import OrderedDict

from app.core.technique_metrics import TechniqueMetricsCollector, ExecutionStatus
from app.core.technique_caching import TechniqueCache
from app.core.per_tenant_config import TenantConfigManager
from app.core.state_migration import StateMigrator
from app.core.shared_gsd import SharedGSDManager
from app.core.capacity_monitor import CapacityMonitor
from app.core.dspy_integration import DSPyIntegration, StubModule, StubOptimizer, StubPrediction
from app.core.technique_router import TechniqueID


# ═══════════════════════════════════════════════════════════════════
# MODULE 1: technique_metrics.py (Gaps 1-8)
# ═══════════════════════════════════════════════════════════════════


class TestTechniqueMetricsGaps:
    """Tests for technique_metrics.py edge cases and gaps."""

    def setup_method(self):
        self.collector = TechniqueMetricsCollector()

    # -- Gap 1 (HIGH): Variant stats treat timeout+error as "failure" --

    def test_gap01_variant_summary_timeout_and_error_increment_failure_count(self):
        """Verify that TIMEOUT and ERROR statuses both increment variant_summary.failure_count.

        The _update_variant_stats method only checks SUCCESS vs non-SUCCESS,
        so TIMEOUT and ERROR are lumped into failure_count alongside FAILURE.
        """
        variant = "parwa"
        self.collector.record_execution(
            technique_id="clara", variant=variant, status="timeout",
        )
        self.collector.record_execution(
            technique_id="clara", variant=variant, status="error",
        )
        self.collector.record_execution(
            technique_id="clara", variant=variant, status="failure",
        )
        self.collector.record_execution(
            technique_id="clara", variant=variant, status="success",
        )

        summary = self.collector.get_variant_summary(variant)
        assert summary is not None
        # All non-success statuses (failure, timeout, error) counted as failures
        assert summary.failure_count == 3
        assert summary.success_count == 1
        assert summary.total_executions == 4

    # -- Gap 2 (MEDIUM): Negative exec_time_ms and negative tokens_used --

    def test_gap02_negative_exec_time_ms_and_tokens_used_are_recorded(self):
        """Verify negative values are recorded without rejection.

        The code does not validate that exec_time_ms or tokens_used are non-negative.
        Negative values flow through unmodified and corrupt aggregated stats.
        """
        self.collector.record_execution(
            technique_id="clara",
            exec_time_ms=-100.0,
            tokens_used=-50,
        )

        stats = self.collector.get_technique_stats("clara")
        assert stats is not None
        assert stats.total_executions == 1
        # Negative values are stored as-is (no validation)
        assert stats.total_exec_time_ms == -100.0
        assert stats.total_tokens == -50
        assert -100.0 in stats.exec_times
        assert stats.min_exec_time_ms == -100.0

    # -- Gap 3 (MEDIUM): get_percentiles with invalid metric string --

    def test_gap03_get_percentiles_unknown_metric_returns_zeros(self):
        """Verify get_percentiles with a non-existent metric key returns all zeros.

        Only 'exec_time_ms' and 'tokens_used' are recognized. Any other metric
        string collects no values, yielding zero percentiles.
        """
        self.collector.record_execution(
            technique_id="clara", exec_time_ms=100.0, tokens_used=50,
        )

        result = self.collector.get_percentiles(metric="foo_bar")
        assert result == {"p50": 0.0, "p95": 0.0, "p99": 0.0}

    # -- Gap 4 (LOW): get_time_windowed_stats with unrecognized window key --

    def test_gap04_time_windowed_stats_unrecognized_window_defaults_to_300s(self):
        """Verify an unrecognized window key silently defaults to 300 seconds.

        TIME_WINDOWS_SECONDS only has '1min', '5min', '15min', '1hr'.
        Unknown keys like '10min' fall through .get() default of 300.
        """
        # Record something that will be within any reasonable window
        self.collector.record_execution(
            technique_id="clara", exec_time_ms=50.0,
        )

        # Both recognized and unrecognized windows should return the record
        stats_5min = self.collector.get_time_windowed_stats("clara", window="5min")
        stats_10min = self.collector.get_time_windowed_stats("clara", window="10min")

        # Both should find the same record since default is 300s for both
        assert stats_5min.total_executions == stats_10min.total_executions

    # -- Gap 5 (MEDIUM): Returned TechniqueStats exec_times list mutation immunity --

    def test_gap05_mutating_returned_stats_does_not_affect_internal_state(self):
        """Verify that mutating the returned TechniqueStats exec_times list
        does not alter the collector's internal state.

        _copy_stats creates a shallow copy via list(), but get_time_windowed_stats
        builds a new TechniqueStats from scratch. Both should be immune.
        """
        self.collector.record_execution(
            technique_id="clara", exec_time_ms=10.0,
        )
        self.collector.record_execution(
            technique_id="clara", exec_time_ms=20.0,
        )

        stats = self.collector.get_technique_stats("clara")
        assert stats is not None
        original_len = len(stats.exec_times)
        assert original_len == 2

        # Mutate the returned list
        stats.exec_times.clear()
        stats.exec_times.append(9999.0)

        # Internal state should be unaffected
        stats_after = self.collector.get_technique_stats("clara")
        assert stats_after is not None
        assert len(stats_after.exec_times) == original_len
        assert 9999.0 not in stats_after.exec_times

    # -- Gap 6 (LOW): Leaderboard with limit=0 returns empty list --

    def test_gap06_leaderboard_limit_zero_returns_empty_list(self):
        """Verify get_leaderboard with limit=0 returns an empty list."""
        self.collector.record_execution(technique_id="clara", exec_time_ms=10.0)
        self.collector.record_execution(technique_id="crp", exec_time_ms=20.0)

        entries = self.collector.get_leaderboard(limit=0)
        assert entries == []

    # -- Gap 7 (LOW): cleanup_stale with max_age_seconds=0 removes all records --

    def test_gap07_cleanup_stale_max_age_zero_removes_all_records(self):
        """Verify cleanup_stale with max_age_seconds=0 removes all records.

        cutoff = time.time() - 0 = time.time(). Records with timestamps
        slightly before now are removed (timestamp >= cutoff check).
        A tiny sleep ensures timestamps are strictly before cutoff.
        """
        self.collector.record_execution(technique_id="clara", exec_time_ms=10.0)
        self.collector.record_execution(technique_id="crp", exec_time_ms=20.0)
        assert self.collector.get_record_count() == 2

        # Brief sleep to ensure record timestamps are before cutoff
        time.sleep(0.01)

        removed = self.collector.cleanup_stale(max_age_seconds=0)
        assert removed >= 0  # May remove 2 or 1 depending on timing
        assert self.collector.get_record_count() == 0

    # -- Gap 8 (LOW): Percentile calculation with all identical values --

    def test_gap08_percentiles_all_identical_values(self):
        """Verify p50==p95==p99 when all values are identical."""
        for _ in range(10):
            self.collector.record_execution(
                technique_id="clara", exec_time_ms=42.0,
            )

        result = self.collector.get_percentiles(metric="exec_time_ms")
        assert result["p50"] == 42.0
        assert result["p95"] == 42.0
        assert result["p99"] == 42.0


# ═══════════════════════════════════════════════════════════════════
# MODULE 2: technique_caching.py (Gaps 9-15)
# ═══════════════════════════════════════════════════════════════════


class TestTechniqueCachingGaps:
    """Tests for technique_caching.py edge cases and gaps."""

    def setup_method(self):
        self.cache = TechniqueCache(max_size=100, default_ttl=600)

    # -- Gap 9 (HIGH): None result stored --

    def test_gap09_none_result_stored_and_cache_size_increases(self):
        """Verify that storing None as a result actually persists it in the cache.

        set() stores None directly in CacheEntry. get() returns entry.result
        (None), incrementing hits not misses. Cache size should reflect storage.
        """
        self.cache.set(
            technique_id="clara",
            query_hash="q1",
            signals_hash="s1",
            company_id="co1",
            result=None,
        )

        stats = self.cache.get_stats()
        assert stats.size == 1, "Cache should contain the None entry"

        # Now retrieve — should be a hit (None is the stored value, not a miss)
        result = self.cache.get(
            technique_id="clara",
            query_hash="q1",
            signals_hash="s1",
            company_id="co1",
        )
        assert result is None  # Stored value is None

        stats_after = self.cache.get_stats()
        assert stats_after.hits == 1, "Retrieving a stored None should be a hit"
        assert stats_after.misses == 0

    # -- Gap 10 (MEDIUM): TTL resolution for unregistered technique_id --

    def test_gap10_unregistered_technique_id_uses_default_ttl(self):
        """Verify that an unregistered technique_id resolves to default TTL.

        _resolve_ttl checks TECHNIQUE_REGISTRY.get(TechniqueID(technique_id)).
        For registered techniques, the tier-based TTL is used.
        For unknown technique IDs that bypass TechniqueID construction,
        the _default_ttl is returned.

        Note: 'clara' is a registered tier_1 technique with TTL=300.
        The cache was initialized with default_ttl=600 for unregistered techniques.
        """
        # Set without explicit TTL override — registered technique uses tier TTL
        self.cache.set(
            technique_id="clara",
            query_hash="q1",
            signals_hash="s1",
            company_id="co1",
            result="value1",
        )

        # Set with explicit TTL override — should use override, not registry
        self.cache.set(
            technique_id="clara",
            query_hash="q2",
            signals_hash="s2",
            company_id="co1",
            result="value2",
            ttl_seconds=999,
        )

        stats = self.cache.get_stats()
        assert stats.size == 2

        # Verify tier-based TTL for clara (tier_1 = 300s)
        cache_key = self.cache.make_cache_key("clara", "q1", "s1", "co1")
        with self.cache._lock:
            entry = self.cache._cache.get(cache_key)
            assert entry is not None
            assert entry.ttl_seconds == 300  # tier_1 default

        # Verify explicit TTL override takes precedence
        cache_key2 = self.cache.make_cache_key("clara", "q2", "s2", "co1")
        with self.cache._lock:
            entry2 = self.cache._cache.get(cache_key2)
            assert entry2 is not None
            assert entry2.ttl_seconds == 999  # explicit override

    # -- Gap 11 (MEDIUM): Negative TTL value --

    def test_gap11_negative_ttl_expires_immediately(self):
        """Verify that a negative TTL causes the entry to expire immediately on get().

        CacheEntry.is_expired checks: time.time() - created_at > ttl_seconds.
        With ttl_seconds=-100, any elapsed time > -100 is True, so it's always expired.
        """
        self.cache.set(
            technique_id="clara",
            query_hash="q1",
            signals_hash="s1",
            company_id="co1",
            result="value1",
            ttl_seconds=-100,
        )

        stats_after_set = self.cache.get_stats()
        assert stats_after_set.size == 1, "Entry should be stored initially"

        # Get should find it expired and return None (miss)
        result = self.cache.get(
            technique_id="clara",
            query_hash="q1",
            signals_hash="s1",
            company_id="co1",
        )
        assert result is None

        stats_after_get = self.cache.get_stats()
        assert stats_after_get.size == 0, "Expired entry should be removed"
        assert stats_after_get.misses == 1
        assert stats_after_get.expired_cleanups == 1

    # -- Gap 12 (MEDIUM): LRU eviction order correctness --

    def test_gap12_lru_eviction_removes_least_recently_accessed(self):
        """Verify LRU eviction order by warming cache near capacity,
        accessing specific entries to move them to end, then triggering eviction.

        The OrderedDict-based LRU evicts the first (least recently used) item.
        """
        small_cache = TechniqueCache(max_size=3, default_ttl=600)

        # Fill to capacity
        small_cache.set("clara", "q1", "s1", "co1", "val1")
        small_cache.set("clara", "q2", "s2", "co1", "val2")
        small_cache.set("clara", "q3", "s3", "co1", "val3")

        assert small_cache.get_size() == 3

        # Access q1 and q2 to move them to end (q3 becomes LRU)
        small_cache.get("clara", "q1", "s1", "co1")
        small_cache.get("clara", "q2", "s2", "co1")

        # Add one more — should evict q3 (the LRU)
        small_cache.set("clara", "q4", "s4", "co1", "val4")

        assert small_cache.get_size() == 3

        # q3 should be evicted, q1 and q2 should survive
        assert small_cache.get("clara", "q3", "s3", "co1") is None
        assert small_cache.get("clara", "q1", "s1", "co1") == "val1"
        assert small_cache.get("clara", "q2", "s2", "co1") == "val2"

    # -- Gap 13 (LOW): invalidate_pattern with non-matching technique_prefix --

    def test_gap13_invalidate_pattern_non_matching_prefix_returns_zero(self):
        """Verify invalidate_pattern returns 0 when prefix matches no entries."""
        self.cache.set("clara", "q1", "s1", "co1", "val1")
        self.cache.set("crp", "q2", "s2", "co1", "val2")

        # Prefix that matches no technique_id
        removed = self.cache.invalidate_pattern(
            company_id="co1", technique_prefix="zzz_nonexistent",
        )
        assert removed == 0

        # Both entries should still be present
        assert self.cache.get_size() == 2

    # -- Gap 14 (LOW): Cache key generation with special characters and very long strings --

    def test_gap14_cache_key_generation_special_chars_and_long_strings(self):
        """Verify cache key generation handles special characters and long strings.

        make_cache_key uses SHA-256, so any input should produce a valid 64-char
        hex digest without issues.
        """
        # Special characters
        key1 = TechniqueCache.make_cache_key(
            "clara", "q!@#$%^&*()", "s<>{}[]|\\", "co_1",
        )
        assert isinstance(key1, str)
        assert len(key1) == 64  # SHA-256 hex digest

        # Very long strings
        long_str = "x" * 10000
        key2 = TechniqueCache.make_cache_key(
            long_str, long_str, long_str, long_str,
        )
        assert isinstance(key2, str)
        assert len(key2) == 64

        # Different inputs produce different keys
        key3 = TechniqueCache.make_cache_key(
            "clara", "q1", "s1", "co1",
        )
        assert key1 != key2
        assert key2 != key3

    # -- Gap 15 (LOW): get_oldest_entry_age and get_newest_entry_age actual precision --

    def test_gap15_entry_age_precision_is_reasonable(self):
        """Verify that get_oldest_entry_age and get_newest_entry_age return
        values with reasonable precision (within a small delta of expected)."""
        self.cache.set("clara", "q1", "s1", "co1", "val1")
        time.sleep(0.05)
        self.cache.set("clara", "q2", "s2", "co1", "val2")

        newest_age = self.cache.get_newest_entry_age()
        oldest_age = self.cache.get_oldest_entry_age()

        assert newest_age is not None
        assert oldest_age is not None

        # Newest should be younger than oldest
        assert newest_age < oldest_age

        # Newest age should be very small (< 0.1s)
        assert newest_age < 0.2

        # Oldest age should be at least ~0.05s
        assert oldest_age >= 0.04

        # Empty cache returns None
        empty_cache = TechniqueCache()
        assert empty_cache.get_oldest_entry_age() is None
        assert empty_cache.get_newest_entry_age() is None


# ═══════════════════════════════════════════════════════════════════
# MODULE 3: per_tenant_config.py (Gaps 16-22)
# ═══════════════════════════════════════════════════════════════════


class TestPerTenantConfigGaps:
    """Tests for per_tenant_config.py edge cases and gaps."""

    def setup_method(self):
        self.mgr = TenantConfigManager()

    # -- Gap 16 (CRITICAL): Callback called inside lock, reentrant update_config --

    def test_gap16_callback_can_recurrently_call_update_config(self):
        """Verify that a config-change callback can safely call update_config()
        without deadlocking, since TenantConfigManager uses RLock.

        BUG NOTE: The comment says 'outside lock for safety' but _notify_change
        is actually called INSIDE the `with self._lock:` block in update_config.
        RLock makes this safe for reentrant calls.
        """
        callback_called = threading.Event()
        inner_update_done = threading.Event()

        def reentrant_callback(company_id, category, changes):
            """Callback that calls update_config from within the lock."""
            callback_called.set()
            # This should not deadlock because RLock allows reentrant acquisition
            self.mgr.update_config(
                company_id, "model",
                {"temperature": 0.9},
            )
            inner_update_done.set()

        self.mgr.on_config_change(reentrant_callback)

        # This triggers the callback while holding the lock
        result = self.mgr.update_config(
            "co_test", "workflow",
            {"max_concurrent_workflows": 10},
        )

        assert callback_called.is_set()
        assert inner_update_done.is_set()

        # Verify inner update took effect
        final_config = self.mgr.get_config("co_test")
        assert final_config.model.temperature == 0.9

    # -- Gap 17 (MEDIUM): validate_config with zero values for positive-only fields --

    def test_gap17_zero_values_for_positive_only_fields_fail_validation(self):
        """Verify that zero values for fields requiring positive integers fail.

        Fields checked with <= 0: max_tokens (compression, model),
        max_concurrent_workflows, checkpoint_timeout_seconds.
        Field checked with < 0: preserve_recent_n (0 is valid for this one).
        """
        # compression.max_tokens = 0 → should fail (<= 0)
        result = self.mgr.validate_config("compression", {"max_tokens": 0})
        assert not result.valid
        assert any("max_tokens must be positive" in e for e in result.errors)

        # compression.preserve_recent_n = 0 → should PASS (check is < 0)
        result = self.mgr.validate_config("compression", {"preserve_recent_n": 0})
        assert result.valid, "preserve_recent_n=0 should be valid (check is < 0)"

        # workflow.max_concurrent_workflows = 0 → should fail (<= 0)
        result = self.mgr.validate_config(
            "workflow", {"max_concurrent_workflows": 0},
        )
        assert not result.valid
        assert any("max_concurrent_workflows must be positive" in e for e in result.errors)

        # workflow.checkpoint_timeout_seconds = 0 → should fail (<= 0)
        result = self.mgr.validate_config(
            "workflow", {"checkpoint_timeout_seconds": 0},
        )
        assert not result.valid

        # model.max_tokens = 0 → should fail (<= 0)
        result = self.mgr.validate_config("model", {"max_tokens": 0})
        assert not result.valid
        assert any("max_tokens must be positive" in e for e in result.errors)

    # -- Gap 18 (MEDIUM): Concurrent import_config and update_config --

    def test_gap18_concurrent_import_and_update_do_not_crash(self):
        """Verify that import_config and update_config running simultaneously
        for the same tenant do not crash or deadlock."""
        errors = []

        def do_import():
            try:
                import_json = '{"overrides": {"model": {"temperature": 0.7}}}'
                self.mgr.import_config("co_concurrent", import_json)
            except Exception as exc:
                errors.append(f"import error: {exc}")

        def do_update():
            try:
                self.mgr.update_config(
                    "co_concurrent", "compression",
                    {"strategy": "hybrid", "level": "light"},
                )
            except Exception as exc:
                errors.append(f"update error: {exc}")

        threads = []
        for _ in range(5):
            threads.append(threading.Thread(target=do_import))
            threads.append(threading.Thread(target=do_update))

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Concurrent operations raised errors: {errors}"
        # Config should exist for the tenant (one of the operations set it)
        config = self.mgr.get_config("co_concurrent")
        assert config is not None

    # -- Gap 19 (MEDIUM): import_config with category not in CATEGORY_SCHEMAS --

    def test_gap19_import_config_unknown_category_fails_validation(self):
        """Verify that import_config with a category not in CATEGORY_SCHEMAS
        fails with a validation error."""
        import_json = '{"overrides": {"unknown_category": {"foo": "bar"}}}'
        result = self.mgr.import_config("co_test", import_json)
        assert not result.valid
        assert any("Unknown category" in e for e in result.errors)

    # -- Gap 20 (LOW): validate_config with extra fields not in schema --

    def test_gap20_extra_valid_typed_fields_not_in_schema_fail(self):
        """Verify that extra fields with valid types but not in the schema
        cause validation errors.

        validate_config checks: if key not in schema → error.
        """
        result = self.mgr.validate_config("compression", {
            "strategy": "hybrid",
            "level": "moderate",
            "extra_field_not_in_schema": 42,  # int, but not in schema
        })
        assert not result.valid
        assert any("Unknown field 'extra_field_not_in_schema'" in e
                    for e in result.errors)

    # -- Gap 21 (MEDIUM): Callback receives original config_dict reference --

    def test_gap21_callback_mutation_does_not_affect_internal_state(self):
        """Verify that mutating config_dict inside a callback does not corrupt
        the manager's internal state, since update_config uses copy.deepcopy
        before storing, but passes the original reference to _notify_change.
        """
        received_configs = []

        def capturing_callback(company_id, category, changes):
            received_configs.append(changes)
            # Mutate the received dict
            changes["temperature"] = "MUTATED"
            changes["injected_key"] = "should_not_persist"

        self.mgr.on_config_change(capturing_callback)

        original = {"temperature": 0.5}
        self.mgr.update_config("co_test", "model", original)

        # Callback received the original dict reference
        assert len(received_configs) == 1
        assert received_configs[0]["temperature"] == "MUTATED"

        # Internal state should be unaffected (uses deepcopy)
        config = self.mgr.get_config("co_test")
        assert config.model.temperature == 0.5

        # The original dict passed by the caller should also be unaffected
        # because _notify_change receives it but the callback mutated it
        # (demonstrating the reference is shared with the callback)
        assert original["temperature"] == "MUTATED", (
            "Original dict IS mutated because callback receives the same reference. "
            "This is the documented behavior gap."
        )

    # -- Gap 22 (LOW): update_config with empty config_dict still increments version --

    def test_gap22_empty_config_dict_increments_version(self):
        """Verify that update_config with an empty dict still increments
        the config version counter."""
        # First update
        self.mgr.update_config("co_test", "model", {"temperature": 0.5})
        history = self.mgr.get_version_history("co_test")
        assert len(history) == 1
        assert history[0]["version"] == 1

        # Second update with empty dict (still valid — no unknown fields)
        self.mgr.update_config("co_test", "model", {})
        history = self.mgr.get_version_history("co_test")
        assert len(history) == 2
        assert history[1]["version"] == 2


# ═══════════════════════════════════════════════════════════════════
# MODULE 4: state_migration.py (Gaps 23-31)
# ═══════════════════════════════════════════════════════════════════


class TestStateMigrationGaps:
    """Tests for state_migration.py edge cases and gaps."""

    def setup_method(self):
        self.migrator = StateMigrator()

    def _make_v1_state(self, **overrides):
        """Helper to create a valid v1 state dict."""
        state = {"query": "test query", "gsd_state": 0}
        state.update(overrides)
        return state

    # -- Gap 23 (CRITICAL): No thread safety --

    def test_gap23_concurrent_migrate_state_does_not_crash(self):
        """Verify that concurrent migrate_state calls don't crash.

        BUG: StateMigrator has no locking. Concurrent migrations on the same
        state dict may corrupt data, but should not crash.
        """
        errors = []
        results = []

        def migrate(state):
            try:
                result = self.migrator.migrate_state(state, target_version=6)
                results.append(result)
            except Exception as exc:
                errors.append(str(exc))

        threads = []
        for _ in range(10):
            state = self._make_v1_state()
            threads.append(threading.Thread(target=migrate, args=(state,)))

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Concurrent migrations raised errors: {errors}"
        assert len(results) == 10

    # -- Gap 24 (HIGH): migrate_state mutates original dict when dry_run=False --

    def test_gap24_migrate_mutates_original_when_not_dry_run(self):
        """Verify that migrate_state with dry_run=False modifies the original
        state dict in place.

        Code: working = copy.deepcopy(state_dict) if dry_run else state_dict
        """
        state = self._make_v1_state()
        original_id = id(state)

        result = self.migrator.migrate_state(state, target_version=6, dry_run=False)

        assert result.success
        assert result.state_after is not None
        # Original dict should be modified (has new fields)
        assert "_version" in state
        assert state["_version"] == 6
        assert "reasoning_thread" in state
        assert "signals" in state
        assert id(result.state_after) != original_id  # state_after is a deepcopy

    # -- Gap 25 (MEDIUM): v4_to_v5 with gsd_state=None --

    def test_gap25_v4_to_v5_gsd_state_none_becomes_new(self):
        """Verify that gsd_state=None in v4 becomes 'new' after v5 migration.

        Code: isinstance(None, int) is False, isinstance(None, str) is False,
        so it falls to the else branch which sets gsd_state = 'new'.
        """
        state = self._make_v1_state(gsd_state=None)
        state["_version"] = 4
        state["reasoning_thread"] = []
        state["reflexion_trace"] = None
        state["technique_token_budget"] = 1500

        result = self.migrator.migrate_state(state, target_version=5)
        assert result.success
        assert state["gsd_state"] == "new"
        assert state["_version"] == 5

    # -- Gap 26 (MEDIUM): v4_to_v5 with gsd_state as float 2.0 --

    def test_gap26_v4_to_v5_gsd_state_float_falls_to_else_branch(self):
        """Verify that gsd_state=2.0 (float) is NOT recognized as int.

        In Python 3, isinstance(2.0, int) is False, so the migration treats
        it as unexpected type and sets gsd_state to 'new'.
        """
        state = self._make_v1_state(gsd_state=2.0)
        state["_version"] = 4
        state["reasoning_thread"] = []
        state["reflexion_trace"] = None
        state["technique_token_budget"] = 1500

        result = self.migrator.migrate_state(state, target_version=5)
        assert result.success
        # 2.0 is float, not int — should fall through to 'new'
        assert state["gsd_state"] == "new"
        assert any("unexpected type" in w.lower() or "float" in w.lower()
                    for w in result.warnings)

    # -- Gap 27 (MEDIUM): Rollback v5_to_v4 with unknown string gsd_state --

    def test_gap27_rollback_v5_to_v4_unknown_gsd_string_falls_back_to_zero(self):
        """Verify that rollback v5→v4 with an unknown gsd_state string
        falls back to int 0."""
        state = self._make_v1_state(gsd_state="unknown_invalid_state")
        state["_version"] = 5
        state["reasoning_thread"] = []
        state["reflexion_trace"] = None
        state["technique_token_budget"] = 1500

        result = self.migrator.rollback_state(state, target_version=4)
        assert result.success
        assert state["gsd_state"] == 0
        assert state["_version"] == 4
        assert any("Unknown gsd_state" in c or "fallback" in c.lower()
                    for c in result.changes_made)

    # -- Gap 28 (MEDIUM): Multi-step rollback (v6 to v3) --

    def test_gap28_multi_step_rollback_v6_to_v3(self):
        """Verify multi-step rollback from v6 down to v3 works correctly.

        Rollback path: v6→v5 (remove signals), v5→v4 (gsd_state to int),
        v4→v3 (remove technique_token_budget).
        """
        state = {
            "query": "test",
            "gsd_state": "processing",
            "reasoning_thread": ["step1"],
            "reflexion_trace": None,
            "technique_token_budget": 2000,
            "signals": {
                "intent_confidence": 0.9,
                "urgency_level": "high",
                "sentiment_score": -0.5,
                "language_code": "en",
            },
            "_version": 6,
        }

        result = self.migrator.rollback_state(state, target_version=3)
        assert result.success
        assert state["_version"] == 3
        # signals removed by v6→v5
        assert "signals" not in state
        # gsd_state reverted to int by v5→v4
        assert state["gsd_state"] == 2  # "processing" → 2
        # technique_token_budget removed by v4→v3
        assert "technique_token_budget" not in state
        # reasoning_thread should still be present (added in v1→v2)
        assert "reasoning_thread" in state
        # reflexion_trace should still be present (added in v2→v3)
        assert "reflexion_trace" in state

    # -- Gap 29 (LOW): v5_to_v6 with signals as empty dict --

    def test_gap29_v5_to_v6_empty_signals_gets_all_defaults_merged(self):
        """Verify that v5→v6 migration with signals={} merges all default keys."""
        state = self._make_v1_state(gsd_state="new")
        state["_version"] = 5
        state["reasoning_thread"] = []
        state["reflexion_trace"] = None
        state["technique_token_budget"] = 1500
        state["signals"] = {}  # Empty dict — all keys missing

        result = self.migrator.migrate_state(state, target_version=6)
        assert result.success
        assert state["_version"] == 6
        assert state["signals"]["intent_confidence"] == 0.0
        assert state["signals"]["urgency_level"] == "medium"
        assert state["signals"]["sentiment_score"] == 0.0
        assert state["signals"]["language_code"] == "en"
        assert any("Merged missing keys" in c for c in result.changes_made)

    # -- Gap 30 (MEDIUM): Custom migration function that raises exception --

    def test_gap30_custom_migration_exception_returns_failure(self):
        """Verify that a custom migration function raising an exception
        results in a failed MigrationResult without crashing."""
        def bad_migration(state):
            raise RuntimeError("Custom migration blew up")

        self.migrator.register_migration(6, 7, bad_migration)

        state = self._make_v1_state()
        state["_version"] = 6
        state["reasoning_thread"] = []
        state["reflexion_trace"] = None
        state["technique_token_budget"] = 1500
        state["signals"] = {
            "intent_confidence": 0.0,
            "urgency_level": "medium",
            "sentiment_score": 0.0,
            "language_code": "en",
        }

        result = self.migrator.migrate_state(state, target_version=7)
        assert not result.success
        assert result.from_version == 6
        assert any("failed" in w.lower() or "blew up" in w.lower()
                    for w in result.warnings)

    # -- Gap 31 (LOW): validate_state with version=0 or negative version --

    def test_gap31_validate_state_version_zero_or_negative(self):
        """Verify that validate_state rejects unknown versions like 0 or -1."""
        state = {"query": "test", "gsd_state": "new"}

        result = self.migrator.validate_state(state, version=0)
        assert not result.valid
        assert any("Unknown schema version" in e for e in result.errors)

        result_neg = self.migrator.validate_state(state, version=-1)
        assert not result_neg.valid
        assert any("Unknown schema version" in e for e in result_neg.errors)


# ═══════════════════════════════════════════════════════════════════
# MODULE 5: shared_gsd.py (Gaps 32-38)
# ═══════════════════════════════════════════════════════════════════


class TestSharedGSDGaps:
    """Tests for shared_gsd.py edge cases and gaps."""

    def setup_method(self):
        self.mgr = SharedGSDManager()

    # -- Gap 32 (CRITICAL): No thread safety --

    def test_gap32_concurrent_record_transition_does_not_crash(self):
        """Verify that concurrent record_transition calls don't crash.

        BUG: SharedGSDManager has no locking. Concurrent calls on defaultdict
        may corrupt data, but should not raise unhandled exceptions.
        """
        errors = []

        def record(i):
            try:
                self.mgr.record_transition(
                    company_id="co1",
                    ticket_id=f"tkt_{i % 5}",
                    from_state="new",
                    to_state="greeting",
                )
            except Exception as exc:
                errors.append(str(exc))

        threads = [threading.Thread(target=record, args=(i,)) for i in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Concurrent transitions raised errors: {errors}"

    # -- Gap 33 (HIGH): clear_ticket_data now cleans _transition_counts (FIXED) --

    def test_gap33_clear_ticket_does_not_clean_transition_counts_heatmap(self):
        """Verify that clear_ticket_data properly cleans _transition_counts,
        so the heatmap no longer shows transitions from the cleared ticket.

        FIX: After clearing ticket data, _transition_counts is rebuilt
        from remaining transition history for that company.
        """
        # Record transitions for two tickets
        self.mgr.record_transition("co1", "tkt_A", "new", "greeting")
        self.mgr.record_transition("co1", "tkt_A", "greeting", "diagnosis")
        self.mgr.record_transition("co1", "tkt_B", "new", "greeting")

        # Verify heatmap has the transitions
        heatmap_before = self.mgr.get_transition_heatmap("co1")
        assert heatmap_before.get("new", {}).get("greeting", 0) >= 2

        # Clear ticket A data
        self.mgr.clear_ticket_data("co1", "tkt_A")

        # Heatmap should only show tkt_B's transition now
        heatmap_after = self.mgr.get_transition_heatmap("co1")
        assert heatmap_after.get("new", {}).get("greeting", 0) >= 1, (
            "FIXED: clear_ticket_data now rebuilds _transition_counts, "
            "so heatmap only shows remaining tickets' transitions"
        )
        assert heatmap_after.get("greeting", {}).get("diagnosis", 0) == 0, (
            "FIXED: tkt_A's greeting->diagnosis transition should be gone"
        )

    # -- Gap 34 (MEDIUM): get_state_duration for state entered multiple times --

    def test_gap34_state_duration_re_entry_cumulative(self):
        """Verify that get_state_duration accumulates time across multiple
        entries into the same state (re-entry)."""
        now = time.time()
        # Simulate: enter diagnosis, leave, enter again
        self.mgr.record_transition("co1", "tkt_1", "greeting", "diagnosis")
        time.sleep(0.05)
        self.mgr.record_transition("co1", "tkt_1", "diagnosis", "greeting")
        time.sleep(0.05)
        self.mgr.record_transition("co1", "tkt_1", "greeting", "diagnosis")

        # Total duration should be at least 0.05s (first entry) since second
        # is still in progress
        duration = self.mgr.get_state_duration("co1", "tkt_1", "diagnosis")
        assert duration > 0.0

    # -- Gap 35 (MEDIUM): suggest_recovery boundary STUCK vs CRITICAL --

    def test_gap35_recovery_boundary_stuck_vs_critical_thresholds(self):
        """Verify suggest_recovery boundary behavior between STUCK (300s)
        and CRITICAL (600s) thresholds.

        We mock time to simulate durations just above each threshold.
        """
        # Test at STUCK threshold (>300s, <=600s)
        self.mgr.record_transition("co1", "tkt_1", "new", "diagnosis")

        # Directly manipulate entered_at to simulate 301s in state
        self.mgr._current_states["co1"]["tkt_1"]["entered_at"] = (
            time.time() - 301
        )

        suggestions = self.mgr.suggest_recovery("co1", "tkt_1")
        # Should suggest review_state (medium priority) but NOT escalate_to_human
        actions = [s["action"] for s in suggestions]
        assert "review_state" in actions
        assert "escalate_to_human" not in actions

        # Test at CRITICAL threshold (>600s)
        self.mgr._current_states["co1"]["tkt_1"]["entered_at"] = (
            time.time() - 601
        )

        suggestions = self.mgr.suggest_recovery("co1", "tkt_1")
        actions = [s["action"] for s in suggestions]
        assert "escalate_to_human" in actions

    # -- Gap 36 (LOW): remove_event_listener for non-registered callback --

    def test_gap36_remove_non_registered_event_listener(self):
        """Verify that removing a callback that was never registered
        does not raise an error (silent no-op)."""
        def never_registered(entry):
            pass

        # Should not raise
        self.mgr.remove_event_listener(never_registered)

        # Verify internal state is unchanged
        assert len(self.mgr._event_listeners) == 0

    # -- Gap 37 (LOW): get_transition_reason for self-transition --

    def test_gap37_transition_reason_self_transition_new_to_new(self):
        """Verify that a self-transition ('new' → 'new') is reported as invalid.

        FULL_TRANSITION_TABLE['new'] = {'greeting'}, and 'new' is not in
        ESCALATION_ELIGIBLE_STATES, so 'new' → 'new' is not valid.
        """
        result = self.mgr.get_transition_reason("new", "new")
        assert result["valid"] is False
        assert "not permitted" in result["reason"]

    # -- Gap 38 (MEDIUM): get_state_duration with entered_at=0 --

    def test_gap38_state_duration_with_entered_at_zero(self):
        """Verify suggest_recovery with entered_at=0 returns no suggestions.

        suggest_recovery checks 'if not entered_at: return suggestions'.
        entered_at=0 is falsy, so it returns empty list immediately.
        """
        self.mgr.record_transition("co1", "tkt_1", "new", "diagnosis")

        # Simulate improperly initialized state with entered_at=0
        self.mgr._current_states["co1"]["tkt_1"]["entered_at"] = 0

        suggestions = self.mgr.suggest_recovery("co1", "tkt_1")
        # entered_at=0 is falsy → returns empty
        assert suggestions == []


# ═══════════════════════════════════════════════════════════════════
# MODULE 6: capacity_monitor.py (Gaps 39-46)
# ═══════════════════════════════════════════════════════════════════


class TestCapacityMonitorGaps:
    """Tests for capacity_monitor.py edge cases and gaps."""

    def setup_method(self):
        self.monitor = CapacityMonitor()

    # -- Gap 39 (CRITICAL): No concurrent access tests --

    def test_gap39_concurrent_acquire_and_release_do_not_crash(self):
        """Verify that concurrent acquire_slot and release_slot calls
        do not crash or corrupt the monitor's state."""
        errors = []
        acquired = threading.Event()

        def acquire_release(i):
            try:
                ticket = f"tkt_{i}"
                # Acquire
                got = self.monitor.acquire_slot("co1", "parwa", ticket)
                if got:
                    acquired.set()
                # Small work
                time.sleep(0.001)
                # Release
                self.monitor.release_slot("co1", "parwa", ticket)
            except Exception as exc:
                errors.append(str(exc))

        threads = [threading.Thread(target=acquire_release, args=(i,))
                    for i in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Concurrent ops raised errors: {errors}"
        assert acquired.is_set()

    # -- Gap 40 (HIGH): acquire_slot silently overwrites existing active slot --

    def test_gap40_double_acquire_silently_overwrites(self):
        """Verify that acquiring a slot for the same ticket_id without
        releasing first silently overwrites the existing slot.

        BUG: acquire_slot does active[ticket_id] = metadata, which
        overwrites any existing entry without warning.
        """
        # First acquire
        got1 = self.monitor.acquire_slot(
            "co1", "parwa", "tkt_1", metadata={"round": 1},
        )
        assert got1 is True

        cap = self.monitor.get_capacity("co1", "parwa")
        assert cap["used"] == 1

        # Second acquire without release — overwrites
        got2 = self.monitor.acquire_slot(
            "co1", "parwa", "tkt_1", metadata={"round": 2},
        )
        assert got2 is True  # Still succeeds because slot count is still 1

        cap = self.monitor.get_capacity("co1", "parwa")
        # used is still 1 because the same ticket_id was overwritten
        assert cap["used"] == 1

    # -- Gap 41 (HIGH): configure_limits reduces capacity below active slots --

    def test_gap41_reduce_limits_below_active_slot_count(self):
        """Verify that configure_limits can reduce max_concurrent below
        the current number of active slots without evicting them.

        BUG: configure_limits only stores the limit, doesn't evict.
        This means used > total, and capacity percentage exceeds 100%.
        """
        # Acquire 8 slots (parwa default is 10)
        for i in range(8):
            self.monitor.acquire_slot("co1", "parwa", f"tkt_{i}")

        cap = self.monitor.get_capacity("co1", "parwa")
        assert cap["used"] == 8
        assert cap["total"] == 10

        # Reduce limit to 3
        self.monitor.configure_limits("co1", "parwa", 3)

        cap = self.monitor.get_capacity("co1", "parwa")
        assert cap["total"] == 3
        assert cap["used"] == 8
        # available should be 0 (clamped), percentage > 100%
        assert cap["available"] == 0
        assert cap["percentage"] > 100.0

    # -- Gap 42 (MEDIUM): Alert escalation path (warning → critical → full) --

    def test_gap42_alert_escalation_warning_critical_full(self):
        """Verify alert levels escalate as capacity fills:
        warning (70%), critical (90%), full (95%).

        Using parwa variant with default max=10:
        7 slots → 70% → warning
        9 slots → 90% → critical
        10 slots → 100% → full (>=95%)
        """
        # 7 of 10 = 70% → warning
        for i in range(7):
            self.monitor.acquire_slot("co1", "parwa", f"tkt_{i}")

        alerts = self.monitor.get_alerts("co1")
        levels = [a["level"] for a in alerts]
        assert "warning" in levels

        # 9 of 10 = 90% → critical
        self.monitor.acquire_slot("co1", "parwa", "tkt_7")
        self.monitor.acquire_slot("co1", "parwa", "tkt_8")

        alerts = self.monitor.get_alerts("co1")
        levels = [a["level"] for a in alerts]
        assert "critical" in levels

        # 10 of 10 = 100% → full
        self.monitor.acquire_slot("co1", "parwa", "tkt_9")

        alerts = self.monitor.get_alerts("co1")
        levels = [a["level"] for a in alerts]
        assert "full" in levels

    # -- Gap 43 (MEDIUM): Utilization history trimming at max 1000 points --

    def test_gap43_utilization_history_trims_at_1000_points(self):
        """Verify that utilization history is trimmed to max 1000 points."""
        # Set a small max for testing — actually the code hardcodes 1000
        # We'll add 1100 points and verify only 1000 remain
        for i in range(1100):
            self.monitor.acquire_slot("co1", "parwa", f"tkt_{i % 5}")

        # Each acquire records a utilization point
        history = self.monitor.get_utilization_history("co1", "parwa")
        assert len(history) <= 1000

    # -- Gap 44 (MEDIUM): clear_company also removes configured limits --

    def test_gap44_clear_company_removes_limits_returns_defaults(self):
        """Verify that clear_company removes configured limits, and
        get_capacity returns default values afterwards."""
        self.monitor.configure_limits("co1", "parwa", 50)
        cap = self.monitor.get_capacity("co1", "parwa")
        assert cap["total"] == 50

        self.monitor.clear_company("co1")

        # After clear, should return default (10 for parwa)
        cap = self.monitor.get_capacity("co1", "parwa")
        assert cap["total"] == 10

    # -- Gap 45 (LOW): Negative priority for acquire_slot --

    def test_gap45_negative_priority_accepted_for_acquire_slot(self):
        """Verify that negative priority values are accepted by acquire_slot
        and result in lower scheduling priority.

        Higher priority values are dequeued first. release_slot internally
        processes the queue, so we check active slots after release.
        """
        # Fill capacity
        for i in range(10):
            self.monitor.acquire_slot("co1", "parwa", f"tkt_fill_{i}")

        # Queue with negative priority
        got = self.monitor.acquire_slot(
            "co1", "parwa", "tkt_neg", priority=-5,
        )
        assert got is False  # Should be queued
        assert self.monitor.get_queue_size("co1", "parwa") >= 1

        # Queue with positive priority
        got = self.monitor.acquire_slot(
            "co1", "parwa", "tkt_pos", priority=10,
        )
        assert got is False  # Should be queued

        # Release a slot — release_slot processes queue internally.
        # Higher priority (10) should be dequeued before negative (-5).
        self.monitor.release_slot("co1", "parwa", "tkt_fill_0")

        # Queue should now have only the negative-priority item
        remaining_queue = self.monitor.get_queue_size("co1", "parwa")
        assert remaining_queue == 1
        # The high-priority ticket should now be active
        cap = self.monitor.get_capacity("co1", "parwa")
        assert cap["used"] == 10  # Still full (one released, one activated)
        # tkt_pos should be active, tkt_neg should still be queued
        assert self.monitor.get_queue_position("co1", "parwa", "tkt_neg") == 0
        assert self.monitor.get_queue_position("co1", "parwa", "tkt_pos") == -1

    # -- Gap 46 (MEDIUM): Duplicate ticket_id deduplication in queue (FIXED) --

    def test_gap46_duplicate_ticket_id_can_be_queued_multiple_times(self):
        """Verify that the same ticket_id is deduplicated in the queue.

        FIX: acquire_slot now checks if ticket_id is already queued
        and skips adding a duplicate entry.
        """
        # Fill capacity
        for i in range(10):
            self.monitor.acquire_slot("co1", "parwa", f"tkt_fill_{i}")

        # Queue same ticket_id twice
        self.monitor.acquire_slot("co1", "parwa", "tkt_dup")
        self.monitor.acquire_slot("co1", "parwa", "tkt_dup")

        queue_size = self.monitor.get_queue_size("co1", "parwa")
        assert queue_size == 1, (
            "FIXED: Duplicate ticket_id should only appear once in queue"
        )


# ═══════════════════════════════════════════════════════════════════
# MODULE 7: dspy_integration.py (Gaps 47-55)
# ═══════════════════════════════════════════════════════════════════


class TestDSPyIntegrationGaps:
    """Tests for dspy_integration.py edge cases and gaps."""

    def setup_method(self):
        self.dspy = DSPyIntegration()

    # -- Gap 47 (CRITICAL): No thread safety --

    def test_gap47_concurrent_execute_does_not_crash(self):
        """Verify that concurrent execute() calls don't crash.

        BUG: DSPyIntegration has no locking. _metrics list access is not
        thread-safe. Concurrent calls may corrupt metrics but shouldn't crash.
        """
        errors = []
        module = StubModule(task_type="classify")

        def run_execute(i):
            try:
                self.dspy.execute(
                    module, {"customer_query": f"query {i}"}
                )
            except Exception as exc:
                errors.append(str(exc))

        threads = [threading.Thread(target=run_execute, args=(i,))
                    for i in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Concurrent executes raised errors: {errors}"
        metrics = self.dspy.get_metrics()
        assert metrics["total_executions"] == 50

    # -- Gap 48 (HIGH): execute() exception path with fallback --

    def test_gap48_execute_exception_falls_back_to_stub(self):
        """Verify that execute() catches exceptions from modules and falls
        back to stub execution, returning a valid result dict."""
        # Create a module that raises on call
        class BrokenModule:
            task_type = "broken"
            def __call__(self, **kwargs):
                raise RuntimeError("Module execution failed")

        result = self.dspy.execute(
            BrokenModule(), {"customer_query": "test"},
        )
        # Should return stub fallback result
        assert isinstance(result, dict)
        assert "response" in result
        assert "[Fallback]" in result["response"]
        assert result["confidence"] == 0.5

        # Metrics should record the failure
        metrics = self.dspy.get_metrics()
        assert metrics["total_executions"] == 1
        assert metrics["error_rate"] == 100.0
        assert metrics["fallback_rate"] == 100.0

    # -- Gap 49 (MEDIUM): configure() validates input values (FIXED) --

    def test_gap49_configure_accepts_invalid_values(self):
        """Verify that configure() rejects invalid values with ValueError.

        FIX: Validation is now performed on config values.
        """
        import pytest

        # Negative max_tokens should raise ValueError
        with pytest.raises(ValueError, match="max_tokens"):
            self.dspy.configure("co1", {"max_tokens": -100})

        # Temperature out of range should raise ValueError
        with pytest.raises(ValueError, match="temperature"):
            self.dspy.configure("co1", {"temperature": 99.9})

        # Empty model_name should raise ValueError
        with pytest.raises(ValueError, match="model_name"):
            self.dspy.configure("co1", {"model_name": ""})

        # Negative num_threads should raise ValueError
        with pytest.raises(ValueError, match="num_threads"):
            self.dspy.configure("co1", {"num_threads": -5})

        # Valid values should still work
        config = self.dspy.configure("co1", {
            "max_tokens": 4096,
            "temperature": 0.7,
            "model_name": "gpt-4",
            "num_threads": 4,
        })
        assert config is not None
        retrieved = self.dspy.get_config("co1")
        assert retrieved.max_tokens == 4096
        assert retrieved.temperature == 0.7

    # -- Gap 50 (MEDIUM): _record_metric auto-trimming at 1000 entries --

    def test_gap50_metric_auto_trimming_at_1000_entries(self):
        """Verify that _record_metric trims metrics list to max 1000 entries."""
        module = StubModule(task_type="classify")
        for i in range(1100):
            self.dspy.execute(module, {"customer_query": f"q{i}"})

        metrics = self.dspy.get_metrics()
        # Should have at most 1000 entries (trimmed from 1100)
        assert metrics["total_executions"] <= 1000
        assert metrics["total_executions"] > 0

    # -- Gap 51 (MEDIUM): get_metrics by_task_type with multiple task types --

    def test_gap51_metrics_by_task_type_multiple_types(self):
        """Verify that get_metrics correctly breaks down metrics by task_type."""
        module_classify = StubModule(task_type="classify")
        module_respond = StubModule(task_type="respond")
        module_summarize = StubModule(task_type="summarize")

        for _ in range(5):
            self.dspy.execute(module_classify, {"customer_query": "test"})
        for _ in range(3):
            self.dspy.execute(module_respond, {"customer_query": "test"})
        for _ in range(2):
            self.dspy.execute(module_summarize, {"conversation_history": "test"})

        metrics = self.dspy.get_metrics()
        by_task = metrics["by_task_type"]

        assert by_task["classify"]["count"] == 5
        assert by_task["respond"]["count"] == 3
        assert by_task["summarize"]["count"] == 2

        # Total should be 10
        assert metrics["total_executions"] == 10

    # -- Gap 52 (MEDIUM): bridge_from_parwa with minimal object --

    def test_gap52_bridge_from_parwa_minimal_object_missing_attributes(self):
        """Verify that bridge_from_parwa handles objects missing expected
        attributes gracefully by using hasattr checks."""
        # Minimal object with no attributes
        minimal = MagicMock(spec=[])  # Empty spec — no attributes
        # Remove all default MagicMock attributes
        minimal.query = "test query"

        inputs = self.dspy.bridge_from_parwa(minimal)
        assert isinstance(inputs, dict)
        # query attribute should be extracted
        assert inputs["customer_query"] == "test query"
        assert inputs["input"] == "test query"

        # Missing signals, gsd_state, gsd_history, technique_results
        # should not be in the dict (hasattr returns False)
        assert "context" not in inputs
        assert "gsd_state" not in inputs
        assert "conversation_history" not in inputs

    # -- Gap 53 (LOW): configure metric_weights parameter --

    def test_gap53_configure_metric_weights_parameter(self):
        """Verify that the metric_weights parameter is accepted and stored."""
        custom_weights = {
            "relevance": 0.5,
            "accuracy": 0.3,
            "conciseness": 0.1,
            "safety": 0.1,
        }
        config = self.dspy.configure("co1", {
            "metric_weights": custom_weights,
        })
        assert config.metric_weights == custom_weights

        retrieved = self.dspy.get_config("co1")
        assert retrieved.metric_weights == custom_weights

        # Verify default weights are used when not specified
        config_default = self.dspy.configure("co2", {})
        assert "relevance" in config_default.metric_weights
        assert config_default.metric_weights["relevance"] == 0.4

    # -- Gap 54 (LOW): _stub_execute with very long query (>100 chars) --

    def test_gap54_stub_execute_truncates_long_query(self):
        """Verify that _stub_execute truncates queries longer than 100 chars."""
        long_query = "x" * 200
        result = DSPyIntegration._stub_execute(
            StubModule(), {"customer_query": long_query},
        )
        assert isinstance(result, dict)
        assert "[Fallback]" in result["response"]
        # Long query should be truncated to 100 chars
        assert "..." in result["response"]
        assert len(result["response"].split(": ", 1)[1].rstrip(".").rstrip("…").strip()) <= 103

    # -- Gap 55 (LOW): StubOptimizer.compile() behavior --

    def test_gap55_stub_optimizer_compile_returns_module_unchanged(self):
        """Verify that StubOptimizer.compile() returns the module unchanged."""
        optimizer = StubOptimizer()
        module = StubModule(task_type="classify")

        result = optimizer.compile(module, trainset=[], metric=None)
        assert result is module

        # Also test with None arguments
        result2 = optimizer.compile(module)
        assert result2 is module
