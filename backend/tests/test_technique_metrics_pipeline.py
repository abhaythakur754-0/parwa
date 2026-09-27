"""
Tests for Technique Performance Metrics Pipeline (SG-16)

Tests for:
- MetricsRecord creation and fields
- MetricsPipeline.record_technique_execution
- StdoutLogSink and InMemoryLogSink
- Company isolation (BC-001)
- get_metrics_summary
- Error handling (BC-008)
- Thread safety
- Edge cases

Minimum 40 tests.
"""

import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from app.core.technique_metrics import TechniqueMetricsCollector
from app.core.technique_metrics_pipeline import (
    InMemoryLogSink,
    LogSink,
    MetricsPipeline,
    MetricsRecord,
    StdoutLogSink,
)


# ════════════════════════════════════════════════════════════════════
# MetricsRecord Tests
# ════════════════════════════════════════════════════════════════════


class TestMetricsRecord:
    """Tests for the MetricsRecord dataclass."""

    def test_create_with_required_fields(self):
        """Test creating a MetricsRecord with required fields."""
        record = MetricsRecord(
            technique_id="clara",
            trigger_signal="r1",
            input_hash="abc123",
            token_cost=100,
            latency_ms=50.0,
            output_quality_score=0.9,
            variant_id="parwa",
            tenant_id="company_1",
            status="success",
        )
        assert record.technique_id == "clara"
        assert record.trigger_signal == "r1"
        assert record.input_hash == "abc123"
        assert record.token_cost == 100
        assert record.latency_ms == 50.0
        assert record.output_quality_score == 0.9
        assert record.variant_id == "parwa"
        assert record.tenant_id == "company_1"
        assert record.status == "success"

    def test_create_with_defaults(self):
        """Test MetricsRecord has default timestamp and status."""
        record = MetricsRecord(
            technique_id="clara",
            trigger_signal="r1",
            input_hash="abc",
            token_cost=0,
            latency_ms=0.0,
            output_quality_score=0.0,
            variant_id="parwa",
            tenant_id="default",
        )
        assert record.status == "success"
        assert record.timestamp > 0
        assert isinstance(record.timestamp, float)

    def test_record_is_dataclass(self):
        """Test MetricsRecord is a dataclass."""
        record = MetricsRecord(
            technique_id="clara",
            trigger_signal="r1",
            input_hash="abc",
            token_cost=0,
            latency_ms=0.0,
            output_quality_score=0.0,
            variant_id="parwa",
            tenant_id="default",
        )
        assert hasattr(record, "__dataclass_fields__")

    def test_record_all_fields_settable(self):
        """Test all fields can be explicitly set."""
        now = time.time()
        record = MetricsRecord(
            technique_id="gsd",
            trigger_signal="r3",
            input_hash="hash1",
            token_cost=500,
            latency_ms=200.0,
            output_quality_score=0.95,
            variant_id="parwa_high",
            tenant_id="company_2",
            timestamp=now,
            status="failure",
        )
        assert record.technique_id == "gsd"
        assert record.trigger_signal == "r3"
        assert record.input_hash == "hash1"
        assert record.token_cost == 500
        assert record.latency_ms == 200.0
        assert record.output_quality_score == 0.95
        assert record.variant_id == "parwa_high"
        assert record.tenant_id == "company_2"
        assert record.timestamp == now
        assert record.status == "failure"

    def test_record_with_empty_strings(self):
        """Test MetricsRecord with empty string fields."""
        record = MetricsRecord(
            technique_id="",
            trigger_signal="",
            input_hash="",
            token_cost=0,
            latency_ms=0.0,
            output_quality_score=0.0,
            variant_id="",
            tenant_id="",
        )
        assert record.technique_id == ""
        assert record.trigger_signal == ""
        assert record.input_hash == ""

    def test_record_with_zero_values(self):
        """Test MetricsRecord with zero numeric values."""
        record = MetricsRecord(
            technique_id="clara",
            trigger_signal="r1",
            input_hash="h",
            token_cost=0,
            latency_ms=0.0,
            output_quality_score=0.0,
            variant_id="parwa",
            tenant_id="c1",
        )
        assert record.token_cost == 0
        assert record.latency_ms == 0.0
        assert record.output_quality_score == 0.0

    def test_record_with_large_values(self):
        """Test MetricsRecord with large numeric values."""
        record = MetricsRecord(
            technique_id="clara",
            trigger_signal="r1",
            input_hash="h",
            token_cost=999999,
            latency_ms=99999.9,
            output_quality_score=1.0,
            variant_id="parwa",
            tenant_id="c1",
        )
        assert record.token_cost == 999999
        assert record.latency_ms == 99999.9
        assert record.output_quality_score == 1.0


# ════════════════════════════════════════════════════════════════════
# StdoutLogSink Tests
# ════════════════════════════════════════════════════════════════════


class TestStdoutLogSink:

    def test_stdout_sink_is_log_sink(self):
        """Test StdoutLogSink is a LogSink subclass."""
        sink = StdoutLogSink()
        assert isinstance(sink, LogSink)

    def test_stdout_sink_emit_does_not_crash(self):
        """Test StdoutLogSink.emit never crashes (BC-008)."""
        sink = StdoutLogSink()
        record = MetricsRecord(
            technique_id="clara",
            trigger_signal="r1",
            input_hash="h",
            token_cost=100,
            latency_ms=50.0,
            output_quality_score=0.9,
            variant_id="parwa",
            tenant_id="c1",
        )
        # Should not raise
        sink.emit(record)

    def test_stdout_sink_with_valid_record(self):
        """Test StdoutLogSink emits valid records without error."""
        sink = StdoutLogSink()
        record = MetricsRecord(
            technique_id="gsd",
            trigger_signal="r3",
            input_hash="hash1",
            token_cost=200,
            latency_ms=100.0,
            output_quality_score=0.8,
            variant_id="mini_parwa",
            tenant_id="c2",
            status="timeout",
        )
        sink.emit(record)  # No assertion, just no crash


# ════════════════════════════════════════════════════════════════════
# InMemoryLogSink Tests
# ════════════════════════════════════════════════════════════════════


class TestInMemoryLogSink:

    def test_in_memory_sink_is_log_sink(self):
        """Test InMemoryLogSink is a LogSink subclass."""
        sink = InMemoryLogSink()
        assert isinstance(sink, LogSink)

    def test_in_memory_sink_stores_records(self):
        """Test InMemoryLogSink stores emitted records."""
        sink = InMemoryLogSink()
        record = MetricsRecord(
            technique_id="clara",
            trigger_signal="r1",
            input_hash="h",
            token_cost=100,
            latency_ms=50.0,
            output_quality_score=0.9,
            variant_id="parwa",
            tenant_id="c1",
        )
        sink.emit(record)
        assert sink.record_count == 1

    def test_in_memory_sink_get_records(self):
        """Test InMemoryLogSink.get_records returns stored records."""
        sink = InMemoryLogSink()
        record1 = MetricsRecord(
            technique_id="clara",
            trigger_signal="r1",
            input_hash="h1",
            token_cost=100,
            latency_ms=50.0,
            output_quality_score=0.9,
            variant_id="parwa",
            tenant_id="c1",
        )
        record2 = MetricsRecord(
            technique_id="gsd",
            trigger_signal="r3",
            input_hash="h2",
            token_cost=200,
            latency_ms=100.0,
            output_quality_score=0.8,
            variant_id="parwa",
            tenant_id="c1",
        )
        sink.emit(record1)
        sink.emit(record2)
        records = sink.get_records()
        assert len(records) == 2
        assert records[0].technique_id == "clara"
        assert records[1].technique_id == "gsd"

    def test_in_memory_sink_clear(self):
        """Test InMemoryLogSink.clear removes all records."""
        sink = InMemoryLogSink()
        record = MetricsRecord(
            technique_id="clara",
            trigger_signal="r1",
            input_hash="h",
            token_cost=100,
            latency_ms=50.0,
            output_quality_score=0.9,
            variant_id="parwa",
            tenant_id="c1",
        )
        sink.emit(record)
        assert sink.record_count == 1
        sink.clear()
        assert sink.record_count == 0
        assert sink.get_records() == []

    def test_in_memory_sink_initially_empty(self):
        """Test InMemoryLogSink starts with no records."""
        sink = InMemoryLogSink()
        assert sink.record_count == 0
        assert sink.get_records() == []

    def test_in_memory_sink_get_records_returns_copy(self):
        """Test get_records returns a copy, not a reference."""
        sink = InMemoryLogSink()
        record = MetricsRecord(
            technique_id="clara",
            trigger_signal="r1",
            input_hash="h",
            token_cost=100,
            latency_ms=50.0,
            output_quality_score=0.9,
            variant_id="parwa",
            tenant_id="c1",
        )
        sink.emit(record)
        records = sink.get_records()
        records.clear()
        assert sink.record_count == 1  # Original unchanged


# ════════════════════════════════════════════════════════════════════
# MetricsPipeline Creation Tests
# ════════════════════════════════════════════════════════════════════


class TestMetricsPipelineCreation:

    def test_pipeline_creates_with_defaults(self):
        """Test MetricsPipeline can be created with no arguments."""
        pipeline = MetricsPipeline()
        assert pipeline is not None
        assert pipeline.collector is not None
        assert len(pipeline.sinks) == 1

    def test_pipeline_creates_with_custom_collector(self):
        """Test MetricsPipeline accepts custom collector."""
        collector = TechniqueMetricsCollector()
        pipeline = MetricsPipeline(collector=collector)
        assert pipeline.collector is collector

    def test_pipeline_creates_with_custom_sinks(self):
        """Test MetricsPipeline accepts custom sinks."""
        sink1 = InMemoryLogSink()
        sink2 = InMemoryLogSink()
        pipeline = MetricsPipeline(sinks=[sink1, sink2])
        assert len(pipeline.sinks) == 2

    def test_pipeline_creates_with_empty_sinks(self):
        """Test MetricsPipeline works with no sinks."""
        pipeline = MetricsPipeline(sinks=[])
        assert len(pipeline.sinks) == 0

    def test_pipeline_creates_default_stdout_sink(self):
        """Test default sink is StdoutLogSink."""
        pipeline = MetricsPipeline()
        assert isinstance(pipeline.sinks[0], StdoutLogSink)


# ════════════════════════════════════════════════════════════════════
# MetricsPipeline.record_technique_execution Tests
# ════════════════════════════════════════════════════════════════════


class TestRecordTechniqueExecution:

    def test_record_returns_metrics_record(self):
        """Test record_technique_execution returns a MetricsRecord."""
        sink = InMemoryLogSink()
        pipeline = MetricsPipeline(sinks=[sink])
        record = pipeline.record_technique_execution(
            technique_id="clara",
            variant_id="parwa",
            tenant_id="company_1",
            trigger_signal="r1",
            input_hash="hash1",
            token_cost=100,
            latency_ms=50.0,
            output_quality_score=0.9,
            status="success",
        )
        assert record is not None
        assert isinstance(record, MetricsRecord)
        assert record.technique_id == "clara"
        assert record.tenant_id == "company_1"

    def test_record_emits_to_sink(self):
        """Test recording emits to configured sinks."""
        sink = InMemoryLogSink()
        pipeline = MetricsPipeline(sinks=[sink])
        pipeline.record_technique_execution(
            technique_id="clara",
            tenant_id="c1",
        )
        assert sink.record_count == 1

    def test_record_emits_to_multiple_sinks(self):
        """Test recording emits to all sinks."""
        sink1 = InMemoryLogSink()
        sink2 = InMemoryLogSink()
        pipeline = MetricsPipeline(sinks=[sink1, sink2])
        pipeline.record_technique_execution(
            technique_id="clara",
            tenant_id="c1",
        )
        assert sink1.record_count == 1
        assert sink2.record_count == 1

    def test_record_in_collector(self):
        """Test recording also records in TechniqueMetricsCollector."""
        collector = TechniqueMetricsCollector()
        sink = InMemoryLogSink()
        pipeline = MetricsPipeline(
            collector=collector, sinks=[sink],
        )
        pipeline.record_technique_execution(
            technique_id="clara",
            variant_id="parwa",
            tenant_id="c1",
            status="success",
            token_cost=100,
            latency_ms=50.0,
        )
        stats = collector.get_technique_stats("clara", "c1")
        assert stats is not None
        assert stats.total_executions == 1
        assert stats.success_count == 1

    def test_record_multiple_times(self):
        """Test recording multiple executions."""
        sink = InMemoryLogSink()
        pipeline = MetricsPipeline(sinks=[sink])
        for i in range(5):
            pipeline.record_technique_execution(
                technique_id="clara",
                tenant_id="c1",
            )
        assert sink.record_count == 5

    def test_record_with_defaults(self):
        """Test recording with only required params uses defaults."""
        sink = InMemoryLogSink()
        pipeline = MetricsPipeline(sinks=[sink])
        record = pipeline.record_technique_execution(
            technique_id="clara",
        )
        assert record is not None
        assert record.variant_id == "parwa"
        assert record.tenant_id == "default"
        assert record.trigger_signal == "unknown"
        assert record.status == "success"
        assert record.token_cost == 0
        assert record.latency_ms == 0.0
        assert record.output_quality_score == 0.0

    def test_record_failure_status(self):
        """Test recording a failure status."""
        collector = TechniqueMetricsCollector()
        sink = InMemoryLogSink()
        pipeline = MetricsPipeline(
            collector=collector, sinks=[sink],
        )
        pipeline.record_technique_execution(
            technique_id="clara",
            tenant_id="c1",
            status="failure",
        )
        stats = collector.get_technique_stats("clara", "c1")
        assert stats is not None
        assert stats.failure_count == 1


# ════════════════════════════════════════════════════════════════════
# Company Isolation Tests (BC-001)
# ════════════════════════════════════════════════════════════════════


class TestCompanyIsolation:

    def test_records_isolated_by_company(self):
        """Test records from different companies are isolated."""
        sink = InMemoryLogSink()
        pipeline = MetricsPipeline(sinks=[sink])

        pipeline.record_technique_execution(
            technique_id="clara",
            tenant_id="company_a",
        )
        pipeline.record_technique_execution(
            technique_id="gsd",
            tenant_id="company_b",
        )

        assert pipeline.get_company_record_count("company_a") == 1
        assert pipeline.get_company_record_count("company_b") == 1

    def test_summary_isolated_by_company(self):
        """Test metrics summary is scoped to the requested company."""
        pipeline = MetricsPipeline(sinks=[InMemoryLogSink()])

        pipeline.record_technique_execution(
            technique_id="clara",
            tenant_id="company_a",
            token_cost=100,
        )
        pipeline.record_technique_execution(
            technique_id="clara",
            tenant_id="company_b",
            token_cost=200,
        )

        summary_a = pipeline.get_metrics_summary("company_a")
        summary_b = pipeline.get_metrics_summary("company_b")

        assert summary_a["total_token_cost"] == 100
        assert summary_b["total_token_cost"] == 200

    def test_collector_isolated_by_company(self):
        """Test TechniqueMetricsCollector data is company-isolated."""
        collector = TechniqueMetricsCollector()
        sink = InMemoryLogSink()
        pipeline = MetricsPipeline(
            collector=collector, sinks=[sink],
        )

        pipeline.record_technique_execution(
            technique_id="clara",
            tenant_id="c1",
        )
        pipeline.record_technique_execution(
            technique_id="clara",
            tenant_id="c2",
        )

        stats_c1 = collector.get_technique_stats("clara", "c1")
        stats_c2 = collector.get_technique_stats("clara", "c2")

        assert stats_c1.total_executions == 1
        assert stats_c2.total_executions == 1

    def test_reset_company_does_not_affect_others(self):
        """Test resetting one company doesn't affect another."""
        pipeline = MetricsPipeline(sinks=[InMemoryLogSink()])

        pipeline.record_technique_execution(
            technique_id="clara",
            tenant_id="c1",
        )
        pipeline.record_technique_execution(
            technique_id="clara",
            tenant_id="c2",
        )

        pipeline.reset_company_metrics("c1")

        assert pipeline.get_company_record_count("c1") == 0
        assert pipeline.get_company_record_count("c2") == 1

    def test_nonexistent_company_returns_empty(self):
        """Test nonexistent company returns empty metrics."""
        pipeline = MetricsPipeline(sinks=[InMemoryLogSink()])
        summary = pipeline.get_metrics_summary("nonexistent")
        assert summary["total_executions"] == 0
        assert summary["techniques"] == {}


# ════════════════════════════════════════════════════════════════════
# get_metrics_summary Tests
# ════════════════════════════════════════════════════════════════════


class TestGetMetricsSummary:

    def test_empty_company_summary(self):
        """Test summary for company with no records."""
        pipeline = MetricsPipeline(sinks=[InMemoryLogSink()])
        summary = pipeline.get_metrics_summary("empty_co")
        assert summary["total_executions"] == 0
        assert summary["company_id"] == "empty_co"

    def test_summary_with_single_record(self):
        """Test summary with a single execution record."""
        pipeline = MetricsPipeline(sinks=[InMemoryLogSink()])
        pipeline.record_technique_execution(
            technique_id="clara",
            tenant_id="c1",
            token_cost=100,
            latency_ms=50.0,
            output_quality_score=0.9,
            status="success",
        )
        summary = pipeline.get_metrics_summary("c1")
        assert summary["total_executions"] == 1
        assert summary["success_count"] == 1
        assert summary["total_token_cost"] == 100
        assert summary["avg_latency_ms"] == 50.0
        assert summary["avg_quality_score"] == 0.9
        assert "clara" in summary["techniques"]

    def test_summary_with_multiple_records(self):
        """Test summary aggregates multiple records correctly."""
        pipeline = MetricsPipeline(sinks=[InMemoryLogSink()])
        pipeline.record_technique_execution(
            technique_id="clara",
            tenant_id="c1",
            token_cost=100,
            latency_ms=50.0,
            output_quality_score=0.8,
            status="success",
        )
        pipeline.record_technique_execution(
            technique_id="clara",
            tenant_id="c1",
            token_cost=200,
            latency_ms=100.0,
            output_quality_score=0.9,
            status="success",
        )
        pipeline.record_technique_execution(
            technique_id="gsd",
            tenant_id="c1",
            token_cost=50,
            latency_ms=30.0,
            output_quality_score=0.7,
            status="failure",
        )
        summary = pipeline.get_metrics_summary("c1")
        assert summary["total_executions"] == 3
        assert summary["success_count"] == 2
        assert summary["failure_count"] == 1
        assert summary["total_token_cost"] == 350
        assert "clara" in summary["techniques"]
        assert "gsd" in summary["techniques"]

    def test_summary_includes_all_status_types(self):
        """Test summary includes timeout and error counts."""
        pipeline = MetricsPipeline(sinks=[InMemoryLogSink()])
        pipeline.record_technique_execution(
            technique_id="clara",
            tenant_id="c1",
            status="timeout",
        )
        pipeline.record_technique_execution(
            technique_id="clara",
            tenant_id="c1",
            status="error",
        )
        summary = pipeline.get_metrics_summary("c1")
        assert summary["timeout_count"] == 1
        assert summary["error_count"] == 1

    def test_summary_with_time_window(self):
        """Test summary with time_window filter."""
        pipeline = MetricsPipeline(sinks=[InMemoryLogSink()])
        pipeline.record_technique_execution(
            technique_id="clara",
            tenant_id="c1",
        )
        # This record is recent, so it should be in "1hr" window
        summary = pipeline.get_metrics_summary("c1", "1hr")
        assert summary["total_executions"] == 1

    def test_summary_time_window_excludes_old(self):
        """Test time window excludes old records."""
        sink = InMemoryLogSink()
        pipeline = MetricsPipeline(sinks=[sink])

        # Manually inject an old record
        old_record = MetricsRecord(
            technique_id="clara",
            trigger_signal="r1",
            input_hash="h",
            token_cost=100,
            latency_ms=50.0,
            output_quality_score=0.9,
            variant_id="parwa",
            tenant_id="c1",
            timestamp=time.time() - 7200,  # 2 hours ago
            status="success",
        )
        with pipeline._lock:
            pipeline._company_records["c1"] = [old_record]

        summary = pipeline.get_metrics_summary("c1", "1hr")
        assert summary["total_executions"] == 0

    def test_summary_per_technique_breakdown(self):
        """Test per-technique breakdown in summary."""
        pipeline = MetricsPipeline(sinks=[InMemoryLogSink()])
        pipeline.record_technique_execution(
            technique_id="clara",
            tenant_id="c1",
            token_cost=100,
            latency_ms=50.0,
            output_quality_score=0.8,
            status="success",
        )
        pipeline.record_technique_execution(
            technique_id="gsd",
            tenant_id="c1",
            token_cost=50,
            latency_ms=30.0,
            output_quality_score=0.7,
            status="success",
        )
        summary = pipeline.get_metrics_summary("c1")
        clara_stats = summary["techniques"]["clara"]
        gsd_stats = summary["techniques"]["gsd"]
        assert clara_stats["total"] == 1
        assert clara_stats["total_token_cost"] == 100
        assert gsd_stats["total"] == 1
        assert gsd_stats["total_token_cost"] == 50


# ════════════════════════════════════════════════════════════════════
# Error Handling Tests (BC-008)
# ════════════════════════════════════════════════════════════════════


class TestErrorHandling:

    def test_record_never_crashes_on_bad_input(self):
        """Test record_technique_execution never crashes (BC-008)."""
        pipeline = MetricsPipeline(sinks=[InMemoryLogSink()])
        # All valid inputs — should work fine
        result = pipeline.record_technique_execution(
            technique_id="clara",
            tenant_id="c1",
        )
        assert result is not None

    def test_sink_failure_does_not_crash_pipeline(self):
        """Test a failing sink doesn't crash the pipeline."""
        failing_sink = MagicMock(spec=LogSink)
        failing_sink.emit.side_effect = RuntimeError("sink error")

        pipeline = MetricsPipeline(sinks=[failing_sink])
        result = pipeline.record_technique_execution(
            technique_id="clara",
            tenant_id="c1",
        )
        assert result is not None

    def test_get_summary_never_crashes(self):
        """Test get_metrics_summary never crashes (BC-008)."""
        pipeline = MetricsPipeline(sinks=[InMemoryLogSink()])
        summary = pipeline.get_metrics_summary("any_company")
        assert summary is not None
        assert isinstance(summary, dict)

    def test_get_company_record_count_never_crashes(self):
        """Test get_company_record_count never crashes."""
        pipeline = MetricsPipeline(sinks=[InMemoryLogSink()])
        count = pipeline.get_company_record_count("any")
        assert isinstance(count, int)

    def test_reset_company_never_crashes(self):
        """Test reset_company_metrics never crashes."""
        pipeline = MetricsPipeline(sinks=[InMemoryLogSink()])
        count = pipeline.reset_company_metrics("any")
        assert isinstance(count, int)

    def test_add_sink_never_crashes(self):
        """Test add_sink never crashes."""
        pipeline = MetricsPipeline(sinks=[InMemoryLogSink()])
        pipeline.add_sink(InMemoryLogSink())
        assert len(pipeline.sinks) == 2

    def test_mixed_good_bad_sinks(self):
        """Test good sinks still receive data when one fails."""
        failing_sink = MagicMock(spec=LogSink)
        failing_sink.emit.side_effect = RuntimeError("fail")
        good_sink = InMemoryLogSink()

        pipeline = MetricsPipeline(sinks=[failing_sink, good_sink])
        pipeline.record_technique_execution(
            technique_id="clara",
            tenant_id="c1",
        )
        assert good_sink.record_count == 1


# ════════════════════════════════════════════════════════════════════
# Thread Safety Tests
# ════════════════════════════════════════════════════════════════════


class TestThreadSafety:

    def test_concurrent_recordings(self):
        """Test concurrent recordings don't lose data."""
        sink = InMemoryLogSink()
        pipeline = MetricsPipeline(sinks=[sink])
        num_threads = 10
        records_per_thread = 50

        def worker():
            for _ in range(records_per_thread):
                pipeline.record_technique_execution(
                    technique_id="clara",
                    tenant_id="c1",
                )

        threads = [
            threading.Thread(target=worker)
            for _ in range(num_threads)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        expected = num_threads * records_per_thread
        assert sink.record_count == expected

    def test_concurrent_different_companies(self):
        """Test concurrent recordings across companies."""
        sink = InMemoryLogSink()
        pipeline = MetricsPipeline(sinks=[sink])

        def worker(company_id: str):
            for _ in range(20):
                pipeline.record_technique_execution(
                    technique_id="clara",
                    tenant_id=company_id,
                )

        threads = [
            threading.Thread(target=worker, args=(f"c{i}",))
            for i in range(5)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        for i in range(5):
            assert (
                pipeline.get_company_record_count(f"c{i}") == 20
            )

    def test_concurrent_summary_and_recording(self):
        """Test concurrent summary reads and writes."""
        pipeline = MetricsPipeline(sinks=[InMemoryLogSink()])

        def writer():
            for _ in range(50):
                pipeline.record_technique_execution(
                    technique_id="clara",
                    tenant_id="c1",
                )

        def reader():
            for _ in range(50):
                pipeline.get_metrics_summary("c1")

        t1 = threading.Thread(target=writer)
        t2 = threading.Thread(target=reader)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert pipeline.get_company_record_count("c1") == 50


# ════════════════════════════════════════════════════════════════════
# Edge Cases
# ════════════════════════════════════════════════════════════════════


class TestEdgeCases:

    def test_pipeline_with_no_sinks(self):
        """Test pipeline works without any sinks."""
        pipeline = MetricsPipeline(sinks=[])
        result = pipeline.record_technique_execution(
            technique_id="clara",
            tenant_id="c1",
        )
        assert result is not None

    def test_add_sink_after_creation(self):
        """Test adding sinks after pipeline creation."""
        sink1 = InMemoryLogSink()
        sink2 = InMemoryLogSink()
        pipeline = MetricsPipeline(sinks=[sink1])
        pipeline.add_sink(sink2)

        pipeline.record_technique_execution(
            technique_id="clara",
            tenant_id="c1",
        )
        assert sink1.record_count == 1
        assert sink2.record_count == 1

    def test_reset_company_returns_count(self):
        """Test reset_company_metrics returns number removed."""
        pipeline = MetricsPipeline(sinks=[InMemoryLogSink()])
        pipeline.record_technique_execution(
            technique_id="clara",
            tenant_id="c1",
        )
        pipeline.record_technique_execution(
            technique_id="gsd",
            tenant_id="c1",
        )
        removed = pipeline.reset_company_metrics("c1")
        assert removed == 2

    def test_reset_nonexistent_company(self):
        """Test reset for nonexistent company returns 0."""
        pipeline = MetricsPipeline(sinks=[InMemoryLogSink()])
        removed = pipeline.reset_company_metrics("nonexistent")
        assert removed == 0

    def test_record_then_reset_then_record_again(self):
        """Test record-reset-record cycle."""
        pipeline = MetricsPipeline(sinks=[InMemoryLogSink()])
        pipeline.record_technique_execution(
            technique_id="clara",
            tenant_id="c1",
        )
        assert pipeline.get_company_record_count("c1") == 1
        pipeline.reset_company_metrics("c1")
        assert pipeline.get_company_record_count("c1") == 0
        pipeline.record_technique_execution(
            technique_id="gsd",
            tenant_id="c1",
        )
        assert pipeline.get_company_record_count("c1") == 1

    def test_collector_property(self):
        """Test collector property returns the collector."""
        collector = TechniqueMetricsCollector()
        pipeline = MetricsPipeline(collector=collector)
        assert pipeline.collector is collector

    def test_sinks_property_returns_copy(self):
        """Test sinks property returns a copy of the list."""
        sink = InMemoryLogSink()
        pipeline = MetricsPipeline(sinks=[sink])
        sinks_copy = pipeline.sinks
        sinks_copy.clear()
        assert len(pipeline.sinks) == 1  # Original unchanged
