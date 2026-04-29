"""
Tests for TechniqueMetricsCollector (Week 10 Day 3)

Comprehensive unit tests covering:
- Single and multiple execution recording
- Per-variant isolation
- Per-company isolation
- Time-windowed metrics
- Percentile calculations (p50, p95, p99)
- Leaderboard sorting
- Reset functionality
- Stale entry cleanup
- Concurrent recording thread safety
- Edge cases (no data, empty stats)
"""

import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest
from app.core.technique_metrics import (
    TIME_WINDOWS_SECONDS,
    VALID_VARIANTS,
    ExecutionRecord,
    ExecutionStatus,
    LeaderboardEntry,
    TechniqueMetricsCollector,
    TechniqueStats,
    VariantSummary,
)
from app.core.technique_router import TechniqueID

# ── Fixtures ──────────────────────────────────────────────────────


@pytest.fixture
def collector():
    """Fresh collector for each test."""
    return TechniqueMetricsCollector()


@pytest.fixture
def populated_collector(collector):
    """Collector with sample data across multiple techniques."""
    # Company A
    for i in range(10):
        collector.record_execution(
            technique_id=TechniqueID.CLARA,
            variant="parwa",
            company_id="company_a",
            status="success",
            tokens_used=50 + i * 10,
            exec_time_ms=100.0 + i * 5,
        )
    # Company A failures
    for i in range(3):
        collector.record_execution(
            technique_id=TechniqueID.CLARA,
            variant="parwa",
            company_id="company_a",
            status="failure",
            tokens_used=30,
            exec_time_ms=200.0,
        )
    # Company B
    for i in range(5):
        collector.record_execution(
            technique_id=TechniqueID.CLARA,
            variant="mini_parwa",
            company_id="company_b",
            status="success",
            tokens_used=40 + i * 5,
            exec_time_ms=80.0 + i * 3,
        )
    # Different technique
    for i in range(7):
        collector.record_execution(
            technique_id=TechniqueID.CHAIN_OF_THOUGHT,
            variant="high_parwa",
            company_id="company_a",
            status="success",
            tokens_used=350 + i * 20,
            exec_time_ms=3000.0 + i * 100,
        )
    for i in range(2):
        collector.record_execution(
            technique_id=TechniqueID.CHAIN_OF_THOUGHT,
            variant="high_parwa",
            company_id="company_a",
            status="timeout",
            tokens_used=400,
            exec_time_ms=5000.0,
        )
    # Timeout/error records
    collector.record_execution(
        technique_id=TechniqueID.REACT,
        variant="high_parwa",
        company_id="company_a",
        status="timeout",
        tokens_used=300,
        exec_time_ms=5000.0,
    )
    collector.record_execution(
        technique_id=TechniqueID.REACT,
        variant="parwa",
        company_id="company_a",
        status="error",
        tokens_used=0,
        exec_time_ms=10.0,
    )
    return collector


# ── 1. Single Execution Recording ────────────────────────────────


class TestSingleExecution:
    """Tests for recording a single execution."""

    def test_record_basic_success(self, collector):
        collector.record_execution(
            technique_id="clara",
            variant="parwa",
            company_id="co1",
            status="success",
            tokens_used=100,
            exec_time_ms=50.0,
        )
        stats = collector.get_technique_stats("clara", "co1")
        assert stats is not None
        assert stats.total_executions == 1
        assert stats.success_count == 1
        assert stats.failure_count == 0
        assert stats.total_tokens == 100
        assert stats.total_exec_time_ms == 50.0

    def test_record_with_technique_id_enum(self, collector):
        collector.record_execution(
            technique_id=TechniqueID.GST,
            company_id="co1",
        )
        stats = collector.get_technique_stats(TechniqueID.GST, "co1")
        assert stats is not None
        assert stats.total_executions == 1

    def test_record_failure(self, collector):
        collector.record_execution(
            technique_id="clara",
            status="failure",
        )
        stats = collector.get_technique_stats("clara")
        assert stats is not None
        assert stats.success_count == 0
        assert stats.failure_count == 1

    def test_record_timeout(self, collector):
        collector.record_execution(
            technique_id="react",
            status="timeout",
        )
        stats = collector.get_technique_stats("react")
        assert stats is not None
        assert stats.timeout_count == 1
        assert stats.success_count == 0

    def test_record_error(self, collector):
        collector.record_execution(
            technique_id="clara",
            status="error",
        )
        stats = collector.get_technique_stats("clara")
        assert stats is not None
        assert stats.error_count == 1

    def test_record_default_values(self, collector):
        collector.record_execution(technique_id="clara")
        stats = collector.get_technique_stats("clara")
        assert stats is not None
        assert stats.total_tokens == 0
        assert stats.total_exec_time_ms == 0.0
        assert stats.company_id if hasattr(stats, "company_id") else True  # noqa: E501

    def test_record_updates_min_max_time(self, collector):
        collector.record_execution(
            technique_id="clara",
            exec_time_ms=100.0,
        )
        collector.record_execution(
            technique_id="clara",
            exec_time_ms=50.0,
        )
        collector.record_execution(
            technique_id="clara",
            exec_time_ms=200.0,
        )
        stats = collector.get_technique_stats("clara")
        assert stats.min_exec_time_ms == 50.0
        assert stats.max_exec_time_ms == 200.0

    def test_record_timestamp(self, collector):
        before = time.time()
        collector.record_execution(technique_id="clara")
        after = time.time()
        assert collector.get_record_count() == 1

    def test_record_invalid_status_raises(self, collector):
        with pytest.raises(ValueError):
            collector.record_execution(
                technique_id="clara",
                status="invalid_status",
            )


# ── 2. Multiple Executions Aggregation ───────────────────────────


class TestMultipleExecutions:
    """Tests for aggregating multiple executions."""

    def test_count_aggregation(self, populated_collector):
        stats = populated_collector.get_technique_stats(
            TechniqueID.CLARA,
            "company_a",
        )
        assert stats.total_executions == 13  # 10 success + 3 failure  # noqa: E501

    def test_success_rate_calculation(self, populated_collector):
        stats = populated_collector.get_technique_stats(
            TechniqueID.CLARA,
            "company_a",
        )
        assert stats.success_count == 10
        assert stats.failure_count == 3

    def test_token_aggregation(self, populated_collector):
        stats = populated_collector.get_technique_stats(
            TechniqueID.CLARA,
            "company_a",
        )
        expected_tokens = sum(50 + i * 10 for i in range(10)) + 30 * 3  # noqa: E501
        assert stats.total_tokens == expected_tokens

    def test_exec_time_aggregation(self, populated_collector):
        stats = populated_collector.get_technique_stats(
            TechniqueID.CLARA,
            "company_a",
        )
        expected_time = sum(100.0 + i * 5 for i in range(10)) + 200.0 * 3
        assert stats.total_exec_time_ms == expected_time

    def test_exec_times_list(self, populated_collector):
        stats = populated_collector.get_technique_stats(
            TechniqueID.CLARA,
            "company_a",
        )
        assert len(stats.exec_times) == 13

    def test_cross_company_aggregation(self, populated_collector):
        stats = populated_collector.get_technique_stats(
            TechniqueID.CLARA,
        )
        # company_a: 13, company_b: 5
        assert stats.total_executions == 18

    def test_multiple_techniques(self, populated_collector):
        clara = populated_collector.get_technique_stats(
            TechniqueID.CLARA,
        )
        cot = populated_collector.get_technique_stats(
            TechniqueID.CHAIN_OF_THOUGHT,
        )
        assert clara is not None
        assert cot is not None
        assert clara.total_executions != cot.total_executions


# ── 3. Per-Variant Isolation ─────────────────────────────────────


class TestVariantIsolation:
    """Tests for per-variant metrics breakdown."""

    def test_variant_summary_parwa(self, populated_collector):
        summary = populated_collector.get_variant_summary("parwa")
        assert summary is not None
        assert summary.total_executions > 0

    def test_variant_summary_mini_parwa(self, populated_collector):
        summary = populated_collector.get_variant_summary(
            "mini_parwa",
        )
        assert summary is not None
        assert summary.total_executions == 5

    def test_variant_summary_high_parwa(self, populated_collector):
        summary = populated_collector.get_variant_summary(
            "high_parwa",
        )
        assert summary is not None
        assert summary.total_executions > 0

    def test_variant_nonexistent(self, collector):
        summary = collector.get_variant_summary("unknown")
        assert summary is None

    def test_all_variant_summaries(self, populated_collector):
        all_v = populated_collector.get_all_variant_summaries()
        assert "parwa" in all_v
        assert "mini_parwa" in all_v
        assert "high_parwa" in all_v

    def test_variant_technique_counts(self, populated_collector):
        summary = populated_collector.get_variant_summary(
            "high_parwa",
        )
        assert "chain_of_thought" in summary.technique_counts
        assert "react" in summary.technique_counts

    def test_variant_success_failure_counts(
        self,
        populated_collector,
    ):
        summary = populated_collector.get_variant_summary("parwa")
        assert summary.success_count > 0
        assert summary.failure_count > 0


# ── 4. Per-Company Isolation ─────────────────────────────────────


class TestCompanyIsolation:
    """Tests for per-company metrics isolation."""

    def test_company_a_stats(self, populated_collector):
        stats = populated_collector.get_technique_stats(
            TechniqueID.CLARA,
            "company_a",
        )
        assert stats.total_executions == 13

    def test_company_b_stats(self, populated_collector):
        stats = populated_collector.get_technique_stats(
            TechniqueID.CLARA,
            "company_b",
        )
        assert stats.total_executions == 5

    def test_nonexistent_company(self, populated_collector):
        stats = populated_collector.get_technique_stats(
            TechniqueID.CLARA,
            "nonexistent",
        )
        assert stats is None

    def test_company_a_no_b_data(self, populated_collector):
        stats = populated_collector.get_technique_stats(
            TechniqueID.CLARA,
            "company_a",
        )
        # company_a should not include company_b records
        assert stats.total_executions == 13  # not 18

    def test_get_company_ids(self, populated_collector):
        ids = populated_collector.get_company_ids()
        assert "company_a" in ids
        assert "company_b" in ids

    def test_cross_company_different_techniques(
        self,
        populated_collector,
    ):
        # CLARA exists for both companies
        cot_a = populated_collector.get_technique_stats(
            TechniqueID.CHAIN_OF_THOUGHT,
            "company_a",
        )
        cot_b = populated_collector.get_technique_stats(
            TechniqueID.CHAIN_OF_THOUGHT,
            "company_b",
        )
        assert cot_a is not None
        assert cot_b is None  # company_b has no CoT


# ── 5. Time-Windowed Metrics ─────────────────────────────────────


class TestTimeWindowedMetrics:
    """Tests for time-windowed metric queries."""

    def test_current_window_includes_recent(
        self,
        collector,
    ):
        collector.record_execution(
            technique_id="clara",
            company_id="co1",
            status="success",
        )
        stats = collector.get_time_windowed_stats(
            "clara",
            "1min",
            "co1",
        )
        assert stats.total_executions == 1

    def test_old_records_excluded(self, collector):
        # Manually inject old record
        old_record = ExecutionRecord(
            technique_id="clara",
            variant="parwa",
            company_id="co1",
            status=ExecutionStatus.SUCCESS,
            tokens_used=100,
            exec_time_ms=50.0,
            timestamp=time.time() - 7200,  # 2 hours ago
        )
        collector._records[("clara", "co1")].append(old_record)
        collector._update_stats(("clara", "co1"), old_record)

        stats = collector.get_time_windowed_stats(
            "clara",
            "1min",
            "co1",
        )
        assert stats.total_executions == 0

    def test_5min_window(self, collector):
        collector.record_execution(
            technique_id="clara",
            company_id="co1",
        )
        stats = collector.get_time_windowed_stats(
            "clara",
            "5min",
            "co1",
        )
        assert stats.total_executions == 1

    def test_15min_window(self, collector):
        collector.record_execution(
            technique_id="clara",
            company_id="co1",
        )
        stats = collector.get_time_windowed_stats(
            "clara",
            "15min",
            "co1",
        )
        assert stats.total_executions == 1

    def test_1hr_window(self, collector):
        collector.record_execution(
            technique_id="clara",
            company_id="co1",
        )
        stats = collector.get_time_windowed_stats(
            "clara",
            "1hr",
            "co1",
        )
        assert stats.total_executions == 1

    def test_time_window_no_company(self, collector):
        collector.record_execution(
            technique_id="clara",
            company_id="co1",
        )
        collector.record_execution(
            technique_id="clara",
            company_id="co2",
        )
        stats = collector.get_time_windowed_stats(
            "clara",
            "1hr",
        )
        assert stats.total_executions == 2

    def test_time_window_empty_result(self, collector):
        stats = collector.get_time_windowed_stats(
            "nonexistent",
            "5min",
        )
        assert stats.total_executions == 0
        assert stats.min_exec_time_ms == 0.0
        assert stats.max_exec_time_ms == 0.0

    def test_time_window_with_technique_id_enum(self, collector):
        collector.record_execution(
            technique_id=TechniqueID.GST,
            company_id="co1",
        )
        stats = collector.get_time_windowed_stats(
            TechniqueID.GST,
            "1hr",
            "co1",
        )
        assert stats.total_executions == 1


# ── 6. Percentile Calculations ───────────────────────────────────


class TestPercentiles:
    """Tests for p50, p95, p99 calculations."""

    def test_empty_percentiles(self, collector):
        p = collector.get_percentiles("exec_time_ms")
        assert p["p50"] == 0.0
        assert p["p95"] == 0.0
        assert p["p99"] == 0.0

    def test_single_value_percentiles(self, collector):
        collector.record_execution(
            technique_id="clara",
            exec_time_ms=100.0,
        )
        p = collector.get_percentiles("exec_time_ms", "clara")
        assert p["p50"] == 100.0
        assert p["p95"] == 100.0
        assert p["p99"] == 100.0

    def test_exec_time_percentiles(self, collector):
        times = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]
        for t in times:
            collector.record_execution(
                technique_id="clara",
                exec_time_ms=t,
            )
        p = collector.get_percentiles("exec_time_ms", "clara")
        assert p["p50"] == 50.0
        # floor-percentile: int(0.95*9)=8 -> 90.0
        assert p["p95"] == 90.0
        # floor-percentile: int(0.99*9)=8 -> 90.0
        assert p["p99"] == 90.0

    def test_tokens_used_percentiles(self, collector):
        tokens = [100, 200, 300, 400, 500]
        for t in tokens:
            collector.record_execution(
                technique_id="clara",
                tokens_used=t,
            )
        p = collector.get_percentiles("tokens_used", "clara")
        assert p["p50"] == 300.0
        # floor-percentile: int(0.95*4)=3 -> 400.0
        assert p["p95"] == 400.0
        # floor-percentile: int(0.99*4)=3 -> 400.0
        assert p["p99"] == 400.0

    def test_percentile_filter_by_company(self, collector):
        for i in range(10):
            collector.record_execution(
                technique_id="clara",
                company_id="co1",
                exec_time_ms=float(i + 1) * 10,
            )
        for i in range(5):
            collector.record_execution(
                technique_id="clara",
                company_id="co2",
                exec_time_ms=float(i + 1) * 100,
            )
        p1 = collector.get_company_percentiles(
            "co1",
            "exec_time_ms",
        )
        p2 = collector.get_company_percentiles(
            "co2",
            "exec_time_ms",
        )
        assert p1["p50"] < p2["p50"]

    def test_percentile_no_technique_filter(self, collector):
        collector.record_execution(
            technique_id="clara",
            exec_time_ms=10.0,
        )
        collector.record_execution(
            technique_id="cot",
            exec_time_ms=100.0,
        )
        p = collector.get_percentiles("exec_time_ms")
        assert p["p50"] == 10.0
        # n=2: int(0.99*1)=0 -> sorted[0]=10.0
        assert p["p99"] == 10.0

    def test_percentiles_are_rounded(self, collector):
        collector.record_execution(
            technique_id="clara",
            exec_time_ms=33.333,
        )
        p = collector.get_percentiles("exec_time_ms", "clara")
        # Should be rounded to 2 decimal places
        assert p["p50"] == round(33.333, 2)


# ── 7. Leaderboard ───────────────────────────────────────────────


class TestLeaderboard:
    """Tests for technique leaderboards."""

    def test_leaderboard_most_used(self, populated_collector):
        board = populated_collector.get_leaderboard(
            sort_by="total_executions",
        )
        assert len(board) >= 2
        assert board[0].value >= board[1].value

    def test_leaderboard_success_rate(self, populated_collector):
        board = populated_collector.get_leaderboard(
            sort_by="success_rate",
        )
        for entry in board:
            assert 0.0 <= entry.value <= 100.0

    def test_leaderboard_avg_exec_time(self, populated_collector):
        board = populated_collector.get_leaderboard(
            sort_by="avg_exec_time_ms",
        )
        # Slowest should be first
        if len(board) >= 2:
            assert board[0].value >= board[1].value

    def test_leaderboard_total_tokens(self, populated_collector):
        board = populated_collector.get_leaderboard(
            sort_by="total_tokens",
        )
        if len(board) >= 2:
            assert board[0].value >= board[1].value

    def test_leaderboard_failure_rate(self, populated_collector):
        board = populated_collector.get_leaderboard(
            sort_by="failure_rate",
        )
        for entry in board:
            assert 0.0 <= entry.value <= 100.0

    def test_leaderboard_limit(self, populated_collector):
        board = populated_collector.get_leaderboard(limit=1)
        assert len(board) == 1

    def test_leaderboard_company_filter(
        self,
        populated_collector,
    ):
        board = populated_collector.get_leaderboard(
            company_id="company_b",
        )
        for entry in board:
            # Only techniques that company_b has used
            assert entry.technique_id == "clara"

    def test_leaderboard_invalid_sort_key(self, populated_collector):
        board = populated_collector.get_leaderboard(
            sort_by="invalid_key",
        )
        # Falls back to total_executions
        assert len(board) > 0

    def test_leaderboard_avg_tokens(self, populated_collector):
        board = populated_collector.get_leaderboard(
            sort_by="avg_tokens",
        )
        assert len(board) > 0

    def test_leaderboard_label(self, populated_collector):
        board = populated_collector.get_leaderboard(
            sort_by="total_tokens",
        )
        for entry in board:
            assert entry.label == "total_tokens"


# ── 8. Reset Functionality ───────────────────────────────────────


class TestReset:
    """Tests for metrics reset."""

    def test_reset_all(self, populated_collector):
        count = populated_collector.reset_metrics()
        assert count > 0
        assert populated_collector.get_record_count() == 0
        assert populated_collector.get_technique_count() == 0

    def test_reset_single_company(self, populated_collector):
        before_a = populated_collector.get_technique_stats(
            TechniqueID.CLARA,
            "company_a",
        )
        assert before_a is not None

        populated_collector.reset_metrics(company_id="company_a")

        after_a = populated_collector.get_technique_stats(
            TechniqueID.CLARA,
            "company_a",
        )
        after_b = populated_collector.get_technique_stats(
            TechniqueID.CLARA,
            "company_b",
        )
        assert after_a is None
        assert after_b is not None

    def test_reset_nonexistent_company(self, populated_collector):
        count = populated_collector.reset_metrics(
            company_id="nonexistent",
        )
        assert count == 0

    def test_reset_clears_variant_stats(self, populated_collector):
        populated_collector.reset_metrics()
        all_v = populated_collector.get_all_variant_summaries()
        assert len(all_v) == 0


# ── 9. Stale Entry Cleanup ───────────────────────────────────────


class TestStaleCleanup:
    """Tests for cleaning up old entries."""

    def test_cleanup_removes_old_records(self, collector):
        # Add recent record
        collector.record_execution(
            technique_id="clara",
            company_id="co1",
        )
        # Add old record manually
        old = ExecutionRecord(
            technique_id="clara",
            variant="parwa",
            company_id="co1",
            status=ExecutionStatus.SUCCESS,
            tokens_used=50,
            exec_time_ms=100.0,
            timestamp=time.time() - 7200,
        )
        collector._records[("clara", "co1")].append(old)

        removed = collector.cleanup_stale(max_age_seconds=3600)
        assert removed == 1
        assert collector.get_record_count() == 1

    def test_cleanup_keeps_recent_records(self, collector):
        collector.record_execution(
            technique_id="clara",
            company_id="co1",
        )
        removed = collector.cleanup_stale(max_age_seconds=3600)
        assert removed == 0
        assert collector.get_record_count() == 1

    def test_cleanup_recalculates_stats(self, collector):
        collector.record_execution(
            technique_id="clara",
            company_id="co1",
            exec_time_ms=100.0,
        )
        old = ExecutionRecord(
            technique_id="clara",
            variant="parwa",
            company_id="co1",
            status=ExecutionStatus.SUCCESS,
            tokens_used=9999,
            exec_time_ms=9999.0,
            timestamp=time.time() - 7200,
        )
        collector._records[("clara", "co1")].append(old)
        collector._update_stats(("clara", "co1"), old)

        collector.cleanup_stale(max_age_seconds=3600)
        stats = collector.get_technique_stats("clara", "co1")
        assert stats.total_tokens == 0  # old one cleaned

    def test_cleanup_empty(self, collector):
        removed = collector.cleanup_stale()
        assert removed == 0

    def test_cleanup_all_stale(self, collector):
        old = ExecutionRecord(
            technique_id="clara",
            variant="parwa",
            company_id="co1",
            status=ExecutionStatus.SUCCESS,
            tokens_used=50,
            exec_time_ms=100.0,
            timestamp=time.time() - 7200,
        )
        collector._records[("clara", "co1")].append(old)
        collector._update_stats(("clara", "co1"), old)

        removed = collector.cleanup_stale(max_age_seconds=3600)
        assert removed == 1
        assert collector.get_record_count() == 0


# ── 10. Concurrent Thread Safety ─────────────────────────────────


class TestConcurrency:
    """Tests for thread safety under concurrent access."""

    def test_concurrent_recording(self, collector):
        """Multiple threads recording simultaneously."""
        num_threads = 10
        records_per_thread = 50

        def record_batch(thread_id):
            for i in range(records_per_thread):
                collector.record_execution(
                    technique_id="clara",
                    variant="parwa",
                    company_id=f"company_{thread_id % 3}",
                    status="success",
                    tokens_used=100,
                    exec_time_ms=50.0,
                )

        threads = [
            threading.Thread(target=record_batch, args=(i,)) for i in range(num_threads)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        expected = num_threads * records_per_thread
        assert collector.get_record_count() == expected

    def test_concurrent_read_write(self, populated_collector):
        """Reading while writing should not crash."""
        errors = []

        def writer():
            try:
                for i in range(20):
                    populated_collector.record_execution(
                        technique_id="clara",
                        company_id="co_new",
                    )
            except Exception as e:
                errors.append(e)

        def reader():
            try:
                for i in range(20):
                    populated_collector.get_technique_stats(
                        "clara",
                    )
                    populated_collector.get_leaderboard()
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

    def test_concurrent_leaderboard_access(
        self,
        populated_collector,
    ):
        """Concurrent leaderboard queries should not crash."""
        errors = []

        def query_leaderboard():
            try:
                for _ in range(50):
                    populated_collector.get_leaderboard(
                        sort_by="total_executions",
                    )
            except Exception as e:
                errors.append(e)

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(query_leaderboard) for _ in range(5)]
            for f in as_completed(futures):
                f.result()

        assert len(errors) == 0

    def test_concurrent_reset_and_record(self):
        """Reset while recording should not corrupt state."""
        collector = TechniqueMetricsCollector()
        errors = []

        def recorder():
            try:
                for i in range(100):
                    collector.record_execution(
                        technique_id="clara",
                        company_id=f"co_{i % 2}",
                    )
            except Exception as e:
                errors.append(e)

        def resetter():
            try:
                for _ in range(5):
                    collector.reset_metrics()
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)

        t1 = threading.Thread(target=recorder)
        t2 = threading.Thread(target=resetter)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert len(errors) == 0


# ── 11. Edge Cases ───────────────────────────────────────────────


class TestEdgeCases:
    """Tests for edge cases and empty states."""

    def test_empty_collector_stats(self, collector):
        stats = collector.get_technique_stats("clara")
        assert stats is None

    def test_empty_collector_variant(self, collector):
        summary = collector.get_variant_summary("parwa")
        assert summary is None

    def test_empty_collector_leaderboard(self, collector):
        board = collector.get_leaderboard()
        assert board == []

    def test_empty_collector_percentiles(self, collector):
        p = collector.get_percentiles("exec_time_ms")
        assert p == {"p50": 0.0, "p95": 0.0, "p99": 0.0}

    def test_empty_collector_company_ids(self, collector):
        ids = collector.get_company_ids()
        assert ids == []

    def test_empty_collector_record_count(self, collector):
        assert collector.get_record_count() == 0

    def test_empty_collector_technique_count(self, collector):
        assert collector.get_technique_count() == 0

    def test_zero_exec_time(self, collector):
        collector.record_execution(
            technique_id="clara",
            exec_time_ms=0.0,
        )
        stats = collector.get_technique_stats("clara")
        assert stats.min_exec_time_ms == 0.0

    def test_zero_tokens(self, collector):
        collector.record_execution(
            technique_id="clara",
            tokens_used=0,
        )
        stats = collector.get_technique_stats("clara")
        assert stats.total_tokens == 0

    def test_very_large_exec_time(self, collector):
        collector.record_execution(
            technique_id="clara",
            exec_time_ms=1e9,
        )
        stats = collector.get_technique_stats("clara")
        assert stats.max_exec_time_ms == 1e9

    def test_time_window_unknown_technique(self, collector):
        stats = collector.get_time_windowed_stats(
            "nonexistent",
            "5min",
        )
        assert stats.total_executions == 0

    def test_all_variants_constant(self):
        assert "parwa" in VALID_VARIANTS
        assert "high_parwa" in VALID_VARIANTS
        assert "mini_parwa" in VALID_VARIANTS
        assert len(VALID_VARIANTS) == 3

    def test_time_windows_constant(self):
        assert TIME_WINDOWS_SECONDS["1min"] == 60
        assert TIME_WINDOWS_SECONDS["5min"] == 300
        assert TIME_WINDOWS_SECONDS["15min"] == 900
        assert TIME_WINDOWS_SECONDS["1hr"] == 3600


# ── 12. Dataclass Tests ──────────────────────────────────────────


class TestDataclasses:
    """Tests for dataclass integrity."""

    def test_execution_record_creation(self):
        record = ExecutionRecord(
            technique_id="clara",
            variant="parwa",
            company_id="co1",
            status=ExecutionStatus.SUCCESS,
            tokens_used=100,
            exec_time_ms=50.0,
        )
        assert record.technique_id == "clara"
        assert record.status == ExecutionStatus.SUCCESS

    def test_technique_stats_defaults(self):
        stats = TechniqueStats(technique_id="clara")
        assert stats.total_executions == 0
        assert stats.success_count == 0
        assert stats.min_exec_time_ms == float("inf")
        assert stats.max_exec_time_ms == 0.0
        assert stats.exec_times == []

    def test_variant_summary_defaults(self):
        vs = VariantSummary(variant="parwa")
        assert vs.total_executions == 0
        assert vs.technique_counts == {}

    def test_leaderboard_entry_creation(self):
        entry = LeaderboardEntry(
            technique_id="clara",
            value=42.0,
            label="total_executions",
        )
        assert entry.technique_id == "clara"
        assert entry.value == 42.0

    def test_execution_status_enum(self):
        assert ExecutionStatus.SUCCESS.value == "success"
        assert ExecutionStatus.FAILURE.value == "failure"
        assert ExecutionStatus.TIMEOUT.value == "timeout"
        assert ExecutionStatus.ERROR.value == "error"
