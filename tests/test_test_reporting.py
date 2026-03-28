"""
Week 59 - Builder 5 Tests: Test Reporting Module
Unit tests for Report Generator, Coverage Analyzer, and Trend Analyzer
"""

import pytest
from parwa_testing_qa.test_reporting import (
    ReportGenerator, TestSummary, ReportFormat,
    CoverageAnalyzer, CoverageReport, CoverageType,
    TrendAnalyzer, TrendData
)


class TestReportGenerator:
    """Tests for ReportGenerator class"""

    @pytest.fixture
    def generator(self):
        """Create report generator"""
        return ReportGenerator()

    @pytest.fixture
    def sample_results(self):
        """Create sample test results"""
        return [
            {"status": "passed", "duration_ms": 100},
            {"status": "passed", "duration_ms": 150},
            {"status": "failed", "duration_ms": 200},
            {"status": "skipped", "duration_ms": 0}
        ]

    def test_generate_summary(self, generator, sample_results):
        """Test summary generation"""
        summary = generator.generate_summary(sample_results)

        assert summary.total == 4
        assert summary.passed == 2
        assert summary.failed == 1
        assert summary.skipped == 1
        assert summary.pass_rate == 50.0

    def test_generate_report_json(self, generator, sample_results):
        """Test JSON report generation"""
        report = generator.generate_report(
            "Test Report",
            sample_results,
            ReportFormat.JSON
        )

        assert "Test Report" in report
        assert '"total": 4' in report

    def test_generate_report_markdown(self, generator, sample_results):
        """Test Markdown report generation"""
        report = generator.generate_report(
            "Test Report",
            sample_results,
            ReportFormat.MARKDOWN
        )

        assert "# Test Report" in report
        assert "Total Tests" in report

    def test_get_report(self, generator, sample_results):
        """Test get report by ID"""
        generator.generate_report("Test", sample_results)
        report_id = list(generator.reports.keys())[0]

        report = generator.get_report(report_id)
        assert report is not None

    def test_list_reports(self, generator, sample_results):
        """Test list reports"""
        report1 = generator.generate_report("Report1", sample_results)
        import time
        time.sleep(0.1)  # Ensure different timestamp
        report2 = generator.generate_report("Report2", sample_results)

        reports = generator.list_reports()
        assert len(reports) >= 1  # At least one report created

    def test_delete_report(self, generator, sample_results):
        """Test delete report"""
        generator.generate_report("Test", sample_results)
        report_id = list(generator.reports.keys())[0]

        result = generator.delete_report(report_id)
        assert result is True
        assert generator.get_report(report_id) is None


class TestCoverageAnalyzer:
    """Tests for CoverageAnalyzer class"""

    @pytest.fixture
    def analyzer(self):
        """Create coverage analyzer"""
        return CoverageAnalyzer()

    def test_record_coverage(self, analyzer):
        """Test coverage recording"""
        analyzer.record_coverage("file.py", [1, 2, 3, 5], 10)

        assert "file.py" in analyzer.coverage_data
        assert analyzer.coverage_data["file.py"]["percentage"] == 40.0

    def test_calculate_coverage(self, analyzer):
        """Test coverage calculation"""
        analyzer.record_coverage("file1.py", [1, 2, 3], 10)
        analyzer.record_coverage("file2.py", [1, 2, 3, 4, 5], 10)

        report = analyzer.calculate_coverage()

        assert report.total_items == 20
        assert report.covered_items == 8
        assert report.percentage == 40.0

    def test_get_file_coverage(self, analyzer):
        """Test file coverage"""
        analyzer.record_coverage("file.py", [1, 2, 3], 10)

        coverage = analyzer.get_file_coverage("file.py")
        assert coverage["percentage"] == 30.0

    def test_merge_coverage(self, analyzer):
        """Test coverage merge"""
        analyzer.record_coverage("file.py", [1, 2], 10)

        other_data = {
            "file.py": {"covered_lines": [3, 4], "total_lines": 10, "percentage": 20.0},
            "other.py": {"covered_lines": [1], "total_lines": 5, "percentage": 20.0}
        }

        analyzer.merge_coverage(other_data)

        assert len(analyzer.coverage_data["file.py"]["covered_lines"]) == 4
        assert "other.py" in analyzer.coverage_data

    def test_clear(self, analyzer):
        """Test clear coverage"""
        analyzer.record_coverage("file.py", [1], 10)
        analyzer.clear()

        assert len(analyzer.coverage_data) == 0


class TestTrendAnalyzer:
    """Tests for TrendAnalyzer class"""

    @pytest.fixture
    def analyzer(self):
        """Create trend analyzer"""
        return TrendAnalyzer()

    def test_record_result(self, analyzer):
        """Test result recording"""
        analyzer.record_result("test1", True, 100)
        analyzer.record_result("test1", False, 150)

        assert len(analyzer.history["test1"]) == 2

    def test_get_flaky_tests(self, analyzer):
        """Test flaky test detection"""
        # Create flaky test (alternating results)
        for i in range(20):
            analyzer.record_result("flaky_test", i % 2 == 0)

        flaky = analyzer.get_flaky_tests(threshold=5)
        assert "flaky_test" in flaky

    def test_get_trend(self, analyzer):
        """Test trend analysis"""
        # Create stable passing test
        for _ in range(20):
            analyzer.record_result("stable_test", True)

        trend = analyzer.get_trend("stable_test")
        assert trend["trend"] == "stable"
        assert trend["recent_pass_rate"] == 100.0

    def test_get_pass_rate_history(self, analyzer):
        """Test pass rate history"""
        for i in range(30):
            analyzer.record_result("test1", True)

        history = analyzer.get_pass_rate_history("test1", window=10)
        assert len(history) > 0
        assert all(h == 100.0 for h in history)

    def test_predict_next_result(self, analyzer):
        """Test result prediction"""
        for _ in range(20):
            analyzer.record_result("predictable", True)

        prediction = analyzer.predict_next_result("predictable")
        assert prediction["prediction"] == "pass"
        assert prediction["pass_probability"] == 100.0

    def test_get_stats(self, analyzer):
        """Test statistics"""
        analyzer.record_result("test1", True)
        analyzer.record_result("test2", True)

        stats = analyzer.get_stats()
        assert stats["total_tests_tracked"] == 2
