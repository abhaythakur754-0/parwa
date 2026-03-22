#!/usr/bin/env python3
"""
Coverage Report Generator for PARWA

Generates comprehensive coverage reports with:
- pytest-cov integration
- HTML report generation
- XML report for CI
- Minimum coverage threshold (80%)
- Per-module coverage breakdown
- Coverage trend tracking
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
import html


@dataclass
class CoverageStats:
    """Coverage statistics for a module or file."""
    name: str
    covered: int
    total: int
    percent: float
    branches_covered: int = 0
    branches_total: int = 0
    missing_lines: List[int] = field(default_factory=list)


@dataclass
class CoverageReport:
    """Complete coverage report."""
    generated_at: str
    total_lines: int
    covered_lines: int
    line_percent: float
    total_branches: int
    covered_branches: int
    branch_percent: float
    modules: List[CoverageStats] = field(default_factory=list)
    threshold_met: bool = True
    threshold_percent: float = 80.0


class CoverageReportGenerator:
    """
    Generates and manages test coverage reports.
    
    Features:
    - Integration with pytest-cov
    - HTML report generation
    - XML report for CI/CD
    - Minimum coverage threshold enforcement
    - Per-module breakdown
    - Trend tracking
    """
    
    DEFAULT_THRESHOLD = 80.0
    COVERAGE_FILE = ".coverage"
    XML_REPORT = "coverage.xml"
    HTML_DIR = "htmlcov"
    TREND_FILE = "coverage_trend.json"
    
    def __init__(
        self,
        project_root: Optional[Path] = None,
        threshold: float = DEFAULT_THRESHOLD,
        output_dir: Optional[Path] = None
    ):
        """Initialize coverage report generator."""
        self.project_root = project_root or Path.cwd()
        self.threshold = threshold
        self.output_dir = output_dir or self.project_root / "test-reports"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
    def run_coverage(
        self,
        test_paths: List[str] = None,
        extra_args: List[str] = None
    ) -> int:
        """
        Run pytest with coverage collection.
        
        Args:
            test_paths: Paths to test directories
            extra_args: Additional pytest arguments
            
        Returns:
            pytest exit code
        """
        if test_paths is None:
            test_paths = ["tests/"]
            
        cmd = [
            sys.executable, "-m", "pytest",
            *test_paths,
            f"--cov=backend",
            f"--cov-report=xml:{self.output_dir / self.XML_REPORT}",
            f"--cov-report=html:{self.output_dir / self.HTML_DIR}",
            "--cov-report=term-missing",
            "-v",
        ]
        
        if extra_args:
            cmd.extend(extra_args)
            
        print(f"Running coverage: {' '.join(cmd)}")
        result = subprocess.run(cmd, cwd=self.project_root)
        return result.returncode
    
    def parse_xml_report(self, xml_path: Optional[Path] = None) -> CoverageReport:
        """
        Parse coverage XML report.
        
        Args:
            xml_path: Path to coverage XML file
            
        Returns:
            CoverageReport object
        """
        xml_path = xml_path or self.output_dir / self.XML_REPORT
        
        if not xml_path.exists():
            raise FileNotFoundError(f"Coverage XML report not found: {xml_path}")
            
        tree = ET.parse(xml_path)
        root = tree.getroot()
        
        # Extract overall stats
        total_lines = int(root.attrib.get("lines-valid", 0))
        covered_lines = int(root.attrib.get("lines-covered", 0))
        total_branches = int(root.attrib.get("branches-valid", 0))
        covered_branches = int(root.attrib.get("branches-covered", 0))
        
        line_percent = (covered_lines / total_lines * 100) if total_lines > 0 else 0
        branch_percent = (covered_branches / total_branches * 100) if total_branches > 0 else 0
        
        # Extract per-module stats
        modules = []
        for package in root.findall(".//package"):
            name = package.attrib.get("name", "unknown")
            
            pkg_lines_valid = int(package.attrib.get("lines-valid", 0))
            pkg_lines_covered = int(package.attrib.get("lines-covered", 0))
            pkg_branches_valid = int(package.attrib.get("branches-valid", 0))
            pkg_branches_covered = int(package.attrib.get("branches-covered", 0))
            
            pkg_percent = (pkg_lines_covered / pkg_lines_valid * 100) if pkg_lines_valid > 0 else 0
            
            # Get missing lines
            missing_lines = []
            for line in package.findall(".//line[@hits='0']"):
                missing_lines.append(int(line.attrib.get("number", 0)))
            
            modules.append(CoverageStats(
                name=name,
                covered=pkg_lines_covered,
                total=pkg_lines_valid,
                percent=round(pkg_percent, 2),
                branches_covered=pkg_branches_covered,
                branches_total=pkg_branches_valid,
                missing_lines=missing_lines[:20]  # Limit to first 20 for readability
            ))
        
        # Sort modules by coverage (lowest first)
        modules.sort(key=lambda m: m.percent)
        
        threshold_met = line_percent >= self.threshold
        
        return CoverageReport(
            generated_at=datetime.now().isoformat(),
            total_lines=total_lines,
            covered_lines=covered_lines,
            line_percent=round(line_percent, 2),
            total_branches=total_branches,
            covered_branches=covered_branches,
            branch_percent=round(branch_percent, 2),
            modules=modules,
            threshold_met=threshold_met,
            threshold_percent=self.threshold
        )
    
    def generate_summary_html(self, report: CoverageReport) -> str:
        """
        Generate a summary HTML report.
        
        Args:
            report: CoverageReport object
            
        Returns:
            HTML string
        """
        status_color = "green" if report.threshold_met else "red"
        status_text = "PASS" if report.threshold_met else "FAIL"
        
        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>Coverage Report - PARWA</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 40px; }}
        .header {{ background: #f8f9fa; padding: 20px; border-radius: 8px; margin-bottom: 20px; }}
        .status {{ display: inline-block; padding: 5px 15px; border-radius: 4px; font-weight: bold; }}
        .status.pass {{ background: #d4edda; color: #155724; }}
        .status.fail {{ background: #f8d7da; color: #721c24; }}
        .stats {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; margin: 20px 0; }}
        .stat-card {{ background: #fff; border: 1px solid #dee2e6; border-radius: 8px; padding: 20px; text-align: center; }}
        .stat-value {{ font-size: 2em; font-weight: bold; color: #333; }}
        .stat-label {{ color: #666; font-size: 0.9em; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #dee2e6; }}
        th {{ background: #f8f9fa; }}
        .low {{ color: #dc3545; }}
        .medium {{ color: #ffc107; }}
        .high {{ color: #28a745; }}
        .progress {{ background: #e9ecef; border-radius: 4px; height: 20px; }}
        .progress-bar {{ height: 100%; border-radius: 4px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Coverage Report</h1>
        <p>Generated: {report.generated_at}</p>
        <p>Threshold: {report.threshold_percent}%</p>
        <span class="status {status_color}">{status_text}</span>
    </div>
    
    <div class="stats">
        <div class="stat-card">
            <div class="stat-value">{report.line_percent:.1f}%</div>
            <div class="stat-label">Line Coverage</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{report.branch_percent:.1f}%</div>
            <div class="stat-label">Branch Coverage</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{report.covered_lines:,}</div>
            <div class="stat-label">Lines Covered</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{report.total_lines:,}</div>
            <div class="stat-label">Total Lines</div>
        </div>
    </div>
    
    <h2>Module Coverage</h2>
    <table>
        <thead>
            <tr>
                <th>Module</th>
                <th>Coverage</th>
                <th>Lines</th>
                <th>Branches</th>
                <th>Progress</th>
            </tr>
        </thead>
        <tbody>
"""
        
        for module in report.modules:
            coverage_class = "low" if module.percent < 50 else ("medium" if module.percent < 80 else "high")
            color = "#dc3545" if module.percent < 50 else ("#ffc107" if module.percent < 80 else "#28a745")
            
            html_content += f"""
            <tr>
                <td>{html.escape(module.name)}</td>
                <td class="{coverage_class}">{module.percent:.1f}%</td>
                <td>{module.covered}/{module.total}</td>
                <td>{module.branches_covered}/{module.branches_total}</td>
                <td>
                    <div class="progress">
                        <div class="progress-bar" style="width: {module.percent}%; background: {color};"></div>
                    </div>
                </td>
            </tr>
"""
        
        html_content += """
        </tbody>
    </table>
    
    <p><a href="htmlcov/index.html">View detailed HTML report</a></p>
</body>
</html>
"""
        return html_content
    
    def save_trend(self, report: CoverageReport) -> None:
        """
        Save coverage trend data.
        
        Args:
            report: CoverageReport object
        """
        trend_file = self.output_dir / self.TREND_FILE
        
        # Load existing trend data
        trend_data = []
        if trend_file.exists():
            with open(trend_file, "r") as f:
                trend_data = json.load(f)
        
        # Add new entry
        trend_data.append({
            "timestamp": report.generated_at,
            "line_percent": report.line_percent,
            "branch_percent": report.branch_percent,
            "total_lines": report.total_lines,
            "covered_lines": report.covered_lines,
        })
        
        # Keep only last 30 entries
        trend_data = trend_data[-30:]
        
        with open(trend_file, "w") as f:
            json.dump(trend_data, f, indent=2)
    
    def generate_badge(self, report: CoverageReport) -> str:
        """
        Generate a coverage badge SVG.
        
        Args:
            report: CoverageReport object
            
        Returns:
            SVG string
        """
        color = "#97CA00" if report.threshold_met else "#e05d44"
        
        return f"""<svg xmlns="http://www.w3.org/2000/svg" width="104" height="20">
  <linearGradient id="a" x2="0" y2="100%">
    <stop offset="0" stop-color="#bbb" stop-opacity=".1"/>
    <stop offset="1" stop-opacity=".1"/>
  </linearGradient>
  <rect rx="3" width="104" height="20" fill="#555"/>
  <rect rx="3" x="62" width="42" height="20" fill="{color}"/>
  <path fill="url(#a)" d="M0 0h104v20H0z"/>
  <g fill="#fff" text-anchor="middle" font-family="DejaVu Sans,Verdana,Geneva,sans-serif" font-size="11">
    <text x="32" y="15">coverage</text>
    <text x="82" y="15">{report.line_percent}%</text>
  </g>
</svg>"""
    
    def generate_report(self, run_tests: bool = True) -> CoverageReport:
        """
        Generate complete coverage report.
        
        Args:
            run_tests: Whether to run tests first
            
        Returns:
            CoverageReport object
        """
        if run_tests:
            exit_code = self.run_coverage()
            if exit_code != 0:
                print(f"Warning: Tests exited with code {exit_code}")
        
        # Parse XML report
        report = self.parse_xml_report()
        
        # Generate summary HTML
        summary_html = self.generate_summary_html(report)
        with open(self.output_dir / "coverage_summary.html", "w") as f:
            f.write(summary_html)
        
        # Generate badge
        badge_svg = self.generate_badge(report)
        with open(self.output_dir / "coverage.svg", "w") as f:
            f.write(badge_svg)
        
        # Save trend
        self.save_trend(report)
        
        # Save JSON report
        report_dict = {
            "generated_at": report.generated_at,
            "total_lines": report.total_lines,
            "covered_lines": report.covered_lines,
            "line_percent": report.line_percent,
            "total_branches": report.total_branches,
            "covered_branches": report.covered_branches,
            "branch_percent": report.branch_percent,
            "threshold_met": report.threshold_met,
            "threshold_percent": report.threshold_percent,
            "modules": [asdict(m) for m in report.modules]
        }
        
        with open(self.output_dir / "coverage_report.json", "w") as f:
            json.dump(report_dict, f, indent=2)
        
        return report


def main():
    """Main entry point for coverage report generation."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate coverage reports for PARWA")
    parser.add_argument("--threshold", type=float, default=80.0, help="Minimum coverage threshold")
    parser.add_argument("--output-dir", type=Path, default=Path("test-reports"), help="Output directory")
    parser.add_argument("--skip-tests", action="store_true", help="Skip running tests")
    parser.add_argument("--project-root", type=Path, default=None, help="Project root directory")
    
    args = parser.parse_args()
    
    generator = CoverageReportGenerator(
        project_root=args.project_root,
        threshold=args.threshold,
        output_dir=args.output_dir
    )
    
    report = generator.generate_report(run_tests=not args.skip_tests)
    
    print("\n" + "=" * 60)
    print("COVERAGE REPORT SUMMARY")
    print("=" * 60)
    print(f"Line Coverage: {report.line_percent:.2f}%")
    print(f"Branch Coverage: {report.branch_percent:.2f}%")
    print(f"Lines: {report.covered_lines}/{report.total_lines}")
    print(f"Branches: {report.covered_branches}/{report.total_branches}")
    print(f"Threshold ({args.threshold}%): {'MET ✓' if report.threshold_met else 'NOT MET ✗'}")
    print("=" * 60)
    
    if not report.threshold_met:
        sys.exit(1)


if __name__ == "__main__":
    main()
