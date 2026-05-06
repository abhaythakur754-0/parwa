#!/usr/bin/env python3
"""
JUnit XML Report Generator for PARWA

Generates JUnit XML reports with:
- JUnit XML format output
- Test case details
- Failure messages
- CI/CD integration
"""

import os
import sys
import json
import xml.etree.ElementTree as ET
from xml.dom import minidom
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field


@dataclass
class TestCase:
    """Test case data for JUnit report."""
    name: str
    classname: str
    time: float
    status: str = "passed"
    message: Optional[str] = None
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    file: Optional[str] = None
    line: Optional[int] = None
    system_out: Optional[str] = None
    system_err: Optional[str] = None


@dataclass
class TestSuite:
    """Test suite data for JUnit report."""
    name: str
    tests: List[TestCase] = field(default_factory=list)
    
    @property
    def test_count(self) -> int:
        return len(self.tests)
    
    @property
    def failure_count(self) -> int:
        return sum(1 for t in self.tests if t.status == "failed")
    
    @property
    def error_count(self) -> int:
        return sum(1 for t in self.tests if t.status == "error")
    
    @property
    def skipped_count(self) -> int:
        return sum(1 for t in self.tests if t.status == "skipped")
    
    @property
    def time(self) -> float:
        return sum(t.time for t in self.tests)


class JUnitReportGenerator:
    """
    Generates JUnit XML reports for CI/CD integration.
    
    Features:
    - Standard JUnit XML format
    - Test case details with timing
    - Failure and error messages
    - CI/CD compatible output
    - Merge multiple test results
    """
    
    JUNIT_SCHEMA = "https://maven.apache.org/surefire/maven-surefire-plugin/xsd/surefire-test-report.xsd"
    
    def __init__(self, output_dir: Optional[Path] = None):
        """Initialize JUnit report generator."""
        self.output_dir = output_dir or Path("test-reports")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.test_suites: List[TestSuite] = []
    
    def add_suite(self, suite: TestSuite) -> None:
        """Add a test suite to the report."""
        self.test_suites.append(suite)
    
    def add_test_case(
        self,
        suite_name: str,
        test_case: TestCase
    ) -> None:
        """Add a test case to a suite."""
        for suite in self.test_suites:
            if suite.name == suite_name:
                suite.tests.append(test_case)
                return
        
        # Create new suite if it doesn't exist
        new_suite = TestSuite(name=suite_name, tests=[test_case])
        self.test_suites.append(new_suite)
    
    def create_test_case_element(self, test: TestCase) -> ET.Element:
        """Create XML element for a test case."""
        attrs = {
            "name": test.name,
            "classname": test.classname,
            "time": f"{test.time:.3f}"
        }
        
        if test.file:
            attrs["file"] = test.file
        if test.line:
            attrs["line"] = str(test.line)
        
        testcase = ET.Element("testcase", attrs)
        
        if test.status == "failed":
            failure = ET.SubElement(
                testcase,
                "failure",
                {
                    "type": test.error_type or "AssertionError",
                    "message": test.message or "Test failed"
                }
            )
            if test.error_message:
                failure.text = test.error_message
        
        elif test.status == "error":
            error = ET.SubElement(
                testcase,
                "error",
                {
                    "type": test.error_type or "Exception",
                    "message": test.message or "Test error"
                }
            )
            if test.error_message:
                error.text = test.error_message
        
        elif test.status == "skipped":
            skipped = ET.SubElement(
                testcase,
                "skipped",
                {"message": test.message or "Test skipped"}
            )
        
        if test.system_out:
            system_out = ET.SubElement(testcase, "system-out")
            system_out.text = test.system_out
        
        if test.system_err:
            system_err = ET.SubElement(testcase, "system-err")
            system_err.text = test.system_err
        
        return testcase
    
    def create_suite_element(self, suite: TestSuite) -> ET.Element:
        """Create XML element for a test suite."""
        attrs = {
            "name": suite.name,
            "tests": str(suite.test_count),
            "failures": str(suite.failure_count),
            "errors": str(suite.error_count),
            "skipped": str(suite.skipped_count),
            "time": f"{suite.time:.3f}",
            "timestamp": datetime.now().isoformat()
        }
        
        testsuite = ET.Element("testsuite", attrs)
        
        for test in suite.tests:
            testsuite.append(self.create_test_case_element(test))
        
        return testsuite
    
    def generate_xml(
        self,
        include_schema: bool = False
    ) -> str:
        """
        Generate JUnit XML string.
        
        Args:
            include_schema: Whether to include XML schema
            
        Returns:
            XML string
        """
        if len(self.test_suites) == 1:
            root = self.create_suite_element(self.test_suites[0])
        else:
            root = ET.Element("testsuites")
            
            total_tests = sum(s.test_count for s in self.test_suites)
            total_failures = sum(s.failure_count for s in self.test_suites)
            total_errors = sum(s.error_count for s in self.test_suites)
            total_skipped = sum(s.skipped_count for s in self.test_suites)
            total_time = sum(s.time for s in self.test_suites)
            
            root.set("name", "PARWA Test Suite")
            root.set("tests", str(total_tests))
            root.set("failures", str(total_failures))
            root.set("errors", str(total_errors))
            root.set("skipped", str(total_skipped))
            root.set("time", f"{total_time:.3f}")
            
            for suite in self.test_suites:
                root.append(self.create_suite_element(suite))
        
        # Pretty print
        xml_str = ET.tostring(root, encoding="unicode")
        dom = minidom.parseString(xml_str)
        pretty_xml = dom.toprettyxml(indent="  ")
        
        # Remove extra blank lines
        lines = [line for line in pretty_xml.split("\n") if line.strip()]
        return "\n".join(lines)
    
    def save_xml(
        self,
        filename: str = "junit.xml",
        include_schema: bool = False
    ) -> Path:
        """
        Save JUnit XML to file.
        
        Args:
            filename: Output filename
            include_schema: Whether to include XML schema
            
        Returns:
            Path to saved file
        """
        output_path = self.output_dir / filename
        
        xml_content = self.generate_xml(include_schema)
        
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(xml_content)
        
        return output_path
    
    def from_pytest_results(
        self,
        pytest_json: str
    ) -> None:
        """
        Load test results from pytest JSON report.
        
        Args:
            pytest_json: Path to pytest JSON report
        """
        with open(pytest_json, "r") as f:
            data = json.load(f)
        
        for test in data.get("tests", []):
            test_case = TestCase(
                name=test.get("name", "unknown"),
                classname=test.get("classname", ""),
                time=test.get("duration", 0),
                status=test.get("outcome", "passed"),
                message=test.get("message"),
                error_type=test.get("error_type"),
                error_message=test.get("error_message"),
                file=test.get("file"),
                line=test.get("line")
            )
            
            suite_name = test.get("classname", "default")
            self.add_test_case(suite_name, test_case)
    
    def from_dict(self, data: Dict[str, Any]) -> None:
        """
        Load test results from dictionary.
        
        Args:
            data: Dictionary with test results
        """
        for suite_data in data.get("suites", []):
            suite = TestSuite(name=suite_data.get("name", "unknown"))
            
            for test_data in suite_data.get("tests", []):
                test_case = TestCase(
                    name=test_data.get("name", "unknown"),
                    classname=test_data.get("classname", ""),
                    time=test_data.get("time", 0),
                    status=test_data.get("status", "passed"),
                    message=test_data.get("message"),
                    error_type=test_data.get("error_type"),
                    error_message=test_data.get("error_message"),
                    file=test_data.get("file"),
                    line=test_data.get("line"),
                    system_out=test_data.get("system_out"),
                    system_err=test_data.get("system_err")
                )
                suite.tests.append(test_case)
            
            self.test_suites.append(suite)
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary of all test results."""
        total_tests = sum(s.test_count for s in self.test_suites)
        total_passed = sum(
            sum(1 for t in s.tests if t.status == "passed")
            for s in self.test_suites
        )
        total_failed = sum(s.failure_count for s in self.test_suites)
        total_errors = sum(s.error_count for s in self.test_suites)
        total_skipped = sum(s.skipped_count for s in self.test_suites)
        total_time = sum(s.time for s in self.test_suites)
        
        return {
            "total_tests": total_tests,
            "passed": total_passed,
            "failed": total_failed,
            "errors": total_errors,
            "skipped": total_skipped,
            "time": round(total_time, 3),
            "pass_rate": round(total_passed / total_tests * 100, 2) if total_tests > 0 else 0,
            "suites": len(self.test_suites)
        }


def main():
    """Main entry point for JUnit report generation."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate JUnit XML reports for PARWA")
    parser.add_argument("--output", "-o", type=Path, default=Path("test-reports/junit.xml"), help="Output file path")
    parser.add_argument("--input", "-i", type=Path, help="Input JSON file with test results")
    parser.add_argument("--pretty", action="store_true", help="Pretty print XML")
    
    args = parser.parse_args()
    
    generator = JUnitReportGenerator(output_dir=args.output.parent)
    
    if args.input:
        with open(args.input, "r") as f:
            data = json.load(f)
        generator.from_dict(data)
    else:
        # Create sample data for demonstration
        sample_suite = TestSuite(
            name="sample_tests",
            tests=[
                TestCase(
                    name="test_example_pass",
                    classname="test_module.TestClass",
                    time=0.123,
                    status="passed"
                ),
                TestCase(
                    name="test_example_fail",
                    classname="test_module.TestClass",
                    time=0.456,
                    status="failed",
                    message="Assertion failed",
                    error_type="AssertionError",
                    error_message="Expected 1 but got 2"
                )
            ]
        )
        generator.add_suite(sample_suite)
    
    output_path = generator.save_xml(args.output.name)
    summary = generator.get_summary()
    
    print(f"JUnit XML report saved to: {output_path}")
    print(f"Summary: {json.dumps(summary, indent=2)}")


if __name__ == "__main__":
    main()
