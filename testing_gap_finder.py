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
        "name": "Ticket Conversation + Internal Notes",
        "files": [
            "backend/app/services/message_service.py",
            "backend/app/services/activity_log_service.py",
            "backend/app/services/internal_note_service.py",
            "backend/app/api/ticket_messages.py",
            "backend/app/api/ticket_notes.py",
            "backend/app/api/ticket_timeline.py",
        ]
    },
    28: {
        "name": "Search + Classification + Assignment",
        "files": [
            "backend/app/services/ticket_search_service.py",
            "backend/app/services/classification_service.py",
            "backend/app/services/assignment_service.py",
            "backend/app/api/ticket_search.py",
            "backend/app/api/ticket_classification.py",
            "backend/app/api/ticket_assignment.py",
            "backend/app/tasks/ticket_tasks.py",
        ]
    },
    29: {
        "name": "Bulk Actions + Merge/Split + SLA System",
        "files": [
            "backend/app/services/bulk_action_service.py",
            "backend/app/services/ticket_merge_service.py",
            "backend/app/services/sla_service.py",
            "backend/app/api/ticket_bulk.py",
            "backend/app/api/ticket_merge.py",
            "backend/app/api/sla.py",
            "backend/app/tasks/sla_tasks.py",
        ]
    },
    30: {
        "name": "Omnichannel + Customer Identity Resolution",
        "files": [
            "backend/app/services/channel_service.py",
            "backend/app/services/customer_service.py",
            "backend/app/services/identity_resolution_service.py",
            "backend/app/api/channels.py",
            "backend/app/api/customers.py",
        ]
    },
    31: {
        "name": "Notification System + Email Templates",
        "files": [
            "backend/app/services/notification_service.py",
            "backend/app/services/notification_template_service.py",
            "backend/app/services/notification_preference_service.py",
            "backend/app/api/notifications.py",
            "backend/app/tasks/notification_tasks.py",
        ]
    },
    32: {
        "name": "Production Situation Handlers + Ticket State Machine",
        "files": [
            "backend/app/services/ticket_state_machine.py",
            "backend/app/services/ticket_lifecycle_service.py",
            "backend/app/api/ticket_lifecycle.py",
            "backend/app/tasks/ticket_lifecycle_tasks.py",
        ]
    },
    33: {
        "name": "SHOULD-HAVE Features: Templates, Triggers, Custom Fields, Collision Detection",
        "files": [
            "backend/app/services/template_service.py",
            "backend/app/services/trigger_service.py",
            "backend/app/services/custom_field_service.py",
            "backend/app/services/collision_service.py",
            "backend/app/api/ticket_templates.py",
            "backend/app/api/triggers.py",
            "backend/app/api/custom_fields.py",
            "backend/app/api/collisions.py",
        ]
    },
    34: {
        "name": "Socket.io Events + Celery Tasks + Analytics (MF10)",
        "files": [
            "backend/app/core/ticket_events.py",
            "backend/app/tasks/ticket_tasks.py",
            "backend/app/services/ticket_analytics_service.py",
            "backend/app/api/ticket_analytics.py",
        ]
    }
}

# Day descriptions for context
DAY_DESCRIPTIONS = {
    24: "Day 24: Database models for ticket system - Ticket, TicketComment, TicketAttachment, SLAPolicy, SLATimer, AssignmentRule, AssignmentLog, TicketMention, TicketMerge. Includes relationships, constraints, and model methods.",
    25: "Day 25: Business logic layer - service classes that orchestrate database operations.",
    26: "Day 26: Ticket CRUD Service + REST API - create, read, update, delete tickets with SLA tracking, auto-assignment, mentions parsing, and merge operations.",
    27: "Day 27: Ticket Conversation + Internal Notes - message CRUD with edit window, thread management, internal notes with pinning, activity timeline tracking for all ticket changes.",
    28: "Day 28: Ticket Search + Classification + Assignment - Full-text search with fuzzy matching and suggestions, rule-based intent/urgency classification with human correction workflow, score-based auto-assignment with rules engine.",
    29: "Day 29: Bulk Actions + Merge/Split + SLA System - Bulk operations on tickets with undo capability, ticket merging with message transfer and unmerge support, SLA policy management with timer tracking and breach detection.",
    30: "Day 30: Omnichannel + Customer Identity Resolution (F-052, F-070) - Channel configuration with PS13 variant down handling, customer CRUD with channel linking, identity resolution with confidence scoring and PS14 grandfathered tickets.",
    31: "Day 31: Notification System + Email Templates (MF05) - Notification dispatch with PS03/PS10 handlers, template CRUD with variable validation, user preferences with priority thresholds and digest settings.",
    32: "Day 32: Production Situation Handlers + Ticket State Machine (PS01-PS15) - State transitions with validation, lifecycle automation, human fallback routing, incident subscriber notifications.",
    33: "Day 33: SHOULD-HAVE Features (MF07-12, PS12, PS16) - Response templates with variables, automated trigger rules engine, custom ticket fields per category, collision detection for concurrent editing, soft delete/redaction, bad feedback auto-review.",
    34: "Day 34: Socket.io Events + Celery Tasks + Analytics (MF10) - Real-time ticket event emission via Socket.io, complete Celery task suite for SLA/stale/spam/bulk operations, ticket analytics dashboard with summary/trends/category/SLA/agent metrics."
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
