#!/usr/bin/env python3
"""
Test Summary Aggregator for PARWA

Aggregates test results with:
- Total tests count
- Pass/fail/skip counts
- Duration per test
- Slowest tests list
- Flaky tests detection
- Summary JSON output
"""

import os
import sys
import json
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from collections import defaultdict
import re


@dataclass
class TestResult:
    """Individual test result."""
    name: str
    classname: str
    status: str  # passed, failed, skipped, error
    duration: float  # seconds
    message: Optional[str] = None
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    file: Optional[str] = None
    line: Optional[int] = None


@dataclass
class TestSuite:
    """Test suite results."""
    name: str
    tests: int
    passed: int
    failed: int
    skipped: int
    errors: int
    duration: float
    test_results: List[TestResult] = field(default_factory=list)


@dataclass
class TestSummary:
    """Complete test summary."""
    generated_at: str
    total_tests: int
    passed: int
    failed: int
    skipped: int
    errors: int
    pass_rate: float
    total_duration: float
    slowest_tests: List[TestResult] = field(default_factory=list)
    failed_tests: List[TestResult] = field(default_factory=list)
    flaky_tests: List[str] = field(default_factory=list)
    suites: List[TestSuite] = field(default_factory=list)
    all_passed: bool = True


class TestSummaryAggregator:
    """
    Aggregates and analyzes test results.
    
    Features:
    - Parse JUnit XML reports
    - Aggregate multiple test suites
    - Identify slowest tests
    - Detect flaky tests
    - Generate comprehensive summaries
    """
    
    JUNIT_FILE = "junit.xml"
    HISTORY_FILE = "test_history.json"
    FLAKY_THRESHOLD = 3  # Number of runs with different results to consider flaky
    
    def __init__(
        self,
        project_root: Optional[Path] = None,
        output_dir: Optional[Path] = None
    ):
        """Initialize test summary aggregator."""
        self.project_root = project_root or Path.cwd()
        self.output_dir = output_dir or self.project_root / "test-reports"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
    def run_pytest(
        self,
        test_paths: List[str] = None,
        extra_args: List[str] = None,
        junit_file: Optional[str] = None
    ) -> int:
        """
        Run pytest and generate JUnit XML report.
        
        Args:
            test_paths: Paths to test directories
            extra_args: Additional pytest arguments
            junit_file: Custom JUnit output file name
            
        Returns:
            pytest exit code
        """
        if test_paths is None:
            test_paths = ["tests/"]
            
        junit_output = junit_file or str(self.output_dir / self.JUNIT_FILE)
            
        cmd = [
            sys.executable, "-m", "pytest",
            *test_paths,
            f"--junitxml={junit_output}",
            "--durations=20",
            "-v",
        ]
        
        if extra_args:
            cmd.extend(extra_args)
            
        print(f"Running tests: {' '.join(cmd)}")
        result = subprocess.run(cmd, cwd=self.project_root)
        return result.returncode
    
    def parse_junit_xml(self, xml_path: Optional[Path] = None) -> List[TestSuite]:
        """
        Parse JUnit XML report.
        
        Args:
            xml_path: Path to JUnit XML file
            
        Returns:
            List of TestSuite objects
        """
        xml_path = xml_path or self.output_dir / self.JUNIT_FILE
        
        if not xml_path.exists():
            raise FileNotFoundError(f"JUnit XML report not found: {xml_path}")
            
        tree = ET.parse(xml_path)
        root = tree.getroot()
        
        suites = []
        
        # Handle both testsuites and testsuite as root
        testsuites = root.findall(".//testsuite") if root.tag == "testsuites" else [root]
        
        for ts in testsuites:
            suite_name = ts.attrib.get("name", "unknown")
            suite_tests = int(ts.attrib.get("tests", 0))
            suite_failures = int(ts.attrib.get("failures", 0))
            suite_errors = int(ts.attrib.get("errors", 0))
            suite_skipped = int(ts.attrib.get("skipped", 0))
            suite_time = float(ts.attrib.get("time", 0))
            suite_passed = suite_tests - suite_failures - suite_errors - suite_skipped
            
            test_results = []
            
            for testcase in ts.findall(".//testcase"):
                name = testcase.attrib.get("name", "unknown")
                classname = testcase.attrib.get("classname", "")
                time = float(testcase.attrib.get("time", 0))
                file = testcase.attrib.get("file")
                line = int(testcase.attrib.get("line", 0)) if "line" in testcase.attrib else None
                
                # Determine status
                status = "passed"
                message = None
                error_type = None
                error_message = None
                
                failure = testcase.find("failure")
                if failure is not None:
                    status = "failed"
                    message = failure.attrib.get("message")
                    error_type = failure.attrib.get("type")
                    error_message = failure.text
                
                error = testcase.find("error")
                if error is not None:
                    status = "error"
                    message = error.attrib.get("message")
                    error_type = error.attrib.get("type")
                    error_message = error.text
                
                skipped = testcase.find("skipped")
                if skipped is not None:
                    status = "skipped"
                    message = skipped.attrib.get("message")
                
                test_results.append(TestResult(
                    name=name,
                    classname=classname,
                    status=status,
                    duration=time,
                    message=message,
                    error_type=error_type,
                    error_message=error_message,
                    file=file,
                    line=line
                ))
            
            suites.append(TestSuite(
                name=suite_name,
                tests=suite_tests,
                passed=suite_passed,
                failed=suite_failures,
                skipped=suite_skipped,
                errors=suite_errors,
                duration=suite_time,
                test_results=test_results
            ))
        
        return suites
    
    def detect_flaky_tests(self, current_results: List[TestSuite]) -> List[str]:
        """
        Detect flaky tests based on historical results.
        
        Args:
            current_results: Current test results
            
        Returns:
            List of flaky test names
        """
        history_file = self.output_dir / self.HISTORY_FILE
        
        # Load history
        history = []
        if history_file.exists():
            with open(history_file, "r") as f:
                history = json.load(f)
        
        # Build test status map
        test_status_map = defaultdict(list)
        
        for run in history[-10:]:  # Last 10 runs
            for test_name, status in run.get("tests", {}).items():
                test_status_map[test_name].append(status)
        
        # Add current results
        current_tests = {}
        for suite in current_results:
            for test in suite.test_results:
                full_name = f"{test.classname}::{test.name}"
                test_status_map[full_name].append(test.status)
                current_tests[full_name] = test.status
        
        # Save current run
        history.append({
            "timestamp": datetime.now().isoformat(),
            "tests": current_tests
        })
        
        with open(history_file, "w") as f:
            json.dump(history[-30:], f, indent=2)  # Keep last 30 runs
        
        # Detect flaky tests (tests that have both passed and failed in recent runs)
        flaky_tests = []
        for test_name, statuses in test_status_map.items():
            if len(set(statuses)) > 1 and len(statuses) >= self.FLAKY_THRESHOLD:
                flaky_tests.append(test_name)
        
        return flaky_tests
    
    def aggregate_results(
        self,
        suites: List[TestSuite],
        detect_flaky: bool = True
    ) -> TestSummary:
        """
        Aggregate test results into a summary.
        
        Args:
            suites: List of test suites
            detect_flaky: Whether to detect flaky tests
            
        Returns:
            TestSummary object
        """
        total_tests = 0
        total_passed = 0
        total_failed = 0
        total_skipped = 0
        total_errors = 0
        total_duration = 0.0
        all_results: List[TestResult] = []
        failed_results: List[TestResult] = []
        
        for suite in suites:
            total_tests += suite.tests
            total_passed += suite.passed
            total_failed += suite.failed
            total_skipped += suite.skipped
            total_errors += suite.errors
            total_duration += suite.duration
            all_results.extend(suite.test_results)
            
            for test in suite.test_results:
                if test.status in ("failed", "error"):
                    failed_results.append(test)
        
        pass_rate = (total_passed / total_tests * 100) if total_tests > 0 else 0
        
        # Get slowest tests (top 10)
        sorted_results = sorted(all_results, key=lambda t: t.duration, reverse=True)
        slowest_tests = sorted_results[:10]
        
        # Detect flaky tests
        flaky_tests = []
        if detect_flaky:
            flaky_tests = self.detect_flaky_tests(suites)
        
        return TestSummary(
            generated_at=datetime.now().isoformat(),
            total_tests=total_tests,
            passed=total_passed,
            failed=total_failed,
            skipped=total_skipped,
            errors=total_errors,
            pass_rate=round(pass_rate, 2),
            total_duration=total_duration,
            slowest_tests=slowest_tests,
            failed_tests=failed_results,
            flaky_tests=flaky_tests,
            suites=suites,
            all_passed=(total_failed == 0 and total_errors == 0)
        )
    
    def generate_summary_html(self, summary: TestSummary) -> str:
        """
        Generate HTML summary report.
        
        Args:
            summary: TestSummary object
            
        Returns:
            HTML string
        """
        status_color = "green" if summary.all_passed else "red"
        status_text = "ALL PASSED" if summary.all_passed else "SOME FAILURES"
        
        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>Test Summary - PARWA</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 40px; }}
        .header {{ background: #f8f9fa; padding: 20px; border-radius: 8px; margin-bottom: 20px; }}
        .status {{ display: inline-block; padding: 5px 15px; border-radius: 4px; font-weight: bold; }}
        .status.pass {{ background: #d4edda; color: #155724; }}
        .status.fail {{ background: #f8d7da; color: #721c24; }}
        .stats {{ display: grid; grid-template-columns: repeat(5, 1fr); gap: 20px; margin: 20px 0; }}
        .stat-card {{ background: #fff; border: 1px solid #dee2e6; border-radius: 8px; padding: 20px; text-align: center; }}
        .stat-value {{ font-size: 2em; font-weight: bold; }}
        .stat-label {{ color: #666; font-size: 0.9em; }}
        .passed {{ color: #28a745; }}
        .failed {{ color: #dc3545; }}
        .skipped {{ color: #6c757d; }}
        .errors {{ color: #fd7e14; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #dee2e6; }}
        th {{ background: #f8f9fa; }}
        .slow {{ color: #fd7e14; }}
        .flaky {{ background: #fff3cd; padding: 10px; border-radius: 4px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Test Summary</h1>
        <p>Generated: {summary.generated_at}</p>
        <span class="status {status_color}">{status_text}</span>
    </div>
    
    <div class="stats">
        <div class="stat-card">
            <div class="stat-value">{summary.total_tests}</div>
            <div class="stat-label">Total Tests</div>
        </div>
        <div class="stat-card">
            <div class="stat-value passed">{summary.passed}</div>
            <div class="stat-label">Passed</div>
        </div>
        <div class="stat-card">
            <div class="stat-value failed">{summary.failed}</div>
            <div class="stat-label">Failed</div>
        </div>
        <div class="stat-card">
            <div class="stat-value skipped">{summary.skipped}</div>
            <div class="stat-label">Skipped</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{summary.pass_rate:.1f}%</div>
            <div class="stat-label">Pass Rate</div>
        </div>
    </div>
    
    <p><strong>Total Duration:</strong> {summary.total_duration:.2f}s</p>
"""
        
        if summary.flaky_tests:
            html_content += f"""
    <div class="flaky">
        <h3>⚠️ Flaky Tests Detected</h3>
        <ul>
            {''.join(f'<li>{test}</li>' for test in summary.flaky_tests)}
        </ul>
    </div>
"""
        
        html_content += """
    <h2>Slowest Tests (Top 10)</h2>
    <table>
        <thead>
            <tr>
                <th>Test</th>
                <th>Duration</th>
                <th>Status</th>
            </tr>
        </thead>
        <tbody>
"""
        
        for test in summary.slowest_tests:
            duration_class = "slow" if test.duration > 1.0 else ""
            html_content += f"""
            <tr>
                <td>{test.classname}::{test.name}</td>
                <td class="{duration_class}">{test.duration:.3f}s</td>
                <td class="{test.status}">{test.status}</td>
            </tr>
"""
        
        html_content += """
        </tbody>
    </table>
"""
        
        if summary.failed_tests:
            html_content += """
    <h2>Failed Tests</h2>
    <table>
        <thead>
            <tr>
                <th>Test</th>
                <th>Error</th>
                <th>Message</th>
            </tr>
        </thead>
        <tbody>
"""
            for test in summary.failed_tests:
                html_content += f"""
            <tr>
                <td>{test.classname}::{test.name}</td>
                <td>{test.error_type or 'N/A'}</td>
                <td><pre>{test.error_message or test.message or 'N/A'}</pre></td>
            </tr>
"""
            html_content += """
        </tbody>
    </table>
"""
        
        html_content += """
</body>
</html>
"""
        return html_content
    
    def generate_summary(self, run_tests: bool = True) -> TestSummary:
        """
        Generate complete test summary.
        
        Args:
            run_tests: Whether to run tests first
            
        Returns:
            TestSummary object
        """
        if run_tests:
            exit_code = self.run_pytest()
            print(f"Tests completed with exit code: {exit_code}")
        
        # Parse JUnit XML
        suites = self.parse_junit_xml()
        
        # Aggregate results
        summary = self.aggregate_results(suites)
        
        # Generate HTML summary
        html = self.generate_summary_html(summary)
        with open(self.output_dir / "test_summary.html", "w") as f:
            f.write(html)
        
        # Save JSON summary
        summary_dict = {
            "generated_at": summary.generated_at,
            "total_tests": summary.total_tests,
            "passed": summary.passed,
            "failed": summary.failed,
            "skipped": summary.skipped,
            "errors": summary.errors,
            "pass_rate": summary.pass_rate,
            "total_duration": summary.total_duration,
            "all_passed": summary.all_passed,
            "flaky_tests": summary.flaky_tests,
            "slowest_tests": [
                {
                    "name": f"{t.classname}::{t.name}",
                    "duration": t.duration,
                    "status": t.status
                }
                for t in summary.slowest_tests
            ],
            "failed_tests": [
                {
                    "name": f"{t.classname}::{t.name}",
                    "error_type": t.error_type,
                    "message": t.message
                }
                for t in summary.failed_tests
            ],
            "suites": [
                {
                    "name": s.name,
                    "tests": s.tests,
                    "passed": s.passed,
                    "failed": s.failed,
                    "skipped": s.skipped,
                    "errors": s.errors,
                    "duration": s.duration
                }
                for s in summary.suites
            ]
        }
        
        with open(self.output_dir / "test_summary.json", "w") as f:
            json.dump(summary_dict, f, indent=2)
        
        return summary


def main():
    """Main entry point for test summary generation."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate test summary for PARWA")
    parser.add_argument("--output-dir", type=Path, default=Path("test-reports"), help="Output directory")
    parser.add_argument("--skip-tests", action="store_true", help="Skip running tests")
    parser.add_argument("--project-root", type=Path, default=None, help="Project root directory")
    
    args = parser.parse_args()
    
    aggregator = TestSummaryAggregator(
        project_root=args.project_root,
        output_dir=args.output_dir
    )
    
    summary = aggregator.generate_summary(run_tests=not args.skip_tests)
    
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print(f"Total Tests: {summary.total_tests}")
    print(f"Passed: {summary.passed}")
    print(f"Failed: {summary.failed}")
    print(f"Skipped: {summary.skipped}")
    print(f"Errors: {summary.errors}")
    print(f"Pass Rate: {summary.pass_rate:.2f}%")
    print(f"Duration: {summary.total_duration:.2f}s")
    print(f"Status: {'ALL PASSED ✓' if summary.all_passed else 'SOME FAILURES ✗'}")
    print("=" * 60)
    
    if not summary.all_passed:
        sys.exit(1)


if __name__ == "__main__":
    main()
