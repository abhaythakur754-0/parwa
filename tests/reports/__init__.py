"""
Test Reports Module for PARWA

This module provides comprehensive test reporting capabilities:
- Coverage reports with threshold enforcement
- Test summary aggregation with flaky test detection
- JUnit XML report generation for CI/CD

Usage:
    # Generate coverage report
    python -m tests.reports.coverage_report --threshold 80
    
    # Generate test summary
    python -m tests.reports.test_summary --output-dir test-reports
    
    # Generate JUnit XML
    python -m tests.reports.junit_report --input results.json --output junit.xml
"""

from .coverage_report import CoverageReportGenerator, CoverageReport, CoverageStats
from .test_summary import TestSummaryAggregator, TestSummary, TestResult, TestSuite
from .junit_report import JUnitReportGenerator, TestCase, TestSuite as JUnitTestSuite

__all__ = [
    "CoverageReportGenerator",
    "CoverageReport",
    "CoverageStats",
    "TestSummaryAggregator",
    "TestSummary",
    "TestResult",
    "TestSuite",
    "JUnitReportGenerator",
    "TestCase",
    "JUnitTestSuite",
]

__version__ = "1.0.0"
