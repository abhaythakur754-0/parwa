"""
Tests for Cross-Tenant Analytics
"""

import pytest
from datetime import datetime, timedelta
from enterprise.multi_tenancy.cross_tenant_analytics import (
    CrossTenantAnalytics, MetricType, AggregationType, MetricPoint, AggregatedMetric
)
from enterprise.multi_tenancy.benchmark_engine import (
    BenchmarkEngine, BenchmarkType, BenchmarkResult, BenchmarkDefinition
)
from enterprise.multi_tenancy.comparison_report import (
    ComparisonReportGenerator, ReportType, ComparisonReport
)


class TestCrossTenantAnalytics:
    """Tests for CrossTenantAnalytics"""

    @pytest.fixture
    def analytics(self):
        return CrossTenantAnalytics(min_tenant_threshold=3)

    def test_record(self, analytics):
        point = analytics.record("tenant_001", "response_time", 150.0)
        assert point.tenant_id == "tenant_001"
        assert point.value == 150.0

    def test_aggregate_sum(self, analytics):
        # Record metrics for multiple tenants
        for i in range(5):
            analytics.record(f"tenant_{i:03d}", "api_calls", 100 * (i + 1))

        result = analytics.aggregate("api_calls", AggregationType.SUM)
        assert result is not None
        assert result.tenant_count == 5

    def test_aggregate_avg(self, analytics):
        for i in range(5):
            analytics.record(f"tenant_{i:03d}", "response_time", 100.0)

        result = analytics.aggregate("response_time", AggregationType.AVG)
        assert result is not None
        assert result.value == 100.0

    def test_aggregate_insufficient_tenants(self, analytics):
        analytics.record("tenant_001", "metric", 100.0)
        analytics.record("tenant_002", "metric", 200.0)

        # Only 2 tenants, threshold is 3
        result = analytics.aggregate("metric", AggregationType.AVG)
        assert result is None

    def test_get_tenant_ranking(self, analytics):
        for i in range(5):
            analytics.record(f"tenant_{i:03d}", "score", 100.0 - i * 10)

        ranking = analytics.get_tenant_ranking("score", "tenant_000")
        assert ranking is not None
        assert ranking["rank"] == 1
        assert ranking["percentile"] == 100.0

    def test_get_distribution(self, analytics):
        for i in range(10):
            analytics.record(f"tenant_{i:03d}", "metric", i * 10.0)

        dist = analytics.get_distribution("metric")
        assert dist["total"] == 10
        assert len(dist["buckets"]) == 10

    def test_compare_tenant_to_average(self, analytics):
        for i in range(5):
            analytics.record(f"tenant_{i:03d}", "metric", 100.0)

        analytics.record("tenant_000", "metric", 200.0)

        comparison = analytics.compare_tenant_to_average("tenant_000", "metric")
        assert comparison is not None
        assert comparison["tenant_value"] > comparison["cross_tenant_average"]

    def test_get_trend(self, analytics):
        # Record metrics for multiple days
        for i in range(5):
            analytics.record(f"tenant_{i:03d}", "metric", 100.0)

        trend = analytics.get_trend("metric", period_days=3)
        assert len(trend) == 3

    def test_get_metrics(self, analytics):
        analytics.record("tenant_001", "metric", 100.0)

        metrics = analytics.get_metrics()
        assert metrics["total_points"] == 1


class TestBenchmarkEngine:
    """Tests for BenchmarkEngine"""

    @pytest.fixture
    def engine(self):
        return BenchmarkEngine(min_tenants_for_ranking=3)

    def test_calculate_benchmark(self, engine):
        metrics = {
            "response_time": 90,
            "throughput": 85,
            "error_rate": 95
        }

        result = engine.calculate_benchmark("tenant_001", "overall_performance", metrics)
        assert result is not None
        assert result.tenant_id == "tenant_001"

    def test_get_percentile_ranking(self, engine):
        # Create multiple benchmark results
        for i in range(5):
            metrics = {"response_time": 80 + i, "throughput": 80 + i, "error_rate": 80 + i}
            engine.calculate_benchmark(f"tenant_{i:03d}", "overall_performance", metrics)

        ranking = engine.get_percentile_ranking("tenant_004", "overall_performance")
        assert ranking is not None
        assert ranking["rank"] <= 5

    def test_get_top_performers(self, engine):
        for i in range(5):
            metrics = {"response_time": 80 + i * 2, "throughput": 80 + i * 2, "error_rate": 80 + i * 2}
            engine.calculate_benchmark(f"tenant_{i:03d}", "overall_performance", metrics)

        top = engine.get_top_performers("overall_performance", limit=3)
        assert len(top) == 3

    def test_get_benchmark_distribution(self, engine):
        for i in range(5):
            metrics = {"response_time": 50 + i * 10, "throughput": 50 + i * 10, "error_rate": 50 + i * 10}
            engine.calculate_benchmark(f"tenant_{i:03d}", "overall_performance", metrics)

        dist = engine.get_benchmark_distribution("overall_performance")
        assert dist["count"] == 5

    def test_add_benchmark_definition(self, engine):
        definition = engine.add_benchmark_definition(
            benchmark_id="custom_benchmark",
            name="Custom Benchmark",
            benchmark_type=BenchmarkType.PERFORMANCE,
            metrics=["metric1", "metric2"],
            weights={"metric1": 0.6, "metric2": 0.4}
        )

        assert definition.benchmark_id == "custom_benchmark"
        assert engine.get_benchmark_definition("custom_benchmark") is not None

    def test_list_benchmarks(self, engine):
        benchmarks = engine.list_benchmarks()
        assert len(benchmarks) > 0

    def test_get_tenant_benchmarks(self, engine):
        metrics = {"response_time": 90, "throughput": 85, "error_rate": 95}
        engine.calculate_benchmark("tenant_001", "overall_performance", metrics)

        results = engine.get_tenant_benchmarks("tenant_001")
        assert len(results) == 1

    def test_compare_to_peers(self, engine):
        for i in range(5):
            metrics = {"response_time": 70 + i * 5, "throughput": 70 + i * 5, "error_rate": 70 + i * 5}
            engine.calculate_benchmark(f"tenant_{i:03d}", "overall_performance", metrics)

        comparison = engine.compare_to_peers("tenant_002", "overall_performance")
        assert comparison is not None
        assert "tenant_score" in comparison


class TestComparisonReportGenerator:
    """Tests for ComparisonReportGenerator"""

    @pytest.fixture
    def generator(self):
        return ComparisonReportGenerator()

    def test_generate_performance_report(self, generator):
        tenant_data = {
            "avg_response_time": 150,
            "throughput": 1000,
            "error_rate": 1.5
        }
        peer_data = {
            "avg_response_time": 200,
            "throughput": 800,
            "error_rate": 2.0
        }

        report = generator.generate_report(
            tenant_id="tenant_001",
            report_type=ReportType.PERFORMANCE,
            tenant_data=tenant_data,
            peer_aggregates=peer_data
        )

        assert report.report_id is not None
        assert len(report.sections) > 0

    def test_generate_usage_report(self, generator):
        tenant_data = {"api_calls": 5000, "features_used": 10}
        peer_data = {"api_calls": 4000, "features_used": 8}

        report = generator.generate_report(
            tenant_id="tenant_001",
            report_type=ReportType.USAGE,
            tenant_data=tenant_data,
            peer_aggregates=peer_data
        )

        assert report.report_type == ReportType.USAGE

    def test_generate_cost_report(self, generator):
        tenant_data = {"monthly_cost": 500, "users": 50}
        peer_data = {"monthly_cost": 600, "users": 40}

        report = generator.generate_report(
            tenant_id="tenant_001",
            report_type=ReportType.COST,
            tenant_data=tenant_data,
            peer_aggregates=peer_data
        )

        assert report.report_type == ReportType.COST

    def test_generate_comprehensive_report(self, generator):
        tenant_data = {
            "avg_response_time": 150,
            "throughput": 1000,
            "error_rate": 1.5,
            "api_calls": 5000,
            "features_used": 10,
            "resource_utilization": 75,
            "automation_rate": 80
        }
        peer_data = {
            "avg_response_time": 200,
            "throughput": 800,
            "error_rate": 2.0,
            "api_calls": 4000,
            "features_used": 8,
            "resource_utilization": 60,
            "automation_rate": 70
        }

        report = generator.generate_report(
            tenant_id="tenant_001",
            report_type=ReportType.COMPREHENSIVE,
            tenant_data=tenant_data,
            peer_aggregates=peer_data
        )

        assert len(report.sections) > 0
        assert "health_score" in report.summary

    def test_get_report(self, generator):
        report = generator.generate_report(
            tenant_id="tenant_001",
            report_type=ReportType.PERFORMANCE,
            tenant_data={},
            peer_aggregates={}
        )

        retrieved = generator.get_report(report.report_id)
        assert retrieved is not None

    def test_get_tenant_reports(self, generator):
        generator.generate_report(
            tenant_id="tenant_001",
            report_type=ReportType.PERFORMANCE,
            tenant_data={},
            peer_aggregates={}
        )

        reports = generator.get_tenant_reports("tenant_001")
        assert len(reports) > 0

    def test_export_report(self, generator):
        report = generator.generate_report(
            tenant_id="tenant_001",
            report_type=ReportType.PERFORMANCE,
            tenant_data={},
            peer_aggregates={}
        )

        export = generator.export_report(report.report_id, format="json")
        assert export is not None
        assert "report_id" in export


class TestAnalyticsIntegration:
    """Integration tests"""

    def test_full_analytics_workflow(self):
        # Setup
        analytics = CrossTenantAnalytics(min_tenant_threshold=3)
        benchmark_engine = BenchmarkEngine(min_tenants_for_ranking=3)
        report_generator = ComparisonReportGenerator()

        # Record metrics
        for i in range(5):
            analytics.record(f"tenant_{i:03d}", "response_time", 100 + i * 20)
            analytics.record(f"tenant_{i:03d}", "throughput", 500 + i * 100)

        # Aggregate
        agg = analytics.aggregate("response_time", AggregationType.AVG)
        assert agg is not None

        # Benchmark
        metrics = {"response_time": 90, "throughput": 85, "error_rate": 95}
        benchmark = benchmark_engine.calculate_benchmark("tenant_001", "overall_performance", metrics)
        assert benchmark is not None

        # Generate report
        report = report_generator.generate_report(
            tenant_id="tenant_001",
            report_type=ReportType.PERFORMANCE,
            tenant_data={"avg_response_time": 150, "throughput": 1000, "error_rate": 1.5},
            peer_aggregates={"avg_response_time": 200, "throughput": 800, "error_rate": 2.0}
        )
        assert report is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
