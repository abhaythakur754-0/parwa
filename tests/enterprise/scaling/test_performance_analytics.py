"""
Tests for Performance Analytics Module - Week 52, Builder 5
"""

import pytest
from datetime import datetime, timedelta

from enterprise.scaling.performance_analytics import (
    PerformanceAnalytics,
    PerformanceMetric,
    PerformanceInsight,
    MetricStats,
    TimeSeriesStore,
    MetricsAnalyzer,
    MetricType,
    TrendDirection,
    Severity,
)
from enterprise.scaling.bottleneck_detector import (
    BottleneckDetector,
    Bottleneck,
    ResourceCollector,
    CorrelationResult,
    BottleneckPredictor,
    BottleneckType,
    BottleneckSeverity,
)
from enterprise.scaling.optimization_reporter import (
    OptimizationReporter,
    OptimizationEngine,
    OptimizationItem,
    OptimizationReport,
    ReportType,
    Priority,
    OptimizationCategory,
)


# ============================================================================
# Performance Analytics Tests
# ============================================================================

class TestPerformanceMetric:
    """Tests for PerformanceMetric class"""

    def test_init(self):
        """Test metric initialization"""
        metric = PerformanceMetric(
            name="cpu",
            metric_type=MetricType.CPU,
            value=50.0,
            unit="%",
        )
        assert metric.name == "cpu"
        assert metric.value == 50.0

    def test_to_dict(self):
        """Test to_dict method"""
        metric = PerformanceMetric(
            name="latency",
            metric_type=MetricType.LATENCY,
            value=100.0,
            unit="ms",
        )
        d = metric.to_dict()
        assert d["name"] == "latency"
        assert d["value"] == 100.0


class TestTimeSeriesStore:
    """Tests for TimeSeriesStore class"""

    def test_init(self):
        """Test store initialization"""
        store = TimeSeriesStore()
        assert len(store.data) == 0

    def test_add(self):
        """Test adding metric"""
        store = TimeSeriesStore()
        metric = PerformanceMetric(
            name="cpu",
            metric_type=MetricType.CPU,
            value=50.0,
            unit="%",
        )
        store.add(metric)
        assert len(store.data) == 1

    def test_get_series(self):
        """Test getting series"""
        store = TimeSeriesStore()
        for i in range(5):
            store.add(PerformanceMetric(
                name="cpu",
                metric_type=MetricType.CPU,
                value=50.0 + i,
                unit="%",
            ))

        series = store.get_series(MetricType.CPU, "cpu")
        assert len(series) == 5

    def test_get_latest(self):
        """Test getting latest"""
        store = TimeSeriesStore()
        for i in range(5):
            store.add(PerformanceMetric(
                name="cpu",
                metric_type=MetricType.CPU,
                value=50.0 + i,
                unit="%",
            ))

        latest = store.get_latest(MetricType.CPU, "cpu")
        assert latest.value == 54.0

    def test_get_all_types(self):
        """Test getting all metric types"""
        store = TimeSeriesStore()
        store.add(PerformanceMetric("cpu", MetricType.CPU, 50, "%"))
        store.add(PerformanceMetric("mem", MetricType.MEMORY, 60, "%"))

        types = store.get_all_types()
        assert len(types) == 2


class TestMetricsAnalyzer:
    """Tests for MetricsAnalyzer class"""

    def test_init(self):
        """Test analyzer initialization"""
        store = TimeSeriesStore()
        analyzer = MetricsAnalyzer(store)
        assert analyzer.store == store

    def test_calculate_stats(self):
        """Test calculating statistics"""
        store = TimeSeriesStore()
        for i in range(10):
            store.add(PerformanceMetric("cpu", MetricType.CPU, 50 + i, "%"))

        analyzer = MetricsAnalyzer(store)
        stats = analyzer.calculate_stats(MetricType.CPU, "cpu")

        assert stats.count == 10
        assert stats.min == 50
        assert stats.max == 59

    def test_calculate_stats_empty(self):
        """Test stats with no data"""
        store = TimeSeriesStore()
        analyzer = MetricsAnalyzer(store)
        stats = analyzer.calculate_stats(MetricType.CPU, "cpu")

        assert stats.count == 0

    def test_compare_periods(self):
        """Test comparing periods"""
        store = TimeSeriesStore()
        now = datetime.utcnow()

        # Period 1 data
        for i in range(5):
            store.add(PerformanceMetric(
                "cpu", MetricType.CPU, 50,
                timestamp=now - timedelta(hours=2),
                unit="%",
            ))

        # Period 2 data
        for i in range(5):
            store.add(PerformanceMetric(
                "cpu", MetricType.CPU, 60,
                timestamp=now - timedelta(hours=1),
                unit="%",
            ))

        analyzer = MetricsAnalyzer(store)
        comparison = analyzer.compare_periods(
            MetricType.CPU, "cpu",
            now - timedelta(hours=3), now - timedelta(hours=2),
            now - timedelta(hours=1), now,
        )

        assert "change_percent" in comparison


class TestPerformanceAnalytics:
    """Tests for PerformanceAnalytics class"""

    def test_init(self):
        """Test analytics initialization"""
        analytics = PerformanceAnalytics()
        assert len(analytics.thresholds) == 0

    def test_set_threshold(self):
        """Test setting threshold"""
        analytics = PerformanceAnalytics()
        analytics.set_threshold(MetricType.CPU, "cpu", warning=70, critical=90)
        assert "cpu:cpu" in analytics.thresholds

    def test_record(self):
        """Test recording metric"""
        analytics = PerformanceAnalytics()
        analytics.record(MetricType.CPU, "cpu", 50)
        assert len(analytics.store.data) == 1

    def test_threshold_check(self):
        """Test threshold checking"""
        analytics = PerformanceAnalytics()
        analytics.set_threshold(MetricType.CPU, "cpu", warning=70, critical=90)

        # Add some history first
        for i in range(10):
            analytics.record(MetricType.CPU, "cpu", 60)

        # Record above threshold
        analytics.record(MetricType.CPU, "cpu", 95)
        assert len(analytics.insights) > 0

    def test_get_dashboard_data(self):
        """Test getting dashboard data"""
        analytics = PerformanceAnalytics()
        analytics.record(MetricType.CPU, "cpu", 50)
        analytics.record(MetricType.MEMORY, "mem", 60)

        dashboard = analytics.get_dashboard_data()
        assert "metrics" in dashboard
        assert "insights" in dashboard

    def test_get_metric_report(self):
        """Test getting metric report"""
        analytics = PerformanceAnalytics()
        for i in range(10):
            analytics.record(MetricType.CPU, "cpu", 50 + i)

        report = analytics.get_metric_report(MetricType.CPU, "cpu")
        assert "stats" in report
        assert "data_points" in report

    def test_export_data(self):
        """Test exporting data"""
        analytics = PerformanceAnalytics()
        analytics.record(MetricType.CPU, "cpu", 50)

        exported = analytics.export_data()
        assert "metrics" in exported
        assert "insights" in exported


# ============================================================================
# Bottleneck Detector Tests
# ============================================================================

class TestResourceCollector:
    """Tests for ResourceCollector class"""

    def test_init(self):
        """Test collector initialization"""
        collector = ResourceCollector()
        assert len(collector.metrics) == 0

    def test_record(self):
        """Test recording metric"""
        collector = ResourceCollector()
        collector.record("cpu", 50, 100, 50)
        assert len(collector.metrics["cpu"]) == 1

    def test_get_latest(self):
        """Test getting latest"""
        collector = ResourceCollector()
        collector.record("cpu", 50, 100, 50)
        collector.record("cpu", 60, 100, 60)

        latest = collector.get_latest("cpu")
        assert latest.utilization_percent == 60

    def test_get_average(self):
        """Test getting average"""
        collector = ResourceCollector()
        collector.record("cpu", 40, 100, 40)
        collector.record("cpu", 50, 100, 50)
        collector.record("cpu", 60, 100, 60)

        avg = collector.get_average("cpu")
        assert avg == 50


class TestBottleneckDetector:
    """Tests for BottleneckDetector class"""

    def test_init(self):
        """Test detector initialization"""
        detector = BottleneckDetector()
        assert len(detector._detection_rules) > 0

    def test_record_resource(self):
        """Test recording resource"""
        detector = BottleneckDetector()
        detector.record_resource("cpu", 50)
        assert "cpu" in detector.collector.metrics

    def test_detect_cpu_bottleneck(self):
        """Test detecting CPU bottleneck"""
        detector = BottleneckDetector()

        # Add sustained high CPU
        for _ in range(10):
            detector.record_resource("cpu", 95)

        bottlenecks = detector.detect()
        cpu_bottlenecks = [b for b in bottlenecks if b.bottleneck_type == BottleneckType.CPU]
        assert len(cpu_bottlenecks) > 0

    def test_detect_no_bottleneck(self):
        """Test with no bottleneck"""
        detector = BottleneckDetector()

        # Add low CPU
        for _ in range(10):
            detector.record_resource("cpu", 30)

        bottlenecks = detector.detect()
        cpu_bottlenecks = [b for b in bottlenecks if b.bottleneck_type == BottleneckType.CPU]
        assert len(cpu_bottlenecks) == 0

    def test_set_custom_threshold(self):
        """Test setting custom threshold"""
        detector = BottleneckDetector()
        detector.set_custom_threshold("custom_resource", 50, 70)
        assert "custom_resource" in detector.thresholds

    def test_analyze_correlations(self):
        """Test correlation analysis"""
        detector = BottleneckDetector()

        # Add correlated metrics
        for i in range(20):
            detector.record_resource("cpu", 50 + i)
            detector.record_resource("memory", 50 + i)

        result = detector.analyze_correlations("cpu", "memory")
        assert result.correlation_coefficient > 0.5

    def test_get_bottleneck_summary(self):
        """Test getting bottleneck summary"""
        detector = BottleneckDetector()

        # Add some bottleneck detections
        for _ in range(10):
            detector.record_resource("cpu", 95)
        detector.detect()

        summary = detector.get_bottleneck_summary()
        assert "total_detected" in summary
        assert "by_severity" in summary


class TestBottleneckPredictor:
    """Tests for BottleneckPredictor class"""

    def test_init(self):
        """Test predictor initialization"""
        detector = BottleneckDetector()
        predictor = BottleneckPredictor(detector)
        assert predictor.detector == detector

    def test_predict_bottleneck_increasing(self):
        """Test predicting bottleneck with increasing trend"""
        detector = BottleneckDetector()
        predictor = BottleneckPredictor(detector)

        # Add increasing values
        for i in range(20):
            detector.record_resource("cpu", 50 + i * 2)

        prediction = predictor.predict_bottleneck("cpu", minutes_ahead=30)
        assert prediction is not None

    def test_predict_no_bottleneck(self):
        """Test predicting no bottleneck"""
        detector = BottleneckDetector()
        predictor = BottleneckPredictor(detector)

        # Add stable low values
        for i in range(20):
            detector.record_resource("cpu", 30)

        prediction = predictor.predict_bottleneck("cpu", minutes_ahead=30)
        assert prediction is None or prediction["severity"] != "critical"


class TestBottleneck:
    """Tests for Bottleneck class"""

    def test_init(self):
        """Test bottleneck initialization"""
        bottleneck = Bottleneck(
            bottleneck_type=BottleneckType.CPU,
            severity=BottleneckSeverity.HIGH,
            location="server1",
            description="High CPU",
            impact="Performance degradation",
            current_value=95,
            threshold_value=70,
        )
        assert bottleneck.bottleneck_type == BottleneckType.CPU
        assert bottleneck.severity == BottleneckSeverity.HIGH

    def test_to_dict(self):
        """Test to_dict method"""
        bottleneck = Bottleneck(
            bottleneck_type=BottleneckType.MEMORY,
            severity=BottleneckSeverity.CRITICAL,
            location="server1",
            description="High Memory",
            impact="OOM risk",
            current_value=95,
            threshold_value=80,
        )
        d = bottleneck.to_dict()
        assert d["type"] == "memory"
        assert d["severity"] == "critical"


# ============================================================================
# Optimization Reporter Tests
# ============================================================================

class TestOptimizationItem:
    """Tests for OptimizationItem class"""

    def test_init(self):
        """Test item initialization"""
        item = OptimizationItem(
            title="Optimize CPU",
            category=OptimizationCategory.PERFORMANCE,
            priority=Priority.HIGH,
            description="Reduce CPU usage",
            current_state="80%",
            recommended_state="60%",
            estimated_impact="20% improvement",
            effort="medium",
            cost="low",
        )
        assert item.title == "Optimize CPU"
        assert item.priority == Priority.HIGH

    def test_to_dict(self):
        """Test to_dict method"""
        item = OptimizationItem(
            title="Optimize Memory",
            category=OptimizationCategory.PERFORMANCE,
            priority=Priority.CRITICAL,
            description="Reduce memory usage",
            current_state="90%",
            recommended_state="70%",
            estimated_impact="Better stability",
            effort="high",
            cost="medium",
        )
        d = item.to_dict()
        assert d["title"] == "Optimize Memory"
        assert d["priority"] == "critical"


class TestOptimizationEngine:
    """Tests for OptimizationEngine class"""

    def test_init(self):
        """Test engine initialization"""
        engine = OptimizationEngine()
        assert len(engine._rules) > 0

    def test_analyze_cpu(self):
        """Test analyzing CPU metrics"""
        engine = OptimizationEngine()
        metrics = {"cpu_avg": 85}

        optimizations = engine.analyze(metrics)
        cpu_opts = [o for o in optimizations if "CPU" in o.title]
        assert len(cpu_opts) > 0

    def test_analyze_memory(self):
        """Test analyzing memory metrics"""
        engine = OptimizationEngine()
        metrics = {"memory_avg": 90}

        optimizations = engine.analyze(metrics)
        mem_opts = [o for o in optimizations if "Memory" in o.title]
        assert len(mem_opts) > 0

    def test_analyze_latency(self):
        """Test analyzing latency metrics"""
        engine = OptimizationEngine()
        metrics = {"latency_p95": 600}

        optimizations = engine.analyze(metrics)
        latency_opts = [o for o in optimizations if "Latency" in o.title]
        assert len(latency_opts) > 0

    def test_analyze_errors(self):
        """Test analyzing error rate"""
        engine = OptimizationEngine()
        metrics = {"error_rate": 5.0}

        optimizations = engine.analyze(metrics)
        error_opts = [o for o in optimizations if "Error" in o.title]
        assert len(error_opts) > 0

    def test_analyze_cost(self):
        """Test analyzing cost optimization"""
        engine = OptimizationEngine()
        metrics = {"resource_utilization": 20}

        optimizations = engine.analyze(metrics)
        cost_opts = [o for o in optimizations if o.category == OptimizationCategory.COST]
        assert len(cost_opts) > 0


class TestOptimizationReporter:
    """Tests for OptimizationReporter class"""

    def test_init(self):
        """Test reporter initialization"""
        reporter = OptimizationReporter()
        assert len(reporter.reports) == 0

    def test_generate_report(self):
        """Test generating report"""
        reporter = OptimizationReporter()
        metrics = {
            "cpu_avg": 85,
            "memory_avg": 80,
        }

        report = reporter.generate_report(
            ReportType.PERFORMANCE_SUMMARY,
            metrics,
        )
        assert report.report_id is not None
        assert len(report.optimizations) > 0

    def test_get_report(self):
        """Test getting report"""
        reporter = OptimizationReporter()
        metrics = {"cpu_avg": 50}
        report = reporter.generate_report(ReportType.PERFORMANCE_SUMMARY, metrics)

        retrieved = reporter.get_report(report.report_id)
        assert retrieved is not None

    def test_get_all_reports(self):
        """Test getting all reports"""
        reporter = OptimizationReporter()
        metrics = {"cpu_avg": 50}

        reporter.generate_report(ReportType.PERFORMANCE_SUMMARY, metrics)
        reporter.generate_report(ReportType.BOTTLENECK_ANALYSIS, metrics)

        all_reports = reporter.get_all_reports()
        assert len(all_reports) == 2

    def test_export_report(self):
        """Test exporting report"""
        reporter = OptimizationReporter()
        metrics = {"cpu_avg": 50}
        report = reporter.generate_report(ReportType.PERFORMANCE_SUMMARY, metrics)

        exported = reporter.export_report(report.report_id, "json")
        assert exported is not None
        assert "report_id" in exported

    def test_compare_reports(self):
        """Test comparing reports"""
        reporter = OptimizationReporter()

        report1 = reporter.generate_report(
            ReportType.PERFORMANCE_SUMMARY,
            {"cpu_avg": 50},
        )
        report2 = reporter.generate_report(
            ReportType.PERFORMANCE_SUMMARY,
            {"cpu_avg": 90},
        )

        comparison = reporter.compare_reports(report1.report_id, report2.report_id)
        assert "optimization_count_change" in comparison

    def test_get_trending_optimizations(self):
        """Test getting trending optimizations"""
        reporter = OptimizationReporter()

        # Generate multiple reports
        for i in range(5):
            reporter.generate_report(
                ReportType.PERFORMANCE_SUMMARY,
                {"cpu_avg": 80 + i * 5},
            )

        trending = reporter.get_trending_optimizations(days=30)
        assert "trending" in trending
