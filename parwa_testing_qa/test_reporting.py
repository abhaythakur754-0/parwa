"""
Week 59 - Builder 5: Test Reporting Module
Report generation, coverage analysis, and trend analysis
"""

import time
import json
import threading
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


class ReportFormat(Enum):
    """Report output formats"""
    JSON = "json"
    HTML = "html"
    MARKDOWN = "markdown"
    JUNIT = "junit"


class CoverageType(Enum):
    """Coverage types"""
    LINE = "line"
    BRANCH = "branch"
    FUNCTION = "function"
    STATEMENT = "statement"


@dataclass
class TestSummary:
    """Test execution summary"""
    total: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    errors: int = 0
    duration_ms: float = 0
    pass_rate: float = 0


@dataclass
class CoverageReport:
    """Coverage report data"""
    coverage_type: CoverageType
    total_items: int = 0
    covered_items: int = 0
    percentage: float = 0
    file_coverage: Dict[str, float] = field(default_factory=dict)
    uncovered_lines: Dict[str, List[int]] = field(default_factory=dict)


@dataclass
class TrendData:
    """Trend data point"""
    timestamp: float
    value: float
    metadata: Dict[str, Any] = field(default_factory=dict)


class ReportGenerator:
    """
    Report generator for test reports and summaries
    """

    def __init__(self):
        self.reports: Dict[str, Dict[str, Any]] = {}
        self.templates: Dict[str, str] = {}
        self.lock = threading.Lock()

    def generate_summary(self, test_results: List[Dict[str, Any]]) -> TestSummary:
        """Generate test summary from results"""
        summary = TestSummary()

        for result in test_results:
            summary.total += 1
            status = result.get("status", "unknown")

            if status == "passed":
                summary.passed += 1
            elif status == "failed":
                summary.failed += 1
            elif status == "skipped":
                summary.skipped += 1
            else:
                summary.errors += 1

            summary.duration_ms += result.get("duration_ms", 0)

        if summary.total > 0:
            summary.pass_rate = (summary.passed / summary.total) * 100

        return summary

    def generate_report(self, name: str, test_results: List[Dict[str, Any]],
                        format: ReportFormat = ReportFormat.JSON) -> str:
        """Generate a test report"""
        summary = self.generate_summary(test_results)
        report_id = f"report-{int(time.time())}"

        report_data = {
            "id": report_id,
            "name": name,
            "generated_at": time.time(),
            "summary": {
                "total": summary.total,
                "passed": summary.passed,
                "failed": summary.failed,
                "skipped": summary.skipped,
                "errors": summary.errors,
                "duration_ms": summary.duration_ms,
                "pass_rate": summary.pass_rate
            },
            "results": test_results
        }

        with self.lock:
            self.reports[report_id] = report_data

        if format == ReportFormat.JSON:
            return json.dumps(report_data, indent=2)
        elif format == ReportFormat.MARKDOWN:
            return self._to_markdown(report_data)
        else:
            return json.dumps(report_data)

    def _to_markdown(self, report: Dict[str, Any]) -> str:
        """Convert report to markdown"""
        summary = report["summary"]
        lines = [
            f"# {report['name']}",
            "",
            "## Summary",
            "",
            f"- **Total Tests**: {summary['total']}",
            f"- **Passed**: {summary['passed']}",
            f"- **Failed**: {summary['failed']}",
            f"- **Skipped**: {summary['skipped']}",
            f"- **Errors**: {summary['errors']}",
            f"- **Pass Rate**: {summary['pass_rate']:.1f}%",
            f"- **Duration**: {summary['duration_ms']:.0f}ms",
            ""
        ]
        return "\n".join(lines)

    def get_report(self, report_id: str) -> Optional[Dict[str, Any]]:
        """Get a report by ID"""
        return self.reports.get(report_id)

    def list_reports(self) -> List[str]:
        """List all report IDs"""
        return list(self.reports.keys())

    def delete_report(self, report_id: str) -> bool:
        """Delete a report"""
        with self.lock:
            if report_id in self.reports:
                del self.reports[report_id]
                return True
        return False


class CoverageAnalyzer:
    """
    Coverage analyzer for code and branch coverage
    """

    def __init__(self):
        self.coverage_data: Dict[str, Dict[str, Any]] = {}
        self.lock = threading.Lock()

    def record_coverage(self, file_path: str, covered_lines: List[int],
                        total_lines: int) -> None:
        """Record coverage data for a file"""
        with self.lock:
            self.coverage_data[file_path] = {
                "covered_lines": covered_lines,
                "total_lines": total_lines,
                "percentage": len(covered_lines) / total_lines * 100 if total_lines > 0 else 0
            }

    def calculate_coverage(self, coverage_type: CoverageType = CoverageType.LINE) -> CoverageReport:
        """Calculate overall coverage"""
        total_items = 0
        covered_items = 0
        file_coverage = {}
        uncovered_lines = {}

        for file_path, data in self.coverage_data.items():
            if coverage_type == CoverageType.LINE:
                total = data["total_lines"]
                covered = len(data["covered_lines"])
                total_items += total
                covered_items += covered
                file_coverage[file_path] = (covered / total * 100) if total > 0 else 0

                # Identify uncovered lines
                uncovered = [i for i in range(1, total + 1)
                            if i not in data["covered_lines"]]
                if uncovered:
                    uncovered_lines[file_path] = uncovered

        return CoverageReport(
            coverage_type=coverage_type,
            total_items=total_items,
            covered_items=covered_items,
            percentage=(covered_items / total_items * 100) if total_items > 0 else 0,
            file_coverage=file_coverage,
            uncovered_lines=uncovered_lines
        )

    def get_file_coverage(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Get coverage for a specific file"""
        return self.coverage_data.get(file_path)

    def merge_coverage(self, other_data: Dict[str, Dict[str, Any]]) -> None:
        """Merge coverage data from another source"""
        with self.lock:
            for file_path, data in other_data.items():
                if file_path in self.coverage_data:
                    # Merge covered lines
                    existing = set(self.coverage_data[file_path]["covered_lines"])
                    new = set(data["covered_lines"])
                    self.coverage_data[file_path]["covered_lines"] = list(existing | new)
                else:
                    self.coverage_data[file_path] = data

    def clear(self) -> None:
        """Clear all coverage data"""
        with self.lock:
            self.coverage_data.clear()


class TrendAnalyzer:
    """
    Trend analyzer for test history and flaky tests
    """

    def __init__(self):
        self.history: Dict[str, List[TrendData]] = defaultdict(list)
        self.flaky_tests: Dict[str, Dict[str, Any]] = {}
        self.lock = threading.Lock()

    def record_result(self, test_id: str, passed: bool,
                      duration_ms: float = 0) -> None:
        """Record a test result"""
        trend = TrendData(
            timestamp=time.time(),
            value=1 if passed else 0,
            metadata={"duration_ms": duration_ms}
        )

        with self.lock:
            self.history[test_id].append(trend)

            # Keep last 100 results
            if len(self.history[test_id]) > 100:
                self.history[test_id] = self.history[test_id][-100:]

            # Check for flakiness
            self._update_flakiness(test_id)

    def _update_flakiness(self, test_id: str) -> None:
        """Update flakiness score for a test"""
        history = self.history[test_id]
        if len(history) < 5:
            return

        # Calculate flakiness based on recent results
        recent = history[-20:]
        results = [t.value for t in recent]

        # Flakiness = variance in results
        mean = sum(results) / len(results)
        if 0 < mean < 1:  # Some passes, some fails
            variance = sum((r - mean) ** 2 for r in results) / len(results)
            flakiness_score = variance * 100
        else:
            flakiness_score = 0

        self.flaky_tests[test_id] = {
            "flakiness_score": flakiness_score,
            "pass_rate": mean * 100,
            "sample_size": len(recent)
        }

    def get_flaky_tests(self, threshold: float = 10) -> List[str]:
        """Get list of flaky tests"""
        return [
            test_id for test_id, data in self.flaky_tests.items()
            if data["flakiness_score"] >= threshold
        ]

    def get_trend(self, test_id: str) -> Dict[str, Any]:
        """Get trend data for a test"""
        history = self.history.get(test_id, [])
        if not history:
            return {"trend": "unknown", "data": []}

        values = [t.value for t in history]
        recent = values[-10:]
        older = values[-20:-10] if len(values) >= 20 else values[:len(values)//2]

        recent_rate = sum(recent) / len(recent) if recent else 0
        older_rate = sum(older) / len(older) if older else 0

        if recent_rate > older_rate + 0.1:
            trend = "improving"
        elif recent_rate < older_rate - 0.1:
            trend = "declining"
        else:
            trend = "stable"

        return {
            "trend": trend,
            "recent_pass_rate": recent_rate * 100,
            "previous_pass_rate": older_rate * 100,
            "data": [
                {"timestamp": t.timestamp, "passed": bool(t.value)}
                for t in history[-20:]
            ]
        }

    def get_pass_rate_history(self, test_id: str,
                              window: int = 20) -> List[float]:
        """Get pass rate history"""
        history = self.history.get(test_id, [])
        if len(history) < window:
            return []

        rates = []
        for i in range(len(history) - window + 1):
            window_data = history[i:i + window]
            rate = sum(t.value for t in window_data) / window
            rates.append(rate * 100)

        return rates

    def predict_next_result(self, test_id: str) -> Dict[str, Any]:
        """Predict next test result probability"""
        history = self.history.get(test_id, [])
        if len(history) < 5:
            return {"confidence": 0, "prediction": None}

        recent = [t.value for t in history[-10:]]
        pass_rate = sum(recent) / len(recent)

        return {
            "confidence": min(1.0, len(history) / 20),
            "prediction": "pass" if pass_rate > 0.5 else "fail",
            "pass_probability": pass_rate * 100
        }

    def get_stats(self) -> Dict[str, Any]:
        """Get overall statistics"""
        total_tests = len(self.history)
        flaky_count = len(self.get_flaky_tests())

        return {
            "total_tests_tracked": total_tests,
            "flaky_tests": flaky_count,
            "flaky_percentage": (flaky_count / total_tests * 100) if total_tests > 0 else 0
        }
