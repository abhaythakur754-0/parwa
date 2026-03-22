#!/usr/bin/env python3
"""
Client Report Generator for PARWA
Generates PDF/Markdown reports with charts and graphs
"""

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict

# Constants
REPORTS_DIR = Path(__file__).parent.parent / "reports"
TEMPLATE_DIR = Path(__file__).parent.parent / "templates" / "reports"


@dataclass
class ReportConfig:
    """Configuration for report generation"""
    client_id: str
    week_number: int
    output_format: str = "markdown"  # markdown, pdf, html
    include_charts: bool = True
    include_recommendations: bool = True
    email_delivery: bool = False
    email_recipients: List[str] = None


class MetricsAggregator:
    """Aggregates metrics for report generation"""

    def __init__(self, client_id: str):
        self.client_id = client_id
        self.accuracy_data: Dict[str, Any] = {}
        self.performance_data: Dict[str, Any] = {}
        self.trending_data: List[Dict] = []

    def load_baseline_data(self) -> bool:
        """Load baseline accuracy and performance data"""
        accuracy_file = REPORTS_DIR / "baseline_accuracy.json"
        performance_file = REPORTS_DIR / "baseline_performance.json"

        if accuracy_file.exists():
            with open(accuracy_file, 'r') as f:
                self.accuracy_data = json.load(f)

        if performance_file.exists():
            with open(performance_file, 'r') as f:
                self.performance_data = json.load(f)

        return bool(self.accuracy_data or self.performance_data)

    def aggregate_metrics(self) -> Dict[str, Any]:
        """Aggregate all metrics into report format"""
        return {
            "client_id": self.client_id,
            "accuracy": self.accuracy_data.get("overall_accuracy", 0),
            "accuracy_by_category": self.accuracy_data.get("accuracy_by_category", {}),
            "p50_latency": self.performance_data.get("p50_latency_ms", 0),
            "p95_latency": self.performance_data.get("p95_latency_ms", 0),
            "p99_latency": self.performance_data.get("p99_latency_ms", 0),
            "throughput": self.performance_data.get("throughput_per_hour", 0),
            "error_rate": self.performance_data.get("error_rate", 0),
        }


class ReportGenerator:
    """Generates client reports in various formats"""

    def __init__(self, config: ReportConfig):
        self.config = config
        self.aggregator = MetricsAggregator(config.client_id)

    def generate(self) -> Path:
        """Generate the report and return path to output file"""
        self.aggregator.load_baseline_data()
        metrics = self.aggregator.aggregate_metrics()

        if self.config.output_format == "markdown":
            return self._generate_markdown(metrics)
        elif self.config.output_format == "html":
            return self._generate_html(metrics)
        elif self.config.output_format == "pdf":
            return self._generate_pdf(metrics)
        else:
            raise ValueError(f"Unknown format: {self.config.output_format}")

    def _generate_markdown(self, metrics: Dict) -> Path:
        """Generate Markdown report"""
        report_path = REPORTS_DIR / f"{self.config.client_id}_week{self.config.week_number}.md"

        content = self._build_markdown_content(metrics)

        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        with open(report_path, 'w') as f:
            f.write(content)

        return report_path

    def _build_markdown_content(self, metrics: Dict) -> str:
        """Build Markdown content from metrics"""
        now = datetime.utcnow().strftime("%Y-%m-%d")

        content = f"""# {self.config.client_id.upper()} - Week {self.config.week_number} Report

**Generated:** {now}
**Report Period:** Week {self.config.week_number}

---

## Executive Summary

| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| Accuracy | {metrics['accuracy']:.1%} | >72% | {'✅ PASS' if metrics['accuracy'] >= 0.72 else '❌ FAIL'} |
| P95 Latency | {metrics['p95_latency']:.0f}ms | <500ms | {'✅ PASS' if metrics['p95_latency'] < 500 else '❌ FAIL'} |
| Error Rate | {metrics['error_rate']:.1%} | <1% | {'✅ PASS' if metrics['error_rate'] < 0.01 else '❌ FAIL'} |
| Throughput | {metrics['throughput']:.0f}/hr | >30/hr | {'✅ PASS' if metrics['throughput'] >= 30 else '❌ FAIL'} |

---

## Performance Metrics

### Latency Percentiles

| Metric | Value |
|--------|-------|
| P50 (Median) | {metrics['p50_latency']:.0f}ms |
| P95 | {metrics['p95_latency']:.0f}ms |
| P99 | {metrics['p99_latency']:.0f}ms |

### Accuracy by Category

"""
        for category, acc in metrics['accuracy_by_category'].items():
            content += f"- **{category}**: {acc:.1%}\n"

        if self.config.include_recommendations:
            content += "\n---\n\n## Recommendations\n\n"
            content += self._generate_recommendations(metrics)

        content += f"\n---\n\n*Generated by PARWA Reporting System v1.0.0*\n"
        return content

    def _generate_recommendations(self, metrics: Dict) -> str:
        """Generate recommendations based on metrics"""
        recs = []

        if metrics['accuracy'] < 0.80:
            recs.append("1. **Improve Accuracy**: Consider adding more FAQ entries for low-accuracy categories")

        if metrics['p95_latency'] > 300:
            recs.append("2. **Optimize Performance**: Review slow queries and add caching")

        if metrics['error_rate'] > 0.005:
            recs.append("3. **Reduce Errors**: Investigate error patterns and add error handling")

        return "\n".join(recs) if recs else "All metrics within target. No immediate actions required."

    def _generate_html(self, metrics: Dict) -> Path:
        """Generate HTML report"""
        report_path = REPORTS_DIR / f"{self.config.client_id}_week{self.config.week_number}.html"

        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>{self.config.client_id} - Week {self.config.week_number} Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        table {{ border-collapse: collapse; width: 100%; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #4CAF50; color: white; }}
        .pass {{ color: green; }}
        .fail {{ color: red; }}
    </style>
</head>
<body>
    <h1>{self.config.client_id.upper()} - Week {self.config.week_number} Report</h1>
    <p>Generated: {datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")}</p>

    <h2>Executive Summary</h2>
    <table>
        <tr><th>Metric</th><th>Value</th><th>Target</th><th>Status</th></tr>
        <tr><td>Accuracy</td><td>{metrics['accuracy']:.1%}</td><td>>72%</td>
            <td class="{'pass' if metrics['accuracy'] >= 0.72 else 'fail'}">
            {'PASS' if metrics['accuracy'] >= 0.72 else 'FAIL'}</td></tr>
        <tr><td>P95 Latency</td><td>{metrics['p95_latency']:.0f}ms</td><td><500ms</td>
            <td class="{'pass' if metrics['p95_latency'] < 500 else 'fail'}">
            {'PASS' if metrics['p95_latency'] < 500 else 'FAIL'}</td></tr>
        <tr><td>Error Rate</td><td>{metrics['error_rate']:.1%}</td><td><1%</td>
            <td class="{'pass' if metrics['error_rate'] < 0.01 else 'fail'}">
            {'PASS' if metrics['error_rate'] < 0.01 else 'FAIL'}</td></tr>
    </table>

    <p><em>Generated by PARWA Reporting System v1.0.0</em></p>
</body>
</html>"""

        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        with open(report_path, 'w') as f:
            f.write(html_content)

        return report_path

    def _generate_pdf(self, metrics: Dict) -> Path:
        """Generate PDF report (requires weasyprint or similar)"""
        # First generate HTML, then convert to PDF
        html_path = self._generate_html(metrics)
        pdf_path = REPORTS_DIR / f"{self.config.client_id}_week{self.config.week_number}.pdf"

        try:
            from weasyprint import HTML
            HTML(str(html_path)).write_pdf(str(pdf_path))
            return pdf_path
        except ImportError:
            # Fallback: return HTML if PDF generation not available
            print("Warning: weasyprint not available, returning HTML instead")
            return html_path

    def deliver_report(self, report_path: Path) -> bool:
        """Deliver report via configured channels"""
        if self.config.email_delivery and self.config.email_recipients:
            return self._send_email(report_path)
        return True

    def _send_email(self, report_path: Path) -> bool:
        """Send report via email"""
        # Placeholder for email implementation
        print(f"Would send report to: {', '.join(self.config.email_recipients)}")
        print(f"Attachment: {report_path}")
        return True


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Generate client reports for PARWA")
    parser.add_argument("--client", required=True, help="Client ID (e.g., client_001)")
    parser.add_argument("--week", type=int, required=True, help="Week number")
    parser.add_argument("--format", choices=["markdown", "html", "pdf"],
                        default="markdown", help="Output format")
    parser.add_argument("--email", action="store_true", help="Send via email")
    parser.add_argument("--recipients", nargs="+", help="Email recipients")

    args = parser.parse_args()

    config = ReportConfig(
        client_id=args.client,
        week_number=args.week,
        output_format=args.format,
        email_delivery=args.email,
        email_recipients=args.recipients or []
    )

    generator = ReportGenerator(config)
    report_path = generator.generate()

    print(f"Report generated: {report_path}")

    if args.email:
        generator.deliver_report(report_path)

    return 0


if __name__ == "__main__":
    sys.exit(main())
