#!/usr/bin/env python3
"""
REUSABLE TESTING GAP FINDER
===========================
Use this for ANY day's code to find testing gaps.

Usage:
    python testing_gap_finder.py --day 24
    python testing_gap_finder.py --day 26
    python testing_gap_finder.py --files "app/services/ticket_service.py,app/api/tickets.py"
"""

import os
import sys
import json
import argparse
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

SYSTEM_PROMPT = """You are a senior software testing engineer. Your job is to find loopholes, bugs, and missing test cases in any software project.

You think in 4 layers:
1. UNIT GAPS — individual functions with edge cases
2. INTEGRATION GAPS — two systems talking to each other, what breaks at the seams
3. FLOW GAPS — full user journeys nobody tested end to end
4. BREAK TESTS — adversarial scenarios where users do unexpected things

You know these failure patterns:
- Race conditions (two things at same time)
- Idempotency failures (same request sent twice)
- Tenant isolation leaks (one customer sees another's data)
- Webhook double-fires (payment systems sending same event twice)
- State loss (in-memory data gone on restart)
- Missing rollback (partial success leaving broken state)
- Silent failures (errors swallowed, never surfaced)
- Cascade failures (one system down takes others down)
- Null/None handling failures
- Empty list/string edge cases
- Boundary conditions (0, -1, max int, etc.)
- Concurrent access issues
- Missing validation

RESPOND IN THIS EXACT FORMAT — no deviation:

GAPS FOUND: [number]

GAP 1
Severity: CRITICAL
Title: [short title]
What breaks: [one sentence]
Real scenario: [concrete example with actual data]
AI agent prompt: [exact prompt to paste into coding AI to write this test]

GAP 2
Severity: HIGH
Title: [short title]
What breaks: [one sentence]
Real scenario: [concrete example]
AI agent prompt: [exact prompt]

[continue for all gaps]

Keep it tight and actionable. Every gap needs an AI agent prompt they can copy paste directly."""

# Day-specific file mappings (correct paths)
DAY_FILES = {
    24: {
        "name": "Database Models (Ticket System)",
        "files": [
            "database/models/tickets.py",
        ]
    },
    25: {
        "name": "Schemas + Pydantic Validation",
        "files": [
            "backend/app/schemas/ticket.py",
            "backend/app/schemas/sla.py",
            "backend/app/schemas/assignment.py",
            "backend/app/schemas/ticket_message.py",
            "backend/app/schemas/bulk_action.py",
        ]
    },
    26: {
        "name": "Ticket CRUD Service + API",
        "files": [
            "backend/app/services/ticket_service.py",
            "backend/app/services/tag_service.py",
            "backend/app/services/category_service.py",
            "backend/app/services/priority_service.py",
            "backend/app/services/attachment_service.py",
            "backend/app/services/pii_scan_service.py",
            "backend/app/api/tickets.py",
        ]
    },
    27: {
        "name": "Ticket Views + Templates",
        "files": [
            "backend/app/templates/emails/",
        ]
    },
    28: {
        "name": "Full Ticket Flow Integration",
        "files": [
            "backend/app/services/ticket_service.py",
            "backend/app/api/tickets.py",
            "database/models/tickets.py",
        ]
    }
}

# Day descriptions for context
DAY_DESCRIPTIONS = {
    24: "Day 24: Database models for ticket system - Ticket, TicketComment, TicketAttachment, SLAPolicy, SLATimer, AssignmentRule, AssignmentLog, TicketMention, TicketMerge. Includes relationships, constraints, and model methods.",
    25: "Day 25: Business logic layer - service classes that orchestrate database operations.",
    26: "Day 26: Ticket CRUD Service + REST API - create, read, update, delete tickets with SLA tracking, auto-assignment, mentions parsing, and merge operations.",
    27: "Day 27: Ticket Views + Templates - web UI for ticket management.",
    28: "Day 28: Full ticket flow integration - end-to-end testing."
}


def read_file_content(filepath: str, base_path: str) -> str:
    """Read file content, handling both files and directories."""
    full_path = Path(base_path) / filepath
    
    if not full_path.exists():
        return f"# FILE NOT FOUND: {filepath}"
    
    if full_path.is_dir():
        # Read all Python files in directory
        contents = []
        for py_file in sorted(full_path.glob("*.py")):
            try:
                content = py_file.read_text()
                contents.append(f"\n# === {py_file.name} ===\n{content}")
            except Exception as e:
                contents.append(f"\n# ERROR reading {py_file.name}: {e}")
        return "\n".join(contents)
    else:
        try:
            return full_path.read_text()
        except Exception as e:
            return f"# ERROR reading file: {e}"


def get_code_for_day(day: int) -> dict:
    """Get all code for a specific day."""
    base_path = Path(__file__).parent
    
    if day not in DAY_FILES:
        return {"error": f"Day {day} not configured. Available days: {list(DAY_FILES.keys())}"}
    
    day_config = DAY_FILES[day]
    day_name = day_config["name"]
    files = day_config["files"]
    description = DAY_DESCRIPTIONS.get(day, f"Day {day} code")
    
    # Read all file contents
    code_contents = []
    for filepath in files:
        content = read_file_content(filepath, str(base_path))
        code_contents.append(f"\n# ========== {filepath} ==========\n{content}")
    
    all_code = "\n".join(code_contents)
    
    return {
        "day": day,
        "name": day_name,
        "description": description,
        "files": files,
        "code": all_code,
        "system_prompt": SYSTEM_PROMPT,
        "user_prompt": f"""Analyze this code for testing gaps.

{description}

CODE TO ANALYZE:
{all_code}

Find all UNIT GAPS, INTEGRATION GAPS, FLOW GAPS, and BREAK TESTS that are missing."""
    }


def get_code_for_files(file_list: list) -> dict:
    """Get code for specific files."""
    base_path = Path(__file__).parent
    code_contents = []
    
    for filepath in file_list:
        content = read_file_content(filepath, str(base_path))
        code_contents.append(f"\n# ========== {filepath} ==========\n{content}")
    
    return {
        "files": file_list,
        "code": "\n".join(code_contents),
        "system_prompt": SYSTEM_PROMPT,
        "user_prompt": f"""Analyze this code for testing gaps.

CODE TO ANALYZE:
{''.join(code_contents)}

Find all UNIT GAPS, INTEGRATION GAPS, FLOW GAPS, and BREAK TESTS that are missing."""
    }


def main():
    parser = argparse.ArgumentParser(description="Testing Gap Finder for PARWA Project")
    parser.add_argument("--day", type=int, help="Day number to analyze (24, 25, 26, etc.)")
    parser.add_argument("--files", type=str, help="Comma-separated list of specific files to analyze")
    parser.add_argument("--output", type=str, default="text", choices=["json", "text", "prompt"], help="Output format")
    
    args = parser.parse_args()
    
    if args.day:
        result = get_code_for_day(args.day)
    elif args.files:
        files = [f.strip() for f in args.files.split(",")]
        result = get_code_for_files(files)
    else:
        print("Usage: python testing_gap_finder.py --day 24")
        print("       python testing_gap_finder.py --files 'app/services/ticket_service.py'")
        print(f"\nAvailable days: {list(DAY_FILES.keys())}")
        sys.exit(1)
    
    if args.output == "json":
        print(json.dumps(result, indent=2))
    elif args.output == "prompt":
        # Output just the prompts for LLM
        print("=== SYSTEM PROMPT ===")
        print(result["system_prompt"])
        print("\n=== USER PROMPT ===")
        print(result["user_prompt"])
    else:
        print(f"=== Day {args.day}: {result.get('name', 'Custom Files')} ===\n")
        print("FILES:", result.get("files", []))
        print("\n" + "="*60)
        print("CODE TO ANALYZE:")
        print("="*60)
        print(result.get("code", ""))


if __name__ == "__main__":
    main()
