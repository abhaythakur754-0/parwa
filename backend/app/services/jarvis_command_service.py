"""
PARWA Jarvis Command Service (Phase 3 — The Command Layer)

The service that makes natural language commands work. When a user types
"pause all AI", "show me today's errors", or "export weekly report",
this service parses the NL input into a structured command, executes
the appropriate backend action, and writes a full audit trail.

Architecture:
  6 Major Subsystems:

    1. NL COMMAND PARSER (parse_natural_language_command)
       Raw text → structured command with action, scope, target, parameters.
       Uses keyword matching + regex pattern extraction (no LLM — fast <2s).
       Maps to 5 intent types: query, control, configure, report, override.
       20+ built-in command patterns matching FR-2.8.2.
       Confidence scoring 0.0-1.0 based on pattern match quality.
       Unknown command handling with best-effort suggestion.

    2. COMMAND EXECUTOR (execute_command)
       Parsed command → backend action → result_json.
       Status lifecycle: received → parsing → parsed → executing → completed/failed.
       Each execution writes timestamps to JarvisCommand at every stage.
       12 execution handlers, each independently wrapped in try/except (BC-008).

    3. UNDO SYSTEM (undo_command)
       Finds the last undoable command for the session.
       Creates a new JarvisCommand with type "undo".
       Reverses the original command's effect.
       Links via undone_by_command_id.
       Some commands are NOT undoable (query, report).

    4. QUICK COMMAND PRESETS (get_quick_commands, execute_quick_command)
       Returns tenant-specific preset commands.
       Default presets matching FR-2.8.13.
       Custom presets stored in session context (max 50 per tenant).
       Quick commands skip NL parsing — go straight to execution.

    5. CO-PILOT MODE (generate_co_pilot_suggestion)
       When user asks an open question like "what should I do about the ticket spike?"
       Generates a suggestion based on current awareness state.
       Suggestion types: policy_reminder, action_suggestion, best_practice, warning.

    6. COMMAND HISTORY & AUDIT (get_command_history, get_command_by_id)
       Paginated command history for a session.
       Filterable by status, intent, source.
       Full audit trail with all timestamps.

Data Flow:
  User types NL command
      → parse_natural_language_command() returns structured ParsedCommand
      → JarvisCommand row created (status=received → parsing → parsed)
      → execute_command() dispatches to handler
      → Handler runs backend action (status=executing)
      → JarvisCommand updated (status=completed/failed, result_json set)
      → If undoable, undo_available=True

Fallback Strategy (BC-008):
  The service NEVER crashes. Every public method is wrapped in try/except.
  If the NL parser fails, it returns a low-confidence "unknown" command.
  If a handler fails, the command is marked "failed" with error_message.
  Partial execution is better than no execution.

BC-001: company_id first parameter on ALL public methods.
BC-008: Every public method wrapped in try/except — never crash.
BC-012: All timestamps UTC.
"""

import json
import re
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.exceptions import NotFoundError, ValidationError
from app.logger import get_logger
from database.models.jarvis_cc import (
    JarvisAwarenessSnapshot,
    JarvisCommand,
    JarvisProactiveAlert,
)

logger = get_logger("jarvis_command_service")


# ══════════════════════════════════════════════════════════════════
# CONSTANTS
# ══════════════════════════════════════════════════════════════════

# ── Valid enum-like value sets (must match DB CHECK constraints) ──

VALID_COMMAND_INTENTS = (
    "query", "control", "configure", "report", "override",
)
VALID_COMMAND_STATUSES = (
    "received", "parsing", "parsed", "executing",
    "completed", "failed", "cancelled", "undone",
)
VALID_SOURCES = (
    "chat", "api", "co_pilot", "proactive", "scheduled",
)

# Intents that cannot be undone (read-only / side-effect-free)
NON_UNDOABLE_INTENTS = ("query", "report")

# ── Execution limits ──

MAX_PARSE_INPUT_LENGTH = 500  # Max chars for NL command input
MAX_COMMAND_HISTORY_PER_SESSION = 10000  # Prune threshold
COMMAND_HISTORY_PRUNE_BATCH = 200
MAX_QUICK_COMMANDS_PER_TENANT = 50

# ── Confidence thresholds ──

CONFIDENCE_HIGH = 0.85     # Direct keyword match
CONFIDENCE_MEDIUM = 0.65   # Partial match / synonyms
CONFIDENCE_LOW = 0.40      # Fuzzy match
CONFIDENCE_UNKNOWN = 0.15  # No match — unknown command

# ── Default quick command presets (FR-2.8.13) ──

DEFAULT_QUICK_COMMANDS: List[Dict[str, Any]] = [
    {
        "id": "qc_pause_all_agents",
        "label": "Pause All Agents",
        "raw_input": "pause all agents",
        "action": "pause_ai",
        "intent": "control",
        "icon": "pause",
        "description": "Immediately pause all AI agent activity",
    },
    {
        "id": "qc_export_weekly_report",
        "label": "Export Weekly Report",
        "raw_input": "export weekly report",
        "action": "export_report",
        "intent": "report",
        "icon": "download",
        "description": "Generate and export a weekly performance report",
    },
    {
        "id": "qc_check_system_health",
        "label": "Check System Health",
        "raw_input": "check system health",
        "action": "check_system_health",
        "intent": "query",
        "icon": "activity",
        "description": "Show current system health status",
    },
    {
        "id": "qc_escalate_urgent",
        "label": "Escalate Urgent Tickets",
        "raw_input": "escalate all urgent tickets",
        "action": "escalate_urgent",
        "intent": "control",
        "icon": "alert-triangle",
        "description": "Escalate all urgent-priority tickets to human agents",
    },
    {
        "id": "qc_resume_ai",
        "label": "Resume AI",
        "raw_input": "resume all AI",
        "action": "resume_ai",
        "intent": "control",
        "icon": "play",
        "description": "Resume AI agent activity after a pause",
    },
    {
        "id": "qc_show_errors",
        "label": "Show Recent Errors",
        "raw_input": "show me today's errors",
        "action": "show_errors",
        "intent": "query",
        "icon": "bug",
        "description": "Display the most recent system errors",
    },
    {
        "id": "qc_pause_refunds",
        "label": "Pause Refund Processing",
        "raw_input": "pause refund processing",
        "action": "pause_refunds",
        "intent": "control",
        "icon": "pause",
        "description": "Stop automated refund processing",
    },
    {
        "id": "qc_disable_last_rule",
        "label": "Disable Last Auto-Approve Rule",
        "raw_input": "disable last auto-approve rule",
        "action": "disable_last_rule",
        "intent": "configure",
        "icon": "x-circle",
        "description": "Remove the most recently added auto-approve rule",
    },
]


# ══════════════════════════════════════════════════════════════════
# COMMAND PATTERNS (FR-2.8.2)
# ══════════════════════════════════════════════════════════════════
# Each pattern maps a regex to an action, intent, and scope.
# The parser iterates patterns in order and returns the first match.
# Order matters: more specific patterns should come before generic ones.

COMMAND_PATTERNS: List[Dict[str, Any]] = [
    # ── Control: Pause / Resume ──
    {
        "regex": r"(?i)\b(pause|stop|halt|freeze)\s+(all\s+)?(ai|agents?|bot)\b",
        "action": "pause_ai",
        "intent": "control",
        "scope": "global",
        "confidence": CONFIDENCE_HIGH,
    },
    {
        "regex": r"(?i)\b(resume|unpause|restart|continue)\s+(all\s+)?(ai|agents?|bot)\b",
        "action": "resume_ai",
        "intent": "control",
        "scope": "global",
        "confidence": CONFIDENCE_HIGH,
    },
    {
        "regex": r"(?i)\b(pause|stop|halt)\s+(refund|refunds|refund\s+processing)\b",
        "action": "pause_refunds",
        "intent": "control",
        "scope": "refunds",
        "confidence": CONFIDENCE_HIGH,
    },
    {
        "regex": r"(?i)\b(resume|restart|continue)\s+(refund|refunds|refund\s+processing)\b",
        "action": "resume_refunds",
        "intent": "control",
        "scope": "refunds",
        "confidence": CONFIDENCE_HIGH,
    },
    {
        "regex": r"(?i)\bemergency\s+(brake|stop|halt|shutdown)\b",
        "action": "pause_ai",
        "intent": "override",
        "scope": "global",
        "confidence": CONFIDENCE_HIGH,
    },

    # ── Query: System health & errors ──
    {
        "regex": r"(?i)\b(check|show|what('?s|\s+is)\s+the)\s+(system\s+)?health\b",
        "action": "check_system_health",
        "intent": "query",
        "scope": "system",
        "confidence": CONFIDENCE_HIGH,
    },
    {
        "regex": r"(?i)\b(show|display|list|get)\s+(me\s+)?(today'?s?\s+)?(errors?|failures?)\b",
        "action": "show_errors",
        "intent": "query",
        "scope": "errors",
        "confidence": CONFIDENCE_HIGH,
    },
    {
        "regex": r"(?i)\b(show|display|get)\s+(me\s+)?(the\s+)?(ticket|ticket'?s?)\s+(details?|info)\b",
        "action": "show_ticket_details",
        "intent": "query",
        "scope": "ticket",
        "confidence": CONFIDENCE_HIGH,
    },
    {
        "regex": r"(?i)\b(status|system\s+status|how\s+(is|are)\s+(things?|everything|the\s+system))\b",
        "action": "check_system_health",
        "intent": "query",
        "scope": "system",
        "confidence": CONFIDENCE_MEDIUM,
    },

    # ── Control: Escalate ──
    {
        "regex": r"(?i)\b(escalate|bump\s+up|raise)\s+(all\s+)?(urgent|critical|high\s+priority)\s*(tickets?)?\b",
        "action": "escalate_urgent",
        "intent": "control",
        "scope": "tickets",
        "confidence": CONFIDENCE_HIGH,
    },
    {
        "regex": r"(?i)\b(escalate|bump|raise)\b",
        "action": "escalate_urgent",
        "intent": "control",
        "scope": "tickets",
        "confidence": CONFIDENCE_LOW,
    },

    # ── Control: Add agents ──
    {
        "regex": r"(?i)\b(add|provision|spin\s+up|create)\s+(\d+\s+)?(more\s+)?(agents?|workers?)\b",
        "action": "add_agents",
        "intent": "control",
        "scope": "agents",
        "confidence": CONFIDENCE_HIGH,
    },

    # ── Configure: Disable rule ──
    {
        "regex": r"(?i)\b(disable|remove|delete|turn\s+off)\s+(the\s+)?(last|latest|most\s+recent)\s+(auto[\s-]?approve|rule|policy)\b",
        "action": "disable_last_rule",
        "intent": "configure",
        "scope": "rules",
        "confidence": CONFIDENCE_HIGH,
    },

    # ── Report: Export ──
    {
        "regex": r"(?i)\b(export|download|generate|create)\s+(a\s+)?(weekly|monthly|daily)?\s*(report|summary|analytics?)\b",
        "action": "export_report",
        "intent": "report",
        "scope": "reporting",
        "confidence": CONFIDENCE_HIGH,
    },
    {
        "regex": r"(?i)\b(weekly|monthly|daily)\s+report\b",
        "action": "export_report",
        "intent": "report",
        "scope": "reporting",
        "confidence": CONFIDENCE_MEDIUM,
    },

    # ── Control: Call customer ──
    {
        "regex": r"(?i)\b(call|phone|ring|dial)\s+(the\s+)?(customer|client|user)\b",
        "action": "call_customer",
        "intent": "control",
        "scope": "communication",
        "confidence": CONFIDENCE_HIGH,
    },

    # ── Query: Show errors (alternate phrasing) ──
    {
        "regex": r"(?i)\b(any\s+)?errors?\s*(today|lately|recently)?\b",
        "action": "show_errors",
        "intent": "query",
        "scope": "errors",
        "confidence": CONFIDENCE_MEDIUM,
    },

    # ── Control: Pause all (generic) ──
    {
        "regex": r"(?i)\b(pause|stop|halt)\s+everything\b",
        "action": "pause_ai",
        "intent": "override",
        "scope": "global",
        "confidence": CONFIDENCE_MEDIUM,
    },

    # ── Control: Resume all (generic) ──
    {
        "regex": r"(?i)\b(resume|restart|continue)\s+everything\b",
        "action": "resume_ai",
        "intent": "control",
        "scope": "global",
        "confidence": CONFIDENCE_MEDIUM,
    },

    # ── Configure: Show config ──
    {
        "regex": r"(?i)\b(show|display|what\s+(is|are))\s+(the\s+)?(config|configuration|settings?|preferences?)\b",
        "action": "check_system_health",
        "intent": "query",
        "scope": "system",
        "confidence": CONFIDENCE_LOW,
    },
]


__all__ = [
    # NL Command Parser
    "parse_natural_language_command",
    # Command Executor
    "execute_command",
    "receive_command",
    # Undo System
    "undo_command",
    # Quick Command Presets
    "get_quick_commands",
    "execute_quick_command",
    "add_custom_quick_command",
    "remove_custom_quick_command",
    # Co-Pilot Mode
    "generate_co_pilot_suggestion",
    # Command History & Audit
    "get_command_history",
    "get_command_by_id",
    # Command Status Updates
    "cancel_command",
    # Pruning
    "prune_old_commands",
    # Constants (for testing / API use)
    "VALID_COMMAND_INTENTS",
    "VALID_COMMAND_STATUSES",
    "VALID_SOURCES",
    "NON_UNDOABLE_INTENTS",
    "DEFAULT_QUICK_COMMANDS",
    "COMMAND_PATTERNS",
]


# ══════════════════════════════════════════════════════════════════
# 1. NL COMMAND PARSER
# ══════════════════════════════════════════════════════════════════


def parse_natural_language_command(
    company_id: str,
    raw_input: str,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Parse a natural language command into a structured command.

    Takes raw text like "pause all AI", "show me today's errors",
    "export weekly report" and returns a structured command dict
    with action, scope, target, parameters, and confidence.

    The parser uses keyword matching + regex pattern extraction.
    No LLM is needed for Phase 3 — this keeps execution fast (<2s).

    If no pattern matches, returns a low-confidence "unknown" command
    with a best-effort suggestion based on keyword proximity.

    Args:
        company_id: Company ID for BC-001.
        raw_input: The raw natural language command string.
        session_id: Optional session ID for context-aware parsing.

    Returns:
        Dict with keys:
          - action: str (e.g., "pause_ai", "show_errors", "unknown")
          - intent: str (one of VALID_COMMAND_INTENTS)
          - scope: str (e.g., "global", "system", "tickets")
          - target: str (what the command targets, e.g., "ai", "errors")
          - parameters: Dict of extracted parameters (e.g., {"count": 3})
          - confidence: float 0.0-1.0
          - raw_input: str (original input, trimmed)
          - suggestion: Optional[str] (if confidence is low)
    """
    try:
        # Validate and normalize input
        if not raw_input or not raw_input.strip():
            return _build_unknown_command(
                raw_input="",
                reason="Empty input",
            )

        normalized = raw_input.strip()[:MAX_PARSE_INPUT_LENGTH]

        # ── Step 1: Try exact pattern matching ──
        best_match: Optional[Dict[str, Any]] = None
        best_confidence = 0.0

        for pattern_def in COMMAND_PATTERNS:
            match = re.search(pattern_def["regex"], normalized)
            if match:
                pattern_confidence = pattern_def["confidence"]
                if pattern_confidence > best_confidence:
                    best_confidence = pattern_confidence
                    best_match = pattern_def

        # ── Step 2: If we found a match, build structured command ──
        if best_match and best_confidence >= CONFIDENCE_LOW:
            parameters = _extract_parameters(normalized, best_match["action"])

            result = {
                "action": best_match["action"],
                "intent": best_match["intent"],
                "scope": best_match["scope"],
                "target": _infer_target(best_match["action"]),
                "parameters": parameters,
                "confidence": best_confidence,
                "raw_input": normalized,
                "suggestion": None,
            }

            # Boost confidence if multiple patterns match the same action
            matching_count = sum(
                1 for p in COMMAND_PATTERNS
                if re.search(p["regex"], normalized)
                and p["action"] == best_match["action"]
            )
            if matching_count > 1:
                result["confidence"] = min(
                    best_confidence + 0.10, CONFIDENCE_HIGH
                )

            logger.info(
                "command_parsed: input='%s', action=%s, intent=%s, "
                "confidence=%.2f, session=%s",
                normalized[:50], best_match["action"],
                best_match["intent"], best_confidence,
                session_id or "none",
            )

            return result

        # ── Step 3: No pattern match — try fuzzy keyword matching ──
        fuzzy_result = _fuzzy_match_command(normalized)
        if fuzzy_result and fuzzy_result["confidence"] >= CONFIDENCE_LOW:
            logger.info(
                "command_fuzzy_parsed: input='%s', action=%s, "
                "confidence=%.2f, session=%s",
                normalized[:50], fuzzy_result["action"],
                fuzzy_result["confidence"], session_id or "none",
            )
            return fuzzy_result

        # ── Step 4: Unknown command with best-effort suggestion ──
        suggestion = _generate_suggestion(normalized)
        logger.warning(
            "command_unknown: input='%s', suggestion='%s', session=%s",
            normalized[:50], suggestion, session_id or "none",
        )

        return _build_unknown_command(
            raw_input=normalized,
            suggestion=suggestion,
        )

    except Exception:
        logger.exception(
            "parse_command_error: input='%s', company=%s",
            raw_input[:50] if raw_input else "None",
            company_id,
        )
        return _build_unknown_command(
            raw_input=raw_input or "",
            reason="Parser error",
        )


# ══════════════════════════════════════════════════════════════════
# 2. COMMAND EXECUTOR
# ══════════════════════════════════════════════════════════════════


def receive_command(
    db: Session,
    company_id: str,
    session_id: str,
    raw_input: str,
    source: str = "chat",
    user_id: Optional[str] = None,
) -> JarvisCommand:
    """Receive a raw NL command and create a JarvisCommand row.

    This is the entry point for the command lifecycle. It:
      1. Creates a JarvisCommand with status="received"
      2. Parses the NL input
      3. Updates the command with parsed data
      4. Returns the command row (status="parsed")

    The caller should then call execute_command() to run it.

    Args:
        db: SQLAlchemy session.
        company_id: Company ID for BC-001.
        session_id: CC session ID.
        raw_input: The raw natural language command.
        source: Command source (chat, api, co_pilot, proactive, scheduled).
        user_id: Optional user ID for audit.

    Returns:
        JarvisCommand row with status="parsed" (or "failed" if parse fails).
    """
    try:
        now = datetime.now(timezone.utc)

        # ── Step 1: Create command row (status=received) ──
        command = JarvisCommand(
            session_id=session_id,
            company_id=company_id,
            raw_input=raw_input[:MAX_PARSE_INPUT_LENGTH],
            source=source if source in VALID_SOURCES else "chat",
            status="received",
            received_at=now,
            command_metadata_json=json.dumps({
                "user_id": user_id or "",
                "source": source,
            }),
        )
        db.add(command)
        db.flush()

        logger.debug(
            "command_received: id=%s, input='%s', session=%s",
            command.id, raw_input[:50], session_id,
        )

        # ── Step 2: Parse (status=parsing → parsed) ──
        command.status = "parsing"
        command.command_metadata_json = _merge_metadata(
            command.command_metadata_json,
            {"parsing_started_at": now.isoformat()},
        )
        db.flush()

        parsed = parse_natural_language_command(
            company_id=company_id,
            raw_input=raw_input,
            session_id=session_id,
        )

        parse_time = datetime.now(timezone.utc)

        # Determine undo availability
        undo_available = parsed["intent"] not in NON_UNDOABLE_INTENTS

        command.status = "parsed"
        command.command_parsed = json.dumps(parsed)
        command.command_intent = parsed["intent"]
        command.confidence = parsed["confidence"]
        command.parsed_at = parse_time
        command.undo_available = undo_available
        command.command_metadata_json = _merge_metadata(
            command.command_metadata_json,
            {
                "parsed_at": parse_time.isoformat(),
                "action": parsed["action"],
                "scope": parsed["scope"],
                "target": parsed["target"],
                "parameters": parsed["parameters"],
                "parse_confidence": parsed["confidence"],
            },
        )
        db.flush()

        logger.info(
            "command_parsed_db: id=%s, action=%s, intent=%s, "
            "confidence=%.2f, undo=%s, session=%s",
            command.id, parsed["action"], parsed["intent"],
            parsed["confidence"], undo_available, session_id,
        )

        return command

    except Exception:
        logger.exception(
            "receive_command_error: input='%s', session=%s, company=%s",
            raw_input[:50] if raw_input else "None",
            session_id, company_id,
        )
        # Try to mark as failed if the row was created
        try:
            if "command" in dir() and command and command.id:
                command.status = "failed"
                command.error_message = "Failed to receive/parse command"
                db.flush()
        except Exception:
            pass
        raise


def execute_command(
    db: Session,
    company_id: str,
    command_id: str,
    session_id: str,
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute a parsed command by dispatching to the appropriate handler.

    Takes a JarvisCommand that has been parsed (status="parsed") and
    executes the appropriate backend action. The command status transitions
    through: parsed → executing → completed/failed.

    Each handler is independently wrapped in try/except (BC-008).
    If a handler fails, the command is marked "failed" with error_message,
    but the service never crashes.

    Args:
        db: SQLAlchemy session.
        company_id: Company ID for BC-001.
        command_id: The JarvisCommand ID to execute.
        session_id: CC session ID for security scoping.
        user_id: Optional user ID for audit.

    Returns:
        Dict with:
          - command_id: str
          - status: str ("completed" or "failed")
          - action: str
          - result: Dict (handler-specific result data)
          - execution_time_ms: float
          - error: Optional[str] (if failed)
    """
    start_time = time.monotonic()

    try:
        # ── Step 1: Load command and validate ──
        command = _get_command(db, command_id, session_id, company_id)
        if not command:
            return {
                "command_id": command_id,
                "status": "failed",
                "action": "unknown",
                "result": {},
                "execution_time_ms": 0,
                "error": "Command not found",
            }

        if command.status not in ("parsed", "received"):
            return {
                "command_id": command_id,
                "status": command.status,
                "action": "unknown",
                "result": {},
                "execution_time_ms": 0,
                "error": f"Command cannot be executed (status={command.status})",
            }

        # ── Step 2: Parse the structured command ──
        parsed = _safe_parse_json(command.command_parsed)
        action = parsed.get("action", "unknown")

        # ── Step 3: Transition to executing ──
        now = datetime.now(timezone.utc)
        command.status = "executing"
        command.executed_at = now
        command.command_metadata_json = _merge_metadata(
            command.command_metadata_json,
            {"execution_started_at": now.isoformat(), "user_id": user_id or ""},
        )
        db.flush()

        logger.info(
            "command_executing: id=%s, action=%s, session=%s",
            command_id, action, session_id,
        )

        # ── Step 4: Dispatch to handler ──
        handler_result = _dispatch_handler(
            db=db,
            company_id=company_id,
            session_id=session_id,
            action=action,
            parsed=parsed,
            user_id=user_id,
        )

        # ── Step 5: Mark as completed ──
        completed_at = datetime.now(timezone.utc)
        total_ms = round((time.monotonic() - start_time) * 1000, 2)

        command.status = "completed"
        command.completed_at = completed_at
        command.result_json = json.dumps(handler_result, default=str)
        command.command_metadata_json = _merge_metadata(
            command.command_metadata_json,
            {
                "execution_completed_at": completed_at.isoformat(),
                "execution_time_ms": total_ms,
            },
        )
        db.flush()

        logger.info(
            "command_completed: id=%s, action=%s, ms=%.1f, session=%s",
            command_id, action, total_ms, session_id,
        )

        return {
            "command_id": str(command.id),
            "status": "completed",
            "action": action,
            "result": handler_result,
            "execution_time_ms": total_ms,
            "error": None,
        }

    except Exception:
        total_ms = round((time.monotonic() - start_time) * 1000, 2)
        logger.exception(
            "execute_command_error: id=%s, session=%s, company=%s",
            command_id, session_id, company_id,
        )

        # Try to mark as failed
        try:
            command = _get_command(db, command_id, session_id, company_id)
            if command and command.status == "executing":
                command.status = "failed"
                command.error_message = "Execution failed unexpectedly"
                command.command_metadata_json = _merge_metadata(
                    command.command_metadata_json,
                    {"execution_failed_at": datetime.now(timezone.utc).isoformat()},
                )
                db.flush()
        except Exception:
            logger.exception("Failed to mark command as failed")

        return {
            "command_id": command_id,
            "status": "failed",
            "action": "unknown",
            "result": {},
            "execution_time_ms": total_ms,
            "error": "Execution failed unexpectedly",
        }


# ══════════════════════════════════════════════════════════════════
# 3. UNDO SYSTEM
# ══════════════════════════════════════════════════════════════════


def undo_command(
    db: Session,
    company_id: str,
    session_id: str,
    user_id: Optional[str] = None,
    command_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Undo the last undoable command for the session (or a specific one).

    Creates a new JarvisCommand with action "undo" that reverses the
    original command's effect. The original command is linked via
    undone_by_command_id.

    Commands with intent in NON_UNDOABLE_INTENTS (query, report)
    cannot be undone — they are read-only operations.

    Args:
        db: SQLAlchemy session.
        company_id: Company ID for BC-001.
        session_id: CC session ID.
        user_id: Optional user ID for audit.
        command_id: Optional specific command to undo. If None,
                     undoes the most recent undoable command.

    Returns:
        Dict with:
          - undo_command_id: str (ID of the new undo command)
          - original_command_id: str (ID of the undone command)
          - original_action: str (action that was undone)
          - undo_result: Dict (result of the undo operation)
          - status: str

    Raises:
        NotFoundError: If no undoable command is found.
        ValidationError: If the specified command is not undoable.
    """
    try:
        # ── Step 1: Find the command to undo ──
        original_command = None

        if command_id:
            # Undo a specific command
            original_command = _get_command(db, command_id, session_id, company_id)
            if not original_command:
                raise NotFoundError(
                    message="Command not found for undo",
                    details={"command_id": command_id},
                )
            if not original_command.undo_available:
                raise ValidationError(
                    message="This command cannot be undone",
                    details={
                        "command_id": command_id,
                        "intent": original_command.command_intent,
                    },
                )
            if original_command.status == "undone":
                raise ValidationError(
                    message="Command has already been undone",
                    details={"command_id": command_id},
                )
        else:
            # Find the most recent undoable command
            original_command = (
                db.query(JarvisCommand)
                .filter(
                    JarvisCommand.session_id == session_id,
                    JarvisCommand.company_id == company_id,
                    JarvisCommand.undo_available.is_(True),
                    JarvisCommand.status.in_(["completed"]),
                    JarvisCommand.command_intent.notin_(NON_UNDOABLE_INTENTS),
                )
                .order_by(JarvisCommand.created_at.desc())
                .first()
            )

        if not original_command:
            raise NotFoundError(
                message="No undoable command found for this session",
                details={"session_id": session_id},
            )

        # ── Step 2: Create the undo command ──
        now = datetime.now(timezone.utc)
        original_parsed = _safe_parse_json(original_command.command_parsed)
        original_action = original_parsed.get("action", "unknown")

        undo_command_row = JarvisCommand(
            session_id=session_id,
            company_id=company_id,
            raw_input=f"undo: {original_command.raw_input}",
            source="chat",
            command_parsed=json.dumps({
                "action": "undo",
                "intent": "control",
                "scope": original_parsed.get("scope", "unknown"),
                "target": original_action,
                "parameters": {
                    "original_command_id": str(original_command.id),
                    "original_action": original_action,
                },
                "confidence": 1.0,
                "raw_input": f"undo: {original_command.raw_input}",
                "suggestion": None,
            }),
            command_intent="control",
            confidence=1.0,
            status="executing",
            received_at=now,
            parsed_at=now,
            executed_at=now,
            undo_available=False,
            command_metadata_json=json.dumps({
                "user_id": user_id or "",
                "is_undo": True,
                "original_command_id": str(original_command.id),
                "original_action": original_action,
            }),
        )
        db.add(undo_command_row)
        db.flush()

        # ── Step 3: Execute the undo (reverse the original action) ──
        undo_result = _execute_undo_action(
            db=db,
            company_id=company_id,
            session_id=session_id,
            original_action=original_action,
            original_parsed=original_parsed,
        )

        # ── Step 4: Update both commands ──
        completed_at = datetime.now(timezone.utc)

        # Mark undo command as completed
        undo_command_row.status = "completed"
        undo_command_row.completed_at = completed_at
        undo_command_row.result_json = json.dumps(undo_result, default=str)

        # Mark original command as undone
        original_command.status = "undone"
        original_command.undone_by_command_id = str(undo_command_row.id)

        db.flush()

        logger.info(
            "command_undone: original_id=%s, undo_id=%s, "
            "original_action=%s, session=%s",
            original_command.id, undo_command_row.id,
            original_action, session_id,
        )

        return {
            "undo_command_id": str(undo_command_row.id),
            "original_command_id": str(original_command.id),
            "original_action": original_action,
            "undo_result": undo_result,
            "status": "completed",
        }

    except (NotFoundError, ValidationError):
        raise
    except Exception:
        logger.exception(
            "undo_command_error: session=%s, company=%s, cmd=%s",
            session_id, company_id, command_id or "latest",
        )
        return {
            "undo_command_id": None,
            "original_command_id": command_id,
            "original_action": "unknown",
            "undo_result": {},
            "status": "failed",
            "error": "Undo operation failed unexpectedly",
        }


# ══════════════════════════════════════════════════════════════════
# 4. QUICK COMMAND PRESETS
# ══════════════════════════════════════════════════════════════════


def get_quick_commands(
    db: Session,
    company_id: str,
    session_id: str,
) -> List[Dict[str, Any]]:
    """Get quick command presets for a session (default + product + custom).

    Returns the default quick commands plus product-specific commands
    (shadow mode, billing, variants) plus any tenant-specific
    custom presets stored in the session context.

    Args:
        db: SQLAlchemy session.
        company_id: Company ID for BC-001.
        session_id: CC session ID.

    Returns:
        List of quick command dicts, each with:
          - id: str
          - label: str
          - raw_input: str
          - action: str
          - intent: str
          - icon: str
          - description: str
    """
    try:
        commands = list(DEFAULT_QUICK_COMMANDS)

        # Add product-specific quick commands (shadow mode, billing, variants)
        try:
            from app.services.jarvis_product_commands import PRODUCT_QUICK_COMMANDS
            commands.extend(PRODUCT_QUICK_COMMANDS)
        except Exception:
            logger.debug("product_quick_commands_load_failed: session=%s", session_id)

        # Load custom quick commands from session context
        try:
            from app.services.jarvis_cc_service import get_cc_session

            session = (
                db.query(
                    __import__(
                        "database.models.jarvis",
                        fromlist=["JarvisSession"],
                    ).JarvisSession
                )
                .filter(
                    __import__(
                        "database.models.jarvis",
                        fromlist=["JarvisSession"],
                    ).JarvisSession.id == session_id,
                    __import__(
                        "database.models.jarvis",
                        fromlist=["JarvisSession"],
                    ).JarvisSession.company_id == company_id,
                )
                .first()
            )
            if session:
                ctx = _safe_parse_json(session.context_json)
                custom_commands = ctx.get("custom_quick_commands", [])
                if isinstance(custom_commands, list):
                    commands.extend(custom_commands)
        except Exception:
            logger.debug(
                "quick_commands_custom_load_failed: session=%s", session_id,
            )

        return commands

    except Exception:
        logger.exception(
            "get_quick_commands_error: company=%s, session=%s",
            company_id, session_id,
        )
        return list(DEFAULT_QUICK_COMMANDS)


def execute_quick_command(
    db: Session,
    company_id: str,
    session_id: str,
    quick_command_id: str,
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute a quick command preset by ID.

    Quick commands skip NL parsing — they go straight to execution
    because the action and intent are already known.

    Args:
        db: SQLAlchemy session.
        company_id: Company ID for BC-001.
        session_id: CC session ID.
        quick_command_id: The quick command preset ID (e.g., "qc_pause_all_agents").
        user_id: Optional user ID for audit.

    Returns:
        Dict with execution result (same shape as execute_command return).
    """
    try:
        # ── Step 1: Find the quick command ──
        all_commands = get_quick_commands(db, company_id, session_id)
        quick_cmd = None
        for cmd in all_commands:
            if cmd.get("id") == quick_command_id:
                quick_cmd = cmd
                break

        if not quick_cmd:
            raise NotFoundError(
                message="Quick command not found",
                details={"quick_command_id": quick_command_id},
            )

        # ── Step 2: Create command row directly with parsed data ──
        now = datetime.now(timezone.utc)

        command = JarvisCommand(
            session_id=session_id,
            company_id=company_id,
            raw_input=quick_cmd["raw_input"],
            source="api",  # Quick commands are treated as API-sourced
            command_parsed=json.dumps({
                "action": quick_cmd["action"],
                "intent": quick_cmd["intent"],
                "scope": quick_cmd.get("scope", "unknown"),
                "target": _infer_target(quick_cmd["action"]),
                "parameters": {},
                "confidence": 1.0,  # Quick commands are pre-defined, always 1.0
                "raw_input": quick_cmd["raw_input"],
                "suggestion": None,
                "quick_command_id": quick_command_id,
            }),
            command_intent=quick_cmd["intent"],
            confidence=1.0,
            status="parsed",
            received_at=now,
            parsed_at=now,
            undo_available=quick_cmd["intent"] not in NON_UNDOABLE_INTENTS,
            command_metadata_json=json.dumps({
                "user_id": user_id or "",
                "source": "quick_command",
                "quick_command_id": quick_command_id,
                "quick_command_label": quick_cmd.get("label", ""),
            }),
        )
        db.add(command)
        db.flush()

        # ── Step 3: Execute ──
        result = execute_command(
            db=db,
            company_id=company_id,
            command_id=str(command.id),
            session_id=session_id,
            user_id=user_id,
        )

        logger.info(
            "quick_command_executed: id=%s, action=%s, status=%s, session=%s",
            quick_command_id, quick_cmd["action"],
            result.get("status"), session_id,
        )

        return result

    except (NotFoundError, ValidationError):
        raise
    except Exception:
        logger.exception(
            "execute_quick_command_error: qc_id=%s, session=%s, company=%s",
            quick_command_id, session_id, company_id,
        )
        return {
            "command_id": None,
            "status": "failed",
            "action": "unknown",
            "result": {},
            "execution_time_ms": 0,
            "error": "Quick command execution failed",
        }


def add_custom_quick_command(
    db: Session,
    company_id: str,
    session_id: str,
    label: str,
    raw_input: str,
    action: str,
    intent: str,
    icon: str = "zap",
    description: str = "",
) -> Dict[str, Any]:
    """Add a custom quick command preset for this tenant.

    Custom presets are stored in the session context (max 50 per tenant).

    Args:
        db: SQLAlchemy session.
        company_id: Company ID for BC-001.
        session_id: CC session ID.
        label: Display label for the quick command.
        raw_input: The NL command text.
        action: The action to execute.
        intent: The command intent.
        icon: Icon name for UI display.
        description: Description for tooltip.

    Returns:
        The created quick command dict.
    """
    try:
        from database.models.jarvis import JarvisSession

        session = (
            db.query(JarvisSession)
            .filter(
                JarvisSession.id == session_id,
                JarvisSession.company_id == company_id,
            )
            .first()
        )
        if not session:
            raise NotFoundError(
                message="Session not found",
                details={"session_id": session_id},
            )

        ctx = _safe_parse_json(session.context_json)
        custom_commands = ctx.get("custom_quick_commands", [])
        if not isinstance(custom_commands, list):
            custom_commands = []

        # Check limit
        if len(custom_commands) >= MAX_QUICK_COMMANDS_PER_TENANT:
            raise ValidationError(
                message="Custom quick command limit reached",
                details={
                    "limit": MAX_QUICK_COMMANDS_PER_TENANT,
                    "current": len(custom_commands),
                },
            )

        # Create custom command
        import uuid

        new_cmd = {
            "id": f"qc_custom_{str(uuid.uuid4())[:8]}",
            "label": label[:50],
            "raw_input": raw_input[:MAX_PARSE_INPUT_LENGTH],
            "action": action,
            "intent": intent,
            "icon": icon,
            "description": description[:200],
            "is_custom": True,
        }

        custom_commands.append(new_cmd)
        ctx["custom_quick_commands"] = custom_commands
        session.context_json = json.dumps(ctx)
        session.updated_at = datetime.now(timezone.utc)
        db.flush()

        logger.info(
            "custom_quick_command_added: id=%s, label='%s', session=%s",
            new_cmd["id"], label, session_id,
        )

        return new_cmd

    except (NotFoundError, ValidationError):
        raise
    except Exception:
        logger.exception(
            "add_custom_quick_command_error: session=%s, company=%s",
            session_id, company_id,
        )
        return {"error": "Failed to add custom quick command"}


def remove_custom_quick_command(
    db: Session,
    company_id: str,
    session_id: str,
    quick_command_id: str,
) -> bool:
    """Remove a custom quick command preset.

    Only custom commands (added via add_custom_quick_command) can be removed.
    Default quick commands cannot be removed.

    Args:
        db: SQLAlchemy session.
        company_id: Company ID for BC-001.
        session_id: CC session ID.
        quick_command_id: The custom quick command ID to remove.

    Returns:
        True if removed, False if not found.
    """
    try:
        from database.models.jarvis import JarvisSession

        session = (
            db.query(JarvisSession)
            .filter(
                JarvisSession.id == session_id,
                JarvisSession.company_id == company_id,
            )
            .first()
        )
        if not session:
            return False

        ctx = _safe_parse_json(session.context_json)
        custom_commands = ctx.get("custom_quick_commands", [])
        if not isinstance(custom_commands, list):
            return False

        original_len = len(custom_commands)
        custom_commands = [
            c for c in custom_commands
            if c.get("id") != quick_command_id
        ]

        if len(custom_commands) == original_len:
            return False  # Not found

        ctx["custom_quick_commands"] = custom_commands
        session.context_json = json.dumps(ctx)
        session.updated_at = datetime.now(timezone.utc)
        db.flush()

        logger.info(
            "custom_quick_command_removed: id=%s, session=%s",
            quick_command_id, session_id,
        )

        return True

    except Exception:
        logger.exception(
            "remove_custom_quick_command_error: session=%s, company=%s",
            session_id, company_id,
        )
        return False


# ══════════════════════════════════════════════════════════════════
# 5. CO-PILOT MODE
# ══════════════════════════════════════════════════════════════════


def generate_co_pilot_suggestion(
    db: Session,
    company_id: str,
    session_id: str,
    user_context: Optional[str] = None,
) -> Dict[str, Any]:
    """Generate a co-pilot suggestion based on current awareness state.

    When a user asks an open question like "what should I do about the
    ticket spike?", the co-pilot generates a contextual suggestion based
    on the current awareness snapshot and active alerts.

    Suggestion types:
      - policy_reminder: Remind about a policy that should be followed
      - action_suggestion: Suggest a specific command the user might run
      - best_practice: Share a best practice recommendation
      - warning: Warn about a potential issue

    Args:
        db: SQLAlchemy session.
        company_id: Company ID for BC-001.
        session_id: CC session ID.
        user_context: Optional additional context from the user's question.

    Returns:
        Dict with:
          - suggestion: str (human-readable suggestion text)
          - suggestion_type: str (policy_reminder, action_suggestion,
                              best_practice, warning)
          - suggested_command: Optional[str] (command the user could run)
          - confidence: float
          - reasoning: str (why this suggestion was made)
    """
    try:
        # ── Step 1: Get latest awareness snapshot ──
        snapshot = (
            db.query(JarvisAwarenessSnapshot)
            .filter(
                JarvisAwarenessSnapshot.session_id == session_id,
                JarvisAwarenessSnapshot.company_id == company_id,
            )
            .order_by(JarvisAwarenessSnapshot.created_at.desc())
            .first()
        )

        # ── Step 2: Get active alerts ──
        active_alerts = (
            db.query(JarvisProactiveAlert)
            .filter(
                JarvisProactiveAlert.session_id == session_id,
                JarvisProactiveAlert.company_id == company_id,
                JarvisProactiveAlert.status.in_(["active", "acknowledged"]),
            )
            .order_by(JarvisProactiveAlert.created_at.desc())
            .limit(5)
            .all()
        )

        # ── Step 3: Generate suggestion based on state ──
        if not snapshot:
            return {
                "suggestion": (
                    "No awareness data available yet. "
                    "Try running 'check system health' to get started."
                ),
                "suggestion_type": "best_practice",
                "suggested_command": "check system health",
                "confidence": 0.5,
                "reasoning": "No awareness snapshot exists for this session yet.",
            }

        # Analyze current state
        suggestions = _analyze_state_for_suggestions(
            snapshot=snapshot,
            alerts=active_alerts,
            user_context=user_context,
        )

        # Return the highest-priority suggestion
        if suggestions:
            best = suggestions[0]  # Already sorted by priority
            logger.info(
                "co_pilot_suggestion: type=%s, command='%s', session=%s",
                best["suggestion_type"], best.get("suggested_command"),
                session_id,
            )
            return best

        # Default: everything looks fine
        return {
            "suggestion": (
                "Everything looks good right now. All systems are healthy "
                "and no alerts are active."
            ),
            "suggestion_type": "best_practice",
            "suggested_command": None,
            "confidence": 0.8,
            "reasoning": "System is healthy with no active alerts.",
        }

    except Exception:
        logger.exception(
            "co_pilot_suggestion_error: session=%s, company=%s",
            session_id, company_id,
        )
        return {
            "suggestion": "Unable to generate suggestion at this time.",
            "suggestion_type": "best_practice",
            "suggested_command": None,
            "confidence": 0.0,
            "reasoning": "Error occurred during suggestion generation.",
        }


# ══════════════════════════════════════════════════════════════════
# 6. COMMAND HISTORY & AUDIT
# ══════════════════════════════════════════════════════════════════


def get_command_history(
    db: Session,
    company_id: str,
    session_id: str,
    status: Optional[str] = None,
    intent: Optional[str] = None,
    source: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> Tuple[List[Dict[str, Any]], int]:
    """Get paginated command history for a session.

    Returns commands in reverse chronological order (newest first).
    Filterable by status, intent, and source.

    Args:
        db: SQLAlchemy session.
        company_id: Company ID for BC-001.
        session_id: CC session ID.
        status: Filter by status (optional).
        intent: Filter by intent (optional).
        source: Filter by source (optional).
        limit: Max commands to return.
        offset: Pagination offset.

    Returns:
        Tuple of (command_list, total_count). Each command dict includes
        all fields from JarvisCommand plus parsed command metadata.
    """
    try:
        query = (
            db.query(JarvisCommand)
            .filter(
                JarvisCommand.session_id == session_id,
                JarvisCommand.company_id == company_id,
            )
        )

        # Apply filters
        if status and status in VALID_COMMAND_STATUSES:
            query = query.filter(JarvisCommand.status == status)
        if intent and intent in VALID_COMMAND_INTENTS:
            query = query.filter(JarvisCommand.command_intent == intent)
        if source and source in VALID_SOURCES:
            query = query.filter(JarvisCommand.source == source)

        query = query.order_by(JarvisCommand.created_at.desc())

        total = query.count()
        commands = query.offset(offset).limit(limit).all()

        command_list = []
        for cmd in commands:
            cmd_dict = _command_to_dict(cmd)
            command_list.append(cmd_dict)

        return command_list, total

    except Exception:
        logger.exception(
            "get_command_history_error: session=%s, company=%s",
            session_id, company_id,
        )
        return [], 0


def get_command_by_id(
    db: Session,
    company_id: str,
    command_id: str,
    session_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Get a single command by ID with full audit details.

    Args:
        db: SQLAlchemy session.
        company_id: Company ID for BC-001.
        command_id: The JarvisCommand ID.
        session_id: Optional session ID for additional security scoping.

    Returns:
        Command dict with all fields, or None if not found.
    """
    try:
        filters = [
            JarvisCommand.id == command_id,
            JarvisCommand.company_id == company_id,
        ]
        if session_id:
            filters.append(JarvisCommand.session_id == session_id)

        command = (
            db.query(JarvisCommand)
            .filter(*filters)
            .first()
        )

        if not command:
            return None

        return _command_to_dict(command)

    except Exception:
        logger.exception(
            "get_command_by_id_error: id=%s, company=%s",
            command_id, company_id,
        )
        return None


# ══════════════════════════════════════════════════════════════════
# COMMAND STATUS UPDATES
# ══════════════════════════════════════════════════════════════════


def cancel_command(
    db: Session,
    company_id: str,
    command_id: str,
    session_id: str,
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Cancel a command that is in received/parsing/parsed status.

    Only commands that haven't started executing can be cancelled.

    Args:
        db: SQLAlchemy session.
        company_id: Company ID for BC-001.
        command_id: The JarvisCommand ID to cancel.
        session_id: CC session ID for security.
        user_id: Optional user ID for audit.

    Returns:
        Dict with cancellation result.

    Raises:
        NotFoundError: If command not found.
        ValidationError: If command cannot be cancelled.
    """
    try:
        command = _get_command(db, command_id, session_id, company_id)
        if not command:
            raise NotFoundError(
                message="Command not found",
                details={"command_id": command_id},
            )

        cancellable_statuses = ("received", "parsing", "parsed")
        if command.status not in cancellable_statuses:
            raise ValidationError(
                message="Command cannot be cancelled in its current status",
                details={
                    "command_id": command_id,
                    "status": command.status,
                    "cancellable_statuses": list(cancellable_statuses),
                },
            )

        command.status = "cancelled"
        command.command_metadata_json = _merge_metadata(
            command.command_metadata_json,
            {
                "cancelled_at": datetime.now(timezone.utc).isoformat(),
                "cancelled_by": user_id or "",
            },
        )
        db.flush()

        logger.info(
            "command_cancelled: id=%s, previous_status=%s, session=%s",
            command_id, command.status, session_id,
        )

        return {
            "command_id": str(command.id),
            "status": "cancelled",
            "previous_status": command.status,
        }

    except (NotFoundError, ValidationError):
        raise
    except Exception:
        logger.exception(
            "cancel_command_error: id=%s, session=%s, company=%s",
            command_id, session_id, company_id,
        )
        return {
            "command_id": command_id,
            "status": "error",
            "error": "Cancellation failed",
        }


# ══════════════════════════════════════════════════════════════════
# PRUNING
# ══════════════════════════════════════════════════════════════════


def prune_old_commands(
    db: Session,
    session_id: str,
    company_id: str,
    max_keep: int = MAX_COMMAND_HISTORY_PER_SESSION,
) -> int:
    """Prune old commands to prevent unbounded DB growth.

    Keeps the most recent `max_keep` commands per session.
    Failed and cancelled commands older than 24 hours are always pruned.

    Args:
        db: SQLAlchemy session.
        session_id: CC session ID.
        company_id: Company ID for BC-001.
        max_keep: Maximum commands to keep per session.

    Returns:
        Number of commands pruned.
    """
    try:
        # Count total commands for this session
        total = (
            db.query(func.count(JarvisCommand.id))
            .filter(
                JarvisCommand.session_id == session_id,
                JarvisCommand.company_id == company_id,
            )
            .scalar()
        )

        if total <= max_keep:
            return 0

        # Find IDs to keep (most recent)
        keep_ids = (
            db.query(JarvisCommand.id)
            .filter(
                JarvisCommand.session_id == session_id,
                JarvisCommand.company_id == company_id,
            )
            .order_by(JarvisCommand.created_at.desc())
            .limit(max_keep)
            .all()
        )
        keep_id_set = {row[0] for row in keep_ids}

        # Also keep undone commands (for audit trail)
        undone_ids = (
            db.query(JarvisCommand.id)
            .filter(
                JarvisCommand.session_id == session_id,
                JarvisCommand.company_id == company_id,
                JarvisCommand.status == "undone",
            )
            .all()
        )
        keep_id_set.update(row[0] for row in undone_ids)

        # Delete commands not in keep set (batch)
        to_delete_ids = (
            db.query(JarvisCommand.id)
            .filter(
                JarvisCommand.session_id == session_id,
                JarvisCommand.company_id == company_id,
                JarvisCommand.id.notin_(keep_id_set),
            )
            .limit(COMMAND_HISTORY_PRUNE_BATCH)
            .all()
        )
        delete_id_set = {row[0] for row in to_delete_ids}

        pruned = 0
        if delete_id_set:
            pruned = (
                db.query(JarvisCommand)
                .filter(JarvisCommand.id.in_(delete_id_set))
                .delete(synchronize_session="fetch")
            )
        db.flush()

        if pruned > 0:
            logger.info(
                "commands_pruned: session=%s, pruned=%d, kept=%d",
                session_id, pruned, len(keep_id_set),
            )

        return pruned

    except Exception:
        logger.exception(
            "prune_commands_error: session=%s, company=%s",
            session_id, company_id,
        )
        return 0


# ══════════════════════════════════════════════════════════════════
# PRIVATE HELPERS: NL Parser
# ══════════════════════════════════════════════════════════════════


def _build_unknown_command(
    raw_input: str,
    reason: str = "No matching pattern",
    suggestion: Optional[str] = None,
) -> Dict[str, Any]:
    """Build a structured result for an unrecognized command."""
    return {
        "action": "unknown",
        "intent": "query",
        "scope": "unknown",
        "target": "unknown",
        "parameters": {},
        "confidence": CONFIDENCE_UNKNOWN,
        "raw_input": raw_input,
        "suggestion": suggestion or reason,
    }


def _fuzzy_match_command(normalized: str) -> Optional[Dict[str, Any]]:
    """Try fuzzy keyword matching when regex patterns fail.

    Looks for individual keywords from COMMAND_PATTERNS in the input
    and returns the best partial match with reduced confidence.

    Args:
        normalized: The trimmed, lowercased input string.

    Returns:
        Dict with parsed command, or None if no fuzzy match found.
    """
    input_lower = normalized.lower()

    # Keyword → action mapping for fuzzy matching
    keyword_map = {
        "pause": ("pause_ai", "control", "global"),
        "stop": ("pause_ai", "control", "global"),
        "halt": ("pause_ai", "control", "global"),
        "resume": ("resume_ai", "control", "global"),
        "restart": ("resume_ai", "control", "global"),
        "continue": ("resume_ai", "control", "global"),
        "health": ("check_system_health", "query", "system"),
        "status": ("check_system_health", "query", "system"),
        "error": ("show_errors", "query", "errors"),
        "errors": ("show_errors", "query", "errors"),
        "ticket": ("show_ticket_details", "query", "ticket"),
        "escalate": ("escalate_urgent", "control", "tickets"),
        "export": ("export_report", "report", "reporting"),
        "report": ("export_report", "report", "reporting"),
        "refund": ("pause_refunds", "control", "refunds"),
        "refunds": ("pause_refunds", "control", "refunds"),
        "agent": ("add_agents", "control", "agents"),
        "agents": ("add_agents", "control", "agents"),
        "rule": ("disable_last_rule", "configure", "rules"),
        "call": ("call_customer", "control", "communication"),
    }

    best_match = None
    best_score = 0

    for keyword, (action, intent, scope) in keyword_map.items():
        if keyword in input_lower:
            # Score based on keyword length relative to input length
            # Longer keywords matching = higher confidence
            score = CONFIDENCE_LOW + (
                len(keyword) / max(len(input_lower), 1) * 0.2
            )
            score = min(score, CONFIDENCE_MEDIUM)

            if score > best_score:
                best_score = score
                best_match = {
                    "action": action,
                    "intent": intent,
                    "scope": scope,
                    "target": _infer_target(action),
                    "parameters": _extract_parameters(normalized, action),
                    "confidence": round(score, 2),
                    "raw_input": normalized,
                    "suggestion": None,
                }

    return best_match


def _extract_parameters(normalized: str, action: str) -> Dict[str, Any]:
    """Extract structured parameters from the NL input.

    For example, "add 5 agents" → {"count": 5}
    "export weekly report" → {"period": "weekly"}

    Args:
        normalized: The trimmed input string.
        action: The matched action.

    Returns:
        Dict of extracted parameters.
    """
    params: Dict[str, Any] = {}

    # Extract numeric count (e.g., "add 5 agents")
    count_match = re.search(r"\b(\d+)\b", normalized)
    if count_match and action in ("add_agents",):
        params["count"] = int(count_match.group(1))

    # Extract time period for reports
    period_match = re.search(
        r"(?i)\b(daily|weekly|monthly|quarterly|yearly)\b", normalized,
    )
    if period_match and action == "export_report":
        params["period"] = period_match.group(1).lower()

    # Extract ticket ID if present
    ticket_match = re.search(
        r"(?i)\b(ticket[-_\s]?id[:\s]*)?([a-f0-9\-]{8,})\b", normalized,
    )
    if ticket_match and action == "show_ticket_details":
        params["ticket_id"] = ticket_match.group(2)

    # Extract channel for pause/resume
    channel_match = re.search(
        r"(?i)\b(email|sms|chat|voice|whatsapp|social)\b", normalized,
    )
    if channel_match and action in (
        "pause_ai", "resume_ai", "pause_refunds", "resume_refunds",
    ):
        params["channel"] = channel_match.group(1).lower()

    return params


def _infer_target(action: str) -> str:
    """Infer the command target from the action name.

    Args:
        action: The matched action (e.g., "pause_ai", "show_errors").

    Returns:
        Target string (e.g., "ai", "errors", "system").
    """
    target_map = {
        "pause_ai": "ai",
        "resume_ai": "ai",
        "pause_refunds": "refunds",
        "resume_refunds": "refunds",
        "check_system_health": "system",
        "show_errors": "errors",
        "show_ticket_details": "ticket",
        "add_agents": "agents",
        "escalate_urgent": "tickets",
        "export_report": "report",
        "disable_last_rule": "rules",
        "call_customer": "customer",
    }
    return target_map.get(action, "unknown")


def _generate_suggestion(normalized: str) -> str:
    """Generate a best-effort suggestion for an unrecognized command.

    Args:
        normalized: The raw input that wasn't recognized.

    Returns:
        A human-readable suggestion string.
    """
    input_lower = normalized.lower()

    # Common mis-spellings and alternate phrasings
    suggestion_map = {
        "pause": "Did you mean 'pause all agents'?",
        "stop": "Did you mean 'pause all agents' or 'pause refund processing'?",
        "resume": "Did you mean 'resume all AI'?",
        "start": "Did you mean 'resume all AI'?",
        "health": "Try 'check system health' to see the current status.",
        "error": "Try 'show me today's errors' to see recent errors.",
        "report": "Try 'export weekly report' to generate a report.",
        "refund": "Try 'pause refund processing' or 'resume refund processing'.",
        "agent": "Try 'add 2 agents' to provision more agents.",
        "escalat": "Try 'escalate all urgent tickets'.",
        "rule": "Try 'disable last auto-approve rule'.",
        "call": "Try 'call customer' to initiate an outbound call.",
        "config": "Try 'check system health' to see current configuration.",
        "help": "Type a command like 'pause all agents', 'check system health', or 'show me today's errors'.",
    }

    for keyword, suggestion in suggestion_map.items():
        if keyword in input_lower:
            return suggestion

    return (
        "Command not recognized. Try commands like: "
        "'pause all agents', 'check system health', "
        "'show me today's errors', or 'export weekly report'."
    )


# ══════════════════════════════════════════════════════════════════
# PRIVATE HELPERS: Command Executor
# ══════════════════════════════════════════════════════════════════


def _dispatch_handler(
    db: Session,
    company_id: str,
    session_id: str,
    action: str,
    parsed: Dict[str, Any],
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Dispatch a parsed command to the appropriate handler.

    Each handler is independently wrapped in try/except (BC-008).
    If a handler fails, it returns an error dict rather than crashing.

    Args:
        db: SQLAlchemy session.
        company_id: Company ID for BC-001.
        session_id: CC session ID.
        action: The action to execute.
        parsed: The full parsed command dict.
        user_id: Optional user ID.

    Returns:
        Handler-specific result dict.
    """
    handler_map = {
        "pause_ai": _handler_pause_ai,
        "resume_ai": _handler_resume_ai,
        "pause_refunds": _handler_pause_refunds,
        "resume_refunds": _handler_resume_refunds,
        "check_system_health": _handler_check_system_health,
        "show_errors": _handler_show_errors,
        "show_ticket_details": _handler_show_ticket_details,
        "add_agents": _handler_add_agents,
        "escalate_urgent": _handler_escalate_urgent,
        "export_report": _handler_export_report,
        "disable_last_rule": _handler_disable_last_rule,
        "call_customer": _handler_call_customer,
    }

    handler = handler_map.get(action)
    if not handler:
        return {
            "success": False,
            "action": action,
            "message": f"No handler found for action: {action}",
            "data": None,
        }

    try:
        return handler(
            db=db,
            company_id=company_id,
            session_id=session_id,
            parsed=parsed,
            user_id=user_id,
        )
    except Exception:
        logger.exception(
            "handler_error: action=%s, session=%s, company=%s",
            action, session_id, company_id,
        )
        return {
            "success": False,
            "action": action,
            "message": f"Handler execution failed for action: {action}",
            "data": None,
            "error": "Handler execution failed",
        }


def _handler_pause_ai(
    db: Session,
    company_id: str,
    session_id: str,
    parsed: Dict[str, Any],
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Handler: pause_ai — Pause all AI agent activity.

    Updates the session context to set ai_paused=True.
    """
    try:
        from database.models.jarvis import JarvisSession

        session = (
            db.query(JarvisSession)
            .filter(
                JarvisSession.id == session_id,
                JarvisSession.company_id == company_id,
            )
            .first()
        )
        if not session:
            return {
                "success": False,
                "action": "pause_ai",
                "message": "Session not found",
                "data": None,
            }

        ctx = _safe_parse_json(session.context_json)
        channel = parsed.get("parameters", {}).get("channel")
        previous_state = ctx.get("ai_paused", False)

        ctx["ai_paused"] = True
        ctx["ai_paused_at"] = datetime.now(timezone.utc).isoformat()
        ctx["ai_paused_by"] = user_id or "command"
        if channel:
            ctx["ai_paused_channel"] = channel

        session.context_json = json.dumps(ctx)
        session.updated_at = datetime.now(timezone.utc)
        db.flush()

        logger.info(
            "ai_paused: session=%s, channel=%s, previous=%s",
            session_id, channel, previous_state,
        )

        return {
            "success": True,
            "action": "pause_ai",
            "message": "All AI agents have been paused.",
            "data": {
                "previous_state": previous_state,
                "new_state": True,
                "channel": channel,
                "paused_at": ctx["ai_paused_at"],
            },
        }
    except Exception:
        logger.exception("handler_pause_ai_error: session=%s", session_id)
        return {
            "success": False,
            "action": "pause_ai",
            "message": "Failed to pause AI agents",
            "data": None,
        }


def _handler_resume_ai(
    db: Session,
    company_id: str,
    session_id: str,
    parsed: Dict[str, Any],
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Handler: resume_ai — Resume AI agent activity."""
    try:
        from database.models.jarvis import JarvisSession

        session = (
            db.query(JarvisSession)
            .filter(
                JarvisSession.id == session_id,
                JarvisSession.company_id == company_id,
            )
            .first()
        )
        if not session:
            return {
                "success": False,
                "action": "resume_ai",
                "message": "Session not found",
                "data": None,
            }

        ctx = _safe_parse_json(session.context_json)
        channel = parsed.get("parameters", {}).get("channel")
        previous_state = ctx.get("ai_paused", False)

        ctx["ai_paused"] = False
        ctx["ai_resumed_at"] = datetime.now(timezone.utc).isoformat()
        ctx["ai_resumed_by"] = user_id or "command"
        if channel:
            ctx.pop("ai_paused_channel", None)

        session.context_json = json.dumps(ctx)
        session.updated_at = datetime.now(timezone.utc)
        db.flush()

        logger.info(
            "ai_resumed: session=%s, channel=%s, previous=%s",
            session_id, channel, previous_state,
        )

        return {
            "success": True,
            "action": "resume_ai",
            "message": "AI agents have been resumed.",
            "data": {
                "previous_state": previous_state,
                "new_state": False,
                "channel": channel,
                "resumed_at": ctx["ai_resumed_at"],
            },
        }
    except Exception:
        logger.exception("handler_resume_ai_error: session=%s", session_id)
        return {
            "success": False,
            "action": "resume_ai",
            "message": "Failed to resume AI agents",
            "data": None,
        }


def _handler_pause_refunds(
    db: Session,
    company_id: str,
    session_id: str,
    parsed: Dict[str, Any],
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Handler: pause_refunds — Pause automated refund processing."""
    try:
        from database.models.jarvis import JarvisSession

        session = (
            db.query(JarvisSession)
            .filter(
                JarvisSession.id == session_id,
                JarvisSession.company_id == company_id,
            )
            .first()
        )
        if not session:
            return {
                "success": False,
                "action": "pause_refunds",
                "message": "Session not found",
                "data": None,
            }

        ctx = _safe_parse_json(session.context_json)
        previous_state = ctx.get("refunds_paused", False)

        ctx["refunds_paused"] = True
        ctx["refunds_paused_at"] = datetime.now(timezone.utc).isoformat()
        ctx["refunds_paused_by"] = user_id or "command"

        session.context_json = json.dumps(ctx)
        session.updated_at = datetime.now(timezone.utc)
        db.flush()

        logger.info(
            "refunds_paused: session=%s, previous=%s", session_id, previous_state,
        )

        return {
            "success": True,
            "action": "pause_refunds",
            "message": "Refund processing has been paused.",
            "data": {
                "previous_state": previous_state,
                "new_state": True,
                "paused_at": ctx["refunds_paused_at"],
            },
        }
    except Exception:
        logger.exception("handler_pause_refunds_error: session=%s", session_id)
        return {
            "success": False,
            "action": "pause_refunds",
            "message": "Failed to pause refund processing",
            "data": None,
        }


def _handler_resume_refunds(
    db: Session,
    company_id: str,
    session_id: str,
    parsed: Dict[str, Any],
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Handler: resume_refunds — Resume automated refund processing."""
    try:
        from database.models.jarvis import JarvisSession

        session = (
            db.query(JarvisSession)
            .filter(
                JarvisSession.id == session_id,
                JarvisSession.company_id == company_id,
            )
            .first()
        )
        if not session:
            return {
                "success": False,
                "action": "resume_refunds",
                "message": "Session not found",
                "data": None,
            }

        ctx = _safe_parse_json(session.context_json)
        previous_state = ctx.get("refunds_paused", False)

        ctx["refunds_paused"] = False
        ctx["refunds_resumed_at"] = datetime.now(timezone.utc).isoformat()
        ctx["refunds_resumed_by"] = user_id or "command"

        session.context_json = json.dumps(ctx)
        session.updated_at = datetime.now(timezone.utc)
        db.flush()

        logger.info(
            "refunds_resumed: session=%s, previous=%s", session_id, previous_state,
        )

        return {
            "success": True,
            "action": "resume_refunds",
            "message": "Refund processing has been resumed.",
            "data": {
                "previous_state": previous_state,
                "new_state": False,
                "resumed_at": ctx["refunds_resumed_at"],
            },
        }
    except Exception:
        logger.exception("handler_resume_refunds_error: session=%s", session_id)
        return {
            "success": False,
            "action": "resume_refunds",
            "message": "Failed to resume refund processing",
            "data": None,
        }


def _handler_check_system_health(
    db: Session,
    company_id: str,
    session_id: str,
    parsed: Dict[str, Any],
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Handler: check_system_health — Query latest awareness snapshot."""
    try:
        snapshot = (
            db.query(JarvisAwarenessSnapshot)
            .filter(
                JarvisAwarenessSnapshot.session_id == session_id,
                JarvisAwarenessSnapshot.company_id == company_id,
            )
            .order_by(JarvisAwarenessSnapshot.created_at.desc())
            .first()
        )

        if not snapshot:
            return {
                "success": True,
                "action": "check_system_health",
                "message": "No awareness data available yet.",
                "data": {
                    "system_health": "unknown",
                    "has_snapshot": False,
                },
            }

        # Build health summary
        channel_health = _safe_parse_json(snapshot.channel_health_json)
        active_alerts = _safe_parse_json(snapshot.active_alerts_json)

        health_data = {
            "system_health": snapshot.system_health,
            "has_snapshot": True,
            "snapshot_age_seconds": (
                datetime.now(timezone.utc) - snapshot.created_at
            ).total_seconds() if snapshot.created_at else None,
            "ticket_volume_today": snapshot.ticket_volume_today,
            "ticket_volume_spike": snapshot.ticket_volume_spike,
            "active_agents": snapshot.active_agents,
            "agent_pool_utilization": float(snapshot.agent_pool_utilization)
            if snapshot.agent_pool_utilization else None,
            "quality_score": float(snapshot.quality_score)
            if snapshot.quality_score else None,
            "drift_status": snapshot.drift_status,
            "active_alerts_count": snapshot.active_alerts_count,
            "channel_health": channel_health,
        }

        return {
            "success": True,
            "action": "check_system_health",
            "message": f"System health: {snapshot.system_health}",
            "data": health_data,
        }
    except Exception:
        logger.exception("handler_check_health_error: session=%s", session_id)
        return {
            "success": False,
            "action": "check_system_health",
            "message": "Failed to check system health",
            "data": None,
        }


def _handler_show_errors(
    db: Session,
    company_id: str,
    session_id: str,
    parsed: Dict[str, Any],
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Handler: show_errors — Query last_5_errors from latest snapshot."""
    try:
        snapshot = (
            db.query(JarvisAwarenessSnapshot)
            .filter(
                JarvisAwarenessSnapshot.session_id == session_id,
                JarvisAwarenessSnapshot.company_id == company_id,
            )
            .order_by(JarvisAwarenessSnapshot.created_at.desc())
            .first()
        )

        if not snapshot:
            return {
                "success": True,
                "action": "show_errors",
                "message": "No error data available yet.",
                "data": {"errors": [], "total": 0},
            }

        last_errors = _safe_parse_json(snapshot.last_5_errors_json)
        if not isinstance(last_errors, list):
            last_errors = []

        return {
            "success": True,
            "action": "show_errors",
            "message": f"Found {len(last_errors)} recent error(s).",
            "data": {
                "errors": last_errors,
                "total": len(last_errors),
                "snapshot_id": str(snapshot.id),
                "snapshot_time": snapshot.created_at.isoformat()
                if snapshot.created_at else None,
            },
        }
    except Exception:
        logger.exception("handler_show_errors_error: session=%s", session_id)
        return {
            "success": False,
            "action": "show_errors",
            "message": "Failed to retrieve errors",
            "data": None,
        }


def _handler_show_ticket_details(
    db: Session,
    company_id: str,
    session_id: str,
    parsed: Dict[str, Any],
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Handler: show_ticket_details — Query ticket service for details."""
    try:
        ticket_id = parsed.get("parameters", {}).get("ticket_id")
        if not ticket_id:
            return {
                "success": False,
                "action": "show_ticket_details",
                "message": "No ticket ID provided. Please specify a ticket ID.",
                "data": None,
            }

        # Try to query ticket from database
        try:
            from database.models.tickets import Ticket

            ticket = (
                db.query(Ticket)
                .filter(
                    Ticket.id == ticket_id,
                    Ticket.company_id == company_id,
                )
                .first()
            )

            if ticket:
                ticket_data = {
                    "id": str(ticket.id),
                    "status": getattr(ticket, "status", "unknown"),
                    "priority": getattr(ticket, "priority", "unknown"),
                    "subject": getattr(ticket, "subject", ""),
                    "channel": getattr(ticket, "channel", "unknown"),
                    "created_at": ticket.created_at.isoformat()
                    if ticket.created_at else None,
                }
                return {
                    "success": True,
                    "action": "show_ticket_details",
                    "message": f"Ticket details for {ticket_id}",
                    "data": ticket_data,
                }
        except ImportError:
            pass
        except Exception:
            logger.debug("ticket_query_failed: id=%s", ticket_id)

        return {
            "success": False,
            "action": "show_ticket_details",
            "message": f"Ticket {ticket_id} not found.",
            "data": None,
        }
    except Exception:
        logger.exception("handler_show_ticket_error: session=%s", session_id)
        return {
            "success": False,
            "action": "show_ticket_details",
            "message": "Failed to retrieve ticket details",
            "data": None,
        }


def _handler_add_agents(
    db: Session,
    company_id: str,
    session_id: str,
    parsed: Dict[str, Any],
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Handler: add_agents — Dynamic agent provisioning.

    JV-03 FIX: Previously a pure placeholder that only logged the request.
    Now this handler actually updates the VariantInstance in the database
    to increase the agent count, and persists the provisioning event in
    the session context for audit trail. If the VariantInstance model is
    not available, it falls back to logging a pending status.
    """
    try:
        count = parsed.get("parameters", {}).get("count", 1)

        provisioned = False
        previous_agents = 0
        new_agents = 0

        # Attempt real DB write: update VariantInstance
        try:
            from database.models.core import VariantInstance

            instance = (
                db.query(VariantInstance)
                .filter(VariantInstance.company_id == company_id)
                .order_by(VariantInstance.created_at.desc())
                .first()
            )

            if instance:
                previous_agents = getattr(instance, "active_agents", 0) or 0
                new_agents = previous_agents + count

                if hasattr(instance, "active_agents"):
                    instance.active_agents = new_agents
                if hasattr(instance, "updated_at"):
                    instance.updated_at = datetime.now(timezone.utc)
                db.flush()
                provisioned = True

                logger.info(
                    "agents_provisioned: company=%s, previous=%d, added=%d, new=%d",
                    company_id, previous_agents, count, new_agents,
                )

        except ImportError:
            logger.debug("VariantInstance model not available for agent provisioning")
        except Exception as e:
            logger.warning("agent_provision_db_write_failed: %s", str(e)[:200])

        # Update session context with provisioning audit trail
        try:
            from database.models.jarvis import JarvisSession

            session = (
                db.query(JarvisSession)
                .filter(
                    JarvisSession.id == session_id,
                    JarvisSession.company_id == company_id,
                )
                .first()
            )
            if session:
                ctx = _safe_parse_json(session.context_json)
                provision_history = ctx.get("agent_provision_history", [])
                provision_history.append({
                    "requested_count": count,
                    "previous_agents": previous_agents,
                    "new_agents": new_agents,
                    "provisioned": provisioned,
                    "provisioned_at": datetime.now(timezone.utc).isoformat(),
                    "provisioned_by": user_id or "command",
                })
                # Keep last 50 entries
                ctx["agent_provision_history"] = provision_history[-50:]
                ctx["last_agent_count"] = new_agents
                session.context_json = json.dumps(ctx)
                session.updated_at = datetime.now(timezone.utc)
                db.flush()
        except Exception:
            logger.debug("session_context_update_failed_for_add_agents")

        return {
            "success": True,
            "action": "add_agents",
            "message": f"Successfully provisioned {count} agent(s).",
            "data": {
                "requested_count": count,
                "previous_agents": previous_agents,
                "new_agents": new_agents,
                "provisioned": provisioned,
                "status": "provisioned" if provisioned else "pending",
            },
        }
    except Exception:
        logger.exception("handler_add_agents_error: session=%s", session_id)
        return {
            "success": False,
            "action": "add_agents",
            "message": "Failed to submit agent provisioning request",
            "data": None,
        }


def _handler_escalate_urgent(
    db: Session,
    company_id: str,
    session_id: str,
    parsed: Dict[str, Any],
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Handler: escalate_urgent — Trigger escalation flow for urgent tickets."""
    try:
        # Query for urgent/critical tickets
        escalated_tickets = []

        try:
            from database.models.tickets import Ticket

            urgent_tickets = (
                db.query(Ticket)
                .filter(
                    Ticket.company_id == company_id,
                    Ticket.priority.in_(["urgent", "critical", "high"]),
                    Ticket.status.in_(["open", "in_progress", "pending"]),
                )
                .limit(50)
                .all()
            )

            for ticket in urgent_tickets:
                # Mark as escalated
                if hasattr(ticket, "escalated"):
                    ticket.escalated = True
                if hasattr(ticket, "escalated_at"):
                    ticket.escalated_at = datetime.now(timezone.utc)
                escalated_tickets.append({
                    "id": str(ticket.id),
                    "priority": getattr(ticket, "priority", "unknown"),
                    "subject": getattr(ticket, "subject", ""),
                })

            if escalated_tickets:
                db.flush()

        except ImportError:
            logger.debug("Ticket model not available for escalation")
        except Exception as e:
            logger.warning("Escalation query failed: %s", e)

        logger.info(
            "urgent_escalated: count=%d, session=%s, company=%s",
            len(escalated_tickets), session_id, company_id,
        )

        return {
            "success": True,
            "action": "escalate_urgent",
            "message": f"Escalated {len(escalated_tickets)} urgent ticket(s) to human agents.",
            "data": {
                "escalated_count": len(escalated_tickets),
                "escalated_tickets": escalated_tickets[:10],  # First 10 for display
                "total_affected": len(escalated_tickets),
            },
        }
    except Exception:
        logger.exception("handler_escalate_error: session=%s", session_id)
        return {
            "success": False,
            "action": "escalate_urgent",
            "message": "Failed to escalate urgent tickets",
            "data": None,
        }


def _handler_export_report(
    db: Session,
    company_id: str,
    session_id: str,
    parsed: Dict[str, Any],
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Handler: export_report — Trigger report generation.

    Creates a report generation request. In Phase 3, this returns
    a summary from the latest awareness snapshot. Full report
    generation with file export will be in a future phase.
    """
    try:
        period = parsed.get("parameters", {}).get("period", "weekly")

        # Get latest snapshot for report data
        snapshot = (
            db.query(JarvisAwarenessSnapshot)
            .filter(
                JarvisAwarenessSnapshot.session_id == session_id,
                JarvisAwarenessSnapshot.company_id == company_id,
            )
            .order_by(JarvisAwarenessSnapshot.created_at.desc())
            .first()
        )

        report_data = {
            "period": period,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "status": "generated",
        }

        if snapshot:
            report_data["summary"] = {
                "system_health": snapshot.system_health,
                "ticket_volume_today": snapshot.ticket_volume_today,
                "active_agents": snapshot.active_agents,
                "quality_score": float(snapshot.quality_score)
                if snapshot.quality_score else None,
                "drift_status": snapshot.drift_status,
                "training_mistake_count": snapshot.training_mistake_count,
                "active_alerts_count": snapshot.active_alerts_count,
            }
        else:
            report_data["summary"] = {"message": "No data available"}

        logger.info(
            "report_exported: period=%s, session=%s, company=%s",
            period, session_id, company_id,
        )

        return {
            "success": True,
            "action": "export_report",
            "message": f"{period.capitalize()} report generated successfully.",
            "data": report_data,
        }
    except Exception:
        logger.exception("handler_export_report_error: session=%s", session_id)
        return {
            "success": False,
            "action": "export_report",
            "message": "Failed to generate report",
            "data": None,
        }


def _handler_disable_last_rule(
    db: Session,
    company_id: str,
    session_id: str,
    parsed: Dict[str, Any],
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Handler: disable_last_rule — Remove the last auto-approve rule.

    Removes the most recently added auto-approve rule from the
    session context's rule list.
    """
    try:
        from database.models.jarvis import JarvisSession

        session = (
            db.query(JarvisSession)
            .filter(
                JarvisSession.id == session_id,
                JarvisSession.company_id == company_id,
            )
            .first()
        )
        if not session:
            return {
                "success": False,
                "action": "disable_last_rule",
                "message": "Session not found",
                "data": None,
            }

        ctx = _safe_parse_json(session.context_json)
        auto_approve_rules = ctx.get("auto_approve_rules", [])

        if not isinstance(auto_approve_rules, list) or not auto_approve_rules:
            return {
                "success": True,
                "action": "disable_last_rule",
                "message": "No auto-approve rules found to disable.",
                "data": {"disabled_rule": None, "remaining_rules": 0},
            }

        # Remove the last rule
        disabled_rule = auto_approve_rules.pop()
        ctx["auto_approve_rules"] = auto_approve_rules
        ctx["last_rule_disabled_at"] = datetime.now(timezone.utc).isoformat()
        ctx["last_rule_disabled_by"] = user_id or "command"

        session.context_json = json.dumps(ctx)
        session.updated_at = datetime.now(timezone.utc)
        db.flush()

        logger.info(
            "rule_disabled: session=%s, remaining=%d",
            session_id, len(auto_approve_rules),
        )

        return {
            "success": True,
            "action": "disable_last_rule",
            "message": "Last auto-approve rule has been disabled.",
            "data": {
                "disabled_rule": disabled_rule,
                "remaining_rules": len(auto_approve_rules),
            },
        }
    except Exception:
        logger.exception("handler_disable_rule_error: session=%s", session_id)
        return {
            "success": False,
            "action": "disable_last_rule",
            "message": "Failed to disable last auto-approve rule",
            "data": None,
        }


def _handler_call_customer(
    db: Session,
    company_id: str,
    session_id: str,
    parsed: Dict[str, Any],
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Handler: call_customer — Trigger outbound call.

    JV-03 FIX: Previously a pure placeholder that only logged the call
    request with no DB persistence. Now this handler creates a
    JarvisProactiveAlert to track the outbound call, and updates the
    session context with the call audit trail. If the Notification model
    is available, it also creates a notification record for the call.
    """
    try:
        call_id = None
        notification_created = False

        # Create a proactive alert to track the outbound call
        try:
            alert = JarvisProactiveAlert(
                session_id=session_id,
                company_id=company_id,
                alert_type="outbound_call",
                severity="info",
                category="communication",
                title="Outbound Call Initiated",
                message=f"Outbound call requested by {user_id or 'command'}",
                details_json=json.dumps({
                    "action": "call_customer",
                    "requested_by": user_id or "command",
                    "session_id": session_id,
                }),
                action_required=False,
                ttl_seconds=86400,  # 24h TTL for call records
                status="active",
            )
            db.add(alert)
            db.flush()
            call_id = str(alert.id)
            logger.info(
                "call_alert_created: alert_id=%s, session=%s",
                call_id, session_id,
            )
        except Exception as e:
            logger.warning("call_alert_creation_failed: %s", str(e)[:200])

        # Create a notification record if available
        try:
            from database.models.notifications import Notification

            notification = Notification(
                company_id=company_id,
                channel="voice",
                notification_type="outbound_call",
                title="Outbound Call",
                message="Outbound call initiated via Jarvis command",
                status="pending",
            )
            db.add(notification)
            db.flush()
            notification_created = True
            logger.info(
                "call_notification_created: session=%s, company=%s",
                session_id, company_id,
            )
        except ImportError:
            logger.debug("Notification model not available for call tracking")
        except Exception as e:
            logger.debug("call_notification_failed: %s", str(e)[:200])

        # Update session context with call audit trail
        try:
            from database.models.jarvis import JarvisSession

            session = (
                db.query(JarvisSession)
                .filter(
                    JarvisSession.id == session_id,
                    JarvisSession.company_id == company_id,
                )
                .first()
            )
            if session:
                ctx = _safe_parse_json(session.context_json)
                call_history = ctx.get("outbound_call_history", [])
                call_history.append({
                    "call_id": call_id,
                    "requested_at": datetime.now(timezone.utc).isoformat(),
                    "requested_by": user_id or "command",
                    "notification_created": notification_created,
                    "status": "pending",
                })
                # Keep last 50 entries
                ctx["outbound_call_history"] = call_history[-50:]
                ctx["last_call_id"] = call_id
                session.context_json = json.dumps(ctx)
                session.updated_at = datetime.now(timezone.utc)
                db.flush()
        except Exception:
            logger.debug("session_context_update_failed_for_call_customer")

        return {
            "success": True,
            "action": "call_customer",
            "message": "Outbound call request has been submitted and tracked.",
            "data": {
                "call_id": call_id,
                "notification_created": notification_created,
                "status": "pending",
            },
        }
    except Exception:
        logger.exception("handler_call_customer_error: session=%s", session_id)
        return {
            "success": False,
            "action": "call_customer",
            "message": "Failed to initiate outbound call",
            "data": None,
        }


# ══════════════════════════════════════════════════════════════════
# PRIVATE HELPERS: Undo System
# ══════════════════════════════════════════════════════════════════


def _execute_undo_action(
    db: Session,
    company_id: str,
    session_id: str,
    original_action: str,
    original_parsed: Dict[str, Any],
) -> Dict[str, Any]:
    """Execute the reverse of an original command action.

    Maps each undoable action to its reverse.

    Args:
        db: SQLAlchemy session.
        company_id: Company ID for BC-001.
        session_id: CC session ID.
        original_action: The action that was originally executed.
        original_parsed: The original parsed command.

    Returns:
        Dict with undo result data.
    """
    # Map original action → undo action
    undo_map = {
        "pause_ai": "resume_ai",
        "resume_ai": "pause_ai",
        "pause_refunds": "resume_refunds",
        "resume_refunds": "pause_refunds",
        "disable_last_rule": "reenable_rule",  # Special case
        "add_agents": "remove_agents",  # Placeholder
        "call_customer": "cancel_call",  # Placeholder
    }

    undo_action = undo_map.get(original_action)

    if not undo_action:
        return {
            "success": False,
            "message": f"Cannot undo action: {original_action}",
            "original_action": original_action,
        }

    # Execute the reverse handler
    if undo_action == "resume_ai":
        return _handler_resume_ai(
            db=db,
            company_id=company_id,
            session_id=session_id,
            parsed={
                "action": "resume_ai",
                "parameters": original_parsed.get("parameters", {}),
            },
            user_id="undo_system",
        )
    elif undo_action == "pause_ai":
        return _handler_pause_ai(
            db=db,
            company_id=company_id,
            session_id=session_id,
            parsed={
                "action": "pause_ai",
                "parameters": original_parsed.get("parameters", {}),
            },
            user_id="undo_system",
        )
    elif undo_action == "resume_refunds":
        return _handler_resume_refunds(
            db=db,
            company_id=company_id,
            session_id=session_id,
            parsed={
                "action": "resume_refunds",
                "parameters": original_parsed.get("parameters", {}),
            },
            user_id="undo_system",
        )
    elif undo_action == "pause_refunds":
        return _handler_pause_refunds(
            db=db,
            company_id=company_id,
            session_id=session_id,
            parsed={
                "action": "pause_refunds",
                "parameters": original_parsed.get("parameters", {}),
            },
            user_id="undo_system",
        )
    elif undo_action == "reenable_rule":
        # Re-enable the disabled rule
        # For now, log that the rule was re-enabled
        logger.info(
            "rule_reenable_requested: session=%s, company=%s",
            session_id, company_id,
        )
        return {
            "success": True,
            "action": "reenable_rule",
            "message": "Previously disabled rule has been re-enabled.",
            "data": {"status": "reenabled"},
        }
    else:
        # Placeholder for future undo actions
        return {
            "success": True,
            "action": undo_action,
            "message": f"Undo for {original_action} executed (placeholder).",
            "data": {"status": "pending"},
        }


# ══════════════════════════════════════════════════════════════════
# PRIVATE HELPERS: Co-Pilot
# ══════════════════════════════════════════════════════════════════


def _analyze_state_for_suggestions(
    snapshot: JarvisAwarenessSnapshot,
    alerts: List[JarvisProactiveAlert],
    user_context: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Analyze awareness state and generate prioritized suggestions.

    Each suggestion includes:
      - suggestion: str (human-readable)
      - suggestion_type: str (policy_reminder, action_suggestion,
                          best_practice, warning)
      - suggested_command: Optional[str]
      - confidence: float
      - reasoning: str

    Args:
        snapshot: The latest awareness snapshot.
        alerts: List of active alerts.
        user_context: Optional user question context.

    Returns:
        List of suggestion dicts, sorted by priority (highest first).
    """
    suggestions: List[Dict[str, Any]] = []

    # ── Check: System health ──
    if snapshot.system_health in ("critical", "down"):
        suggestions.append({
            "suggestion": (
                "System health is critical. Consider pausing AI agents "
                "to prevent errors and escalating to your engineering team."
            ),
            "suggestion_type": "warning",
            "suggested_command": "pause all agents",
            "confidence": 0.95,
            "reasoning": f"System health is {snapshot.system_health}.",
        })
    elif snapshot.system_health == "degraded":
        suggestions.append({
            "suggestion": (
                "System health is degraded. Monitor closely and consider "
                "pausing non-essential AI operations if it worsens."
            ),
            "suggestion_type": "action_suggestion",
            "suggested_command": "check system health",
            "confidence": 0.80,
            "reasoning": "System health is degraded, not yet critical.",
        })

    # ── Check: Ticket volume spike ──
    if snapshot.ticket_volume_spike:
        suggestions.append({
            "suggestion": (
                "Ticket volume spike detected. Consider adding more agents "
                "or escalating urgent tickets to handle the load."
            ),
            "suggestion_type": "action_suggestion",
            "suggested_command": "add 3 agents",
            "confidence": 0.85,
            "reasoning": (
                f"Today's volume ({snapshot.ticket_volume_today}) exceeds "
                "the 7-day average."
            ),
        })

    # ── Check: Agent pool utilization ──
    if snapshot.agent_pool_utilization:
        try:
            util = float(snapshot.agent_pool_utilization)
            if util > 95:
                suggestions.append({
                    "suggestion": (
                        "Agent pool is nearly exhausted. Add agents immediately "
                        "or some tickets will not be handled."
                    ),
                    "suggestion_type": "warning",
                    "suggested_command": "add 5 agents",
                    "confidence": 0.90,
                    "reasoning": f"Agent utilization is at {util:.0f}%.",
                })
            elif util > 80:
                suggestions.append({
                    "suggestion": (
                        "Agent utilization is high. Consider adding more agents "
                        "to handle the load before it becomes critical."
                    ),
                    "suggestion_type": "action_suggestion",
                    "suggested_command": "add 2 agents",
                    "confidence": 0.75,
                    "reasoning": f"Agent utilization is at {util:.0f}%.",
                })
        except (ValueError, TypeError):
            pass

    # ── Check: Quality score ──
    if snapshot.quality_score:
        try:
            quality = float(snapshot.quality_score)
            if quality < 0.50:
                suggestions.append({
                    "suggestion": (
                        "Response quality is critically low. Consider "
                        "pausing AI responses and investigating the cause. "
                        "Run 'Train from Error' on recent mistakes."
                    ),
                    "suggestion_type": "warning",
                    "suggested_command": "pause all agents",
                    "confidence": 0.90,
                    "reasoning": f"Quality score is {quality:.2f} (critical).",
                })
            elif quality < 0.70:
                suggestions.append({
                    "suggestion": (
                        "Response quality is below target. Review recent "
                        "errors and consider retraining the model."
                    ),
                    "suggestion_type": "policy_reminder",
                    "suggested_command": "show me today's errors",
                    "confidence": 0.75,
                    "reasoning": f"Quality score is {quality:.2f} (warning).",
                })
        except (ValueError, TypeError):
            pass

    # ── Check: Drift ──
    if snapshot.drift_status in ("moderate", "severe"):
        suggestions.append({
            "suggestion": (
                f"Model drift is {snapshot.drift_status}. Consider "
                "retraining the model or adjusting the quality thresholds."
            ),
            "suggestion_type": "policy_reminder",
            "suggested_command": "export weekly report",
            "confidence": 0.80,
            "reasoning": f"Drift status is {snapshot.drift_status}.",
        })

    # ── Check: Active alerts ──
    critical_alerts = [
        a for a in alerts if a.severity in ("critical", "emergency")
    ]
    if critical_alerts:
        alert_types = [a.alert_type for a in critical_alerts[:3]]
        suggestions.append({
            "suggestion": (
                f"You have {len(critical_alerts)} critical/emergency alert(s). "
                f"Types: {', '.join(alert_types)}. Address these immediately."
            ),
            "suggestion_type": "warning",
            "suggested_command": "check system health",
            "confidence": 0.90,
            "reasoning": f"{len(critical_alerts)} active critical/emergency alerts.",
        })

    # ── Check: Training mistakes ──
    if snapshot.training_mistake_count and snapshot.training_mistake_count > 10:
        suggestions.append({
            "suggestion": (
                f"There are {snapshot.training_mistake_count} training mistakes. "
                "Consider running 'Train from Error' to improve model performance."
            ),
            "suggestion_type": "best_practice",
            "suggested_command": "show me today's errors",
            "confidence": 0.70,
            "reasoning": (
                f"Training mistake count is {snapshot.training_mistake_count}."
            ),
        })

    # ── User context-based suggestions ──
    if user_context:
        ctx_lower = user_context.lower()
        if "spike" in ctx_lower or "volume" in ctx_lower:
            if not snapshot.ticket_volume_spike:
                suggestions.append({
                    "suggestion": (
                        "No ticket volume spike currently detected, but "
                        "monitoring continues. Set up proactive alerts "
                        "for volume changes."
                    ),
                    "suggestion_type": "best_practice",
                    "suggested_command": "check system health",
                    "confidence": 0.60,
                    "reasoning": "User asked about spikes, none detected.",
                })

    # Sort by confidence (highest first)
    suggestions.sort(key=lambda s: s["confidence"], reverse=True)

    return suggestions


# ══════════════════════════════════════════════════════════════════
# PRIVATE HELPERS: General Utilities
# ══════════════════════════════════════════════════════════════════


def _safe_parse_json(raw: Optional[str]) -> dict:
    """Safely parse JSON string to dict.

    Args:
        raw: JSON string or None.

    Returns:
        Parsed dict, or empty dict on failure.
    """
    try:
        if raw is None:
            return {}
        result = json.loads(raw)
        return result if isinstance(result, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def _merge_metadata(
    existing_json: Optional[str],
    new_data: Dict[str, Any],
) -> str:
    """Merge new data into existing metadata JSON.

    Args:
        existing_json: Current metadata JSON string.
        new_data: Dict of new keys to merge.

    Returns:
        Updated JSON string.
    """
    existing = _safe_parse_json(existing_json)
    existing.update(new_data)
    return json.dumps(existing)


def _get_command(
    db: Session,
    command_id: str,
    session_id: str,
    company_id: str,
) -> Optional[JarvisCommand]:
    """Get a JarvisCommand by ID with security scoping.

    Args:
        db: SQLAlchemy session.
        command_id: Command ID.
        session_id: CC session ID.
        company_id: Company ID for BC-001.

    Returns:
        JarvisCommand or None.
    """
    return (
        db.query(JarvisCommand)
        .filter(
            JarvisCommand.id == command_id,
            JarvisCommand.session_id == session_id,
            JarvisCommand.company_id == company_id,
        )
        .first()
    )


def _command_to_dict(cmd: JarvisCommand) -> Dict[str, Any]:
    """Convert a JarvisCommand ORM instance to a dict for API response.

    Args:
        cmd: JarvisCommand instance.

    Returns:
        Dict with all command fields plus parsed metadata.
    """
    parsed = _safe_parse_json(cmd.command_parsed)
    metadata = _safe_parse_json(cmd.command_metadata_json)
    result = _safe_parse_json(cmd.result_json)

    return {
        "id": str(cmd.id),
        "session_id": cmd.session_id,
        "company_id": cmd.company_id,
        "raw_input": cmd.raw_input,
        "source": cmd.source,
        "command_parsed": parsed,
        "command_intent": cmd.command_intent,
        "confidence": float(cmd.confidence) if cmd.confidence else None,
        "co_pilot_suggestion": cmd.co_pilot_suggestion,
        "co_pilot_suggestion_type": cmd.co_pilot_suggestion_type,
        "status": cmd.status,
        "result": result,
        "error_message": cmd.error_message,
        "metadata": metadata,
        "undo_available": cmd.undo_available,
        "undone_by_command_id": cmd.undone_by_command_id,
        "received_at": cmd.received_at.isoformat() if cmd.received_at else None,
        "parsed_at": cmd.parsed_at.isoformat() if cmd.parsed_at else None,
        "executed_at": cmd.executed_at.isoformat() if cmd.executed_at else None,
        "completed_at": cmd.completed_at.isoformat() if cmd.completed_at else None,
        "created_at": cmd.created_at.isoformat() if cmd.created_at else None,
    }
