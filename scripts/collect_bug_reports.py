#!/usr/bin/env python3
"""Collect Bug Reports from Logs - Week 19 Builder 3"""

import argparse
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional
from collections import defaultdict


def parse_log_line(line: str) -> Optional[Dict[str, Any]]:
    """Parse a single log line for errors"""
    error_patterns = [
        r"ERROR:\s*(?P<message>.+)",
        r"Exception:\s*(?P<message>.+)",
        r"Traceback.*",
        r"Failed to\s*(?P<message>.+)",
        r"(?P<type>\w+Error):\s*(?P<message>.+)",
    ]

    for pattern in error_patterns:
        match = re.search(pattern, line, re.IGNORECASE)
        if match:
            return {
                "raw": line.strip(),
                "message": match.group("message", "").strip() if match else line.strip(),
                "type": match.group("type", "Unknown") if "type" in match.groupdict() else "Unknown",
                "timestamp": datetime.utcnow().isoformat()
            }
    return None


def group_similar_errors(errors: List[Dict]) -> Dict[str, List[Dict]]:
    """Group similar errors together"""
    groups = defaultdict(list)

    for error in errors:
        # Create a key based on error type and first 50 chars of message
        key = f"{error.get('type', 'Unknown')}:{error.get('message', '')[:50]}"
        groups[key].append(error)

    return dict(groups)


def generate_bug_report(errors: List[Dict], output_format: str = "json") -> str:
    """Generate bug report from collected errors"""
    grouped = group_similar_errors(errors)

    report = {
        "generated_at": datetime.utcnow().isoformat(),
        "total_errors": len(errors),
        "unique_errors": len(grouped),
        "groups": []
    }

    for key, group in grouped.items():
        error_type, message_prefix = key.split(":", 1)
        report["groups"].append({
            "type": error_type,
            "message_pattern": message_prefix,
            "count": len(group),
            "first_occurrence": min(e["timestamp"] for e in group),
            "last_occurrence": max(e["timestamp"] for e in group),
            "samples": group[:3]  # Include up to 3 samples
        })

    # Sort by count descending
    report["groups"].sort(key=lambda x: x["count"], reverse=True)

    if output_format == "json":
        return json.dumps(report, indent=2)
    else:
        return format_as_markdown(report)


def format_as_markdown(report: Dict) -> str:
    """Format report as Markdown"""
    lines = [
        "# Bug Report",
        f"\n**Generated:** {report['generated_at']}",
        f"**Total Errors:** {report['total_errors']}",
        f"**Unique Errors:** {report['unique_errors']}\n",
        "## Error Groups\n"
    ]

    for group in report["groups"]:
        lines.append(f"### {group['type']}: {group['message_pattern']}")
        lines.append(f"- **Count:** {group['count']}")
        lines.append(f"- **First:** {group['first_occurrence']}")
        lines.append(f"- **Last:** {group['last_occurrence']}\n")

    return "\n".join(lines)


def export_to_github_issues(report: Dict, output_dir: str) -> List[str]:
    """Export errors as GitHub issue format files"""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    issue_files = []

    for i, group in enumerate(report.get("groups", [])[:10]):  # Top 10
        issue_content = f"""---
title: "[Bug] {group['type']}: {group['message_pattern']}"
labels: ["bug", "auto-generated"]
---

## Description

{group['message_pattern']}

## Frequency

- **Occurrences:** {group['count']}
- **First seen:** {group['first_occurrence']}
- **Last seen:** {group['last_occurrence']}

## Sample Logs

```
{group['samples'][0]['raw'] if group['samples'] else 'N/A'}
```

## Auto-generated

This issue was automatically generated from error logs.
"""
        issue_file = output_path / f"issue_{i+1}_{group['type'].lower()}.md"
        with open(issue_file, 'w') as f:
            f.write(issue_content)
        issue_files.append(str(issue_file))

    return issue_files


def main():
    parser = argparse.ArgumentParser(description="Collect bug reports from logs")
    parser.add_argument("--log-dir", required=True, help="Directory containing log files")
    parser.add_argument("--output", default="bug_report.json", help="Output file")
    parser.add_argument("--format", choices=["json", "markdown"], default="json")
    parser.add_argument("--github-issues", help="Directory to export GitHub issue files")

    args = parser.parse_args()

    log_dir = Path(args.log_dir)
    if not log_dir.exists():
        print(f"Error: Log directory not found: {log_dir}")
        return 1

    # Collect errors from all log files
    errors = []
    for log_file in log_dir.glob("*.log"):
        with open(log_file) as f:
            for line in f:
                parsed = parse_log_line(line)
                if parsed:
                    errors.append(parsed)

    if not errors:
        print("No errors found in logs")
        return 0

    # Generate report
    report_content = generate_bug_report(errors, args.format)

    # Write output
    output_path = Path(args.output)
    with open(output_path, 'w') as f:
        f.write(report_content)

    print(f"Bug report generated: {output_path}")
    print(f"Total errors found: {len(errors)}")

    # Export GitHub issues if requested
    if args.github_issues:
        report = json.loads(report_content) if args.format == "json" else None
        if report:
            issue_files = export_to_github_issues(report, args.github_issues)
            print(f"GitHub issues exported: {len(issue_files)} files")

    return 0


if __name__ == "__main__":
    exit(main())
