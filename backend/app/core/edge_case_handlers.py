"""
SG-28: Edge-Case Handler Registry (~20 handlers)

Registry pattern for detecting and handling edge cases in the AI
customer support pipeline. Each handler inspects the incoming query
and optional context dict, deciding whether it can handle a specific
edge case.

Architecture:
- EdgeCaseHandler ABC base class
- EdgeCaseAction enum (PROCEED/REWRITE/REDIRECT/BLOCK/ESCALATE)
- EdgeCaseResult / EdgeCaseProcessingResult dataclasses
- EdgeCaseRegistry central orchestrator

BC-001: All operations scoped to company_id.
BC-008: Graceful degradation on errors.
GAP-022: 2s per-handler timeout, 10s total chain timeout.
GAP-023: Handler chain customizable per variant (mini_parwa runs fewer).
"""

from __future__ import annotations

import re
import time
import unicodedata
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Type

from backend.app.logger import get_logger

logger = get_logger("edge_case_handlers")


# ══════════════════════════════════════════════════════════════════
# CONSTANTS
# ══════════════════════════════════════════════════════════════════

MAX_QUERY_LENGTH = 10000
HANDLER_TIMEOUT_SECONDS = 2.0
CHAIN_TIMEOUT_SECONDS = 10.0
DUPLICATE_SIMILARITY_THRESHOLD = 0.9
MULTI_QUESTION_THRESHOLD = 3
CONTEXT_EXPIRY_MINUTES = 30
CONFIDENCE_THRESHOLD = 0.5

# ── FAQ keyword → answer mapping ────────────────────────────────
_FAQ_TABLE: Dict[str, str] = {
    "how do i reset my password": (
        "You can reset your password by clicking "
        "'Forgot Password' on the login page."
    ),
    "how do i cancel my subscription": (
        "To cancel, go to Settings > Billing > Cancel Plan."
    ),
    "how do i contact support": (
        "You can reach us via the chat widget or "
        "email support@example.com."
    ),
    "what are your business hours": (
        "Our support team is available Mon–Fri, "
        "9 AM – 6 PM (UTC)."
    ),
    "how do i upgrade my plan": (
        "Go to Settings > Billing > Change Plan "
        "to upgrade anytime."
    ),
}

# ── Pricing keywords ────────────────────────────────────────────
_PRICING_KEYWORDS: Set[str] = {
    "pricing", "plan", "cost", "upgrade", "enterprise",
    "subscription fee", "billing", "invoice", "payment",
    "how much", "price",
}

# ── Legal terminology keywords ──────────────────────────────────
_LEGAL_KEYWORDS: Set[str] = {
    "lawsuit", "attorney", "legal action", "dmca", "gdpr",
    "litigation", "subpoena", "compliance", "regulation",
    "liability", "indemnification", "breach of contract",
}

# ── Competitor list (configurable) ──────────────────────────────
DEFAULT_COMPETITORS: Set[str] = {
    "zendesk", "freshdesk", "intercom", "help scout",
    "crisp", "tawk.to", "livechat", "drift",
}

# ── System command patterns ─────────────────────────────────────
_SYSTEM_COMMAND_PATTERNS: List[str] = [
    r"/admin\b",
    r"/system\b",
    r"\bsudo\b",
    r"\broot access\b",
    r"\bDROP\s+TABLE\b",
    r"\bDELETE\s+FROM\b",
    r"\bTRUNCATE\b",
    r"\bexec\s*\(",
    r"\beval\s*\(",
    r"\bos\.system\b",
]

# ── Malicious HTML patterns ─────────────────────────────────────
_MALICIOUS_HTML_PATTERNS: List[str] = [
    r"<script",
    r"javascript:",
    r"\bonerror\s*=",
    r"\bonclick\s*=",
    r"<iframe",
    r"<object",
    r"<embed",
    r"vbscript:",
    r"data:text/html",
]

# ── Unsupported language ranges (Unicode block starts) ──────────
_UNSUPPORTED_RANGES: List[tuple[int, int, str]] = [
    (0x4E00, 0x9FFF, "CJK"),          # CJK Unified Ideographs
    (0x3040, 0x309F, "Japanese"),      # Hiragana
    (0x30A0, 0x30FF, "Japanese"),      # Katakana
    (0xAC00, 0xD7AF, "Korean"),        # Hangul Syllables
    (0x0600, 0x06FF, "Arabic"),        # Arabic
    (0x0590, 0x05FF, "Hebrew"),        # Hebrew
    (0x0400, 0x04FF, "Cyrillic"),      # Cyrillic
    (0x0E00, 0x0E7F, "Thai"),          # Thai
    (0x0900, 0x097F, "Devanagari"),    # Devanagari
]

# ── Variant-specific handler allowlists (GAP-023) ───────────────
# mini_parwa runs a reduced set for faster L1 processing
VARIANT_HANDLER_WHITELIST: Dict[str, List[str]] = {
    "mini_parwa": [
        "empty_query", "too_long_query", "malicious_html",
        "blocked_user", "maintenance_mode", "timeout",
        "emojis_only", "code_blocks", "system_commands",
        "faq_match",
    ],
    "parwa": None,      # All handlers
    "parwa_high": None, # All handlers
}

# Compiled regex for system commands (module-level)
_RE_SYSTEM_COMMANDS = re.compile(
    "|".join(_SYSTEM_COMMAND_PATTERNS),
    re.IGNORECASE,
)
_RE_MALICIOUS_HTML = re.compile(
    "|".join(_MALICIOUS_HTML_PATTERNS),
    re.IGNORECASE,
)
_RE_CODE_FENCE = re.compile(r"```[\s\S]*?```", re.MULTILINE)


# ══════════════════════════════════════════════════════════════════
# ENUMS & DATA CLASSES
# ══════════════════════════════════════════════════════════════════


class EdgeCaseAction(str, Enum):
    """Actions an edge-case handler can request."""
    PROCEED = "proceed"
    REWRITE = "rewrite"
    REDIRECT = "redirect"
    BLOCK = "block"
    ESCALATE = "escalate"


class EdgeCaseSeverity(str, Enum):
    """Severity levels for edge-case findings."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class EdgeCaseResult:
    """Result produced by a single edge-case handler.

    Attributes:
        handler_type: Identifier of the handler that produced this.
        action: What the pipeline should do next.
        severity: How severe this edge case is.
        rewritten_query: If action is REWRITE, the cleaned query.
        redirect_target: If action is REDIRECT, where to send.
        reason: Human-readable explanation.
        metadata: Extra structured data for logging/analytics.
    """
    handler_type: str
    action: EdgeCaseAction
    severity: str = EdgeCaseSeverity.LOW.value
    rewritten_query: Optional[str] = None
    redirect_target: Optional[str] = None
    reason: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EdgeCaseProcessingResult:
    """Aggregated result after running the full handler chain.

    Attributes:
        final_action: The most restrictive action from the chain.
        final_query: The query after any rewrites.
        handlers_triggered: List of handler_type strings that fired.
        blocked: Whether the query was blocked.
        rewritten: Whether the query was rewritten.
        processing_time_ms: Total chain processing time.
        results: Individual results from each triggered handler.
    """
    final_action: EdgeCaseAction = EdgeCaseAction.PROCEED
    final_query: str = ""
    handlers_triggered: List[str] = field(default_factory=list)
    blocked: bool = False
    rewritten: bool = False
    processing_time_ms: float = 0.0
    results: List[EdgeCaseResult] = field(default_factory=list)


# ══════════════════════════════════════════════════════════════════
# ABSTRACT BASE HANDLER
# ══════════════════════════════════════════════════════════════════


class EdgeCaseHandler(ABC):
    """Base class for all edge-case handlers.

    Subclasses must define handler_type, priority, can_handle(),
    and handle().
    """

    @property
    @abstractmethod
    def handler_type(self) -> str:
        """Unique string identifier for this handler."""
        ...

    @property
    @abstractmethod
    def priority(self) -> int:
        """Integer priority (lower = runs first)."""
        ...

    @abstractmethod
    def can_handle(self, query: str, context: Dict[str, Any]) -> bool:
        """Return True if this handler can handle the given query.

        Args:
            query: The user's query string.
            context: Optional context dict with metadata.

        Returns:
            Whether this handler should fire.
        """
        ...

    @abstractmethod
    def handle(
        self, query: str, context: Dict[str, Any],
    ) -> EdgeCaseResult:
        """Process the query and return a result.

        Args:
            query: The user's query string.
            context: Optional context dict with metadata.

        Returns:
            EdgeCaseResult with action and details.
        """
        ...


# ══════════════════════════════════════════════════════════════════
# HELPER UTILITIES
# ══════════════════════════════════════════════════════════════════


def _strip_emojis(text: str) -> str:
    """Remove emoji characters from text.

    Uses Unicode categories So (Symbol, Other) and Sk
    (Modifier, Symbol) to detect emojis.

    Args:
        text: Input string possibly containing emojis.

    Returns:
        String with emojis removed.
    """
    return "".join(
        ch for ch in text
        if unicodedata.category(ch) not in ("So", "Sk")
    )


def _has_only_emojis(text: str) -> bool:
    """Check if text contains only emojis and whitespace.

    Args:
        text: Input string.

    Returns:
        True if removing emojis leaves no alphanumeric chars.
    """
    stripped = _strip_emojis(text)
    return len(stripped.strip()) == 0


def _detect_script(text: str) -> Optional[str]:
    """Detect if text uses a non-Latin script.

    Args:
        text: Input string.

    Returns:
        Script name if non-Latin detected, None if Latin/ASCII.
    """
    for start, end, name in _UNSUPPORTED_RANGES:
        for char in text:
            code_point = ord(char)
            if start <= code_point <= end:
                return name
    return None


def _count_questions(query: str) -> int:
    """Count the number of questions in a query.

    Counts question marks and common question-starting words.

    Args:
        query: Input query string.

    Returns:
        Number of questions detected.
    """
    count = query.count("?")
    question_words = [
        "how", "what", "when", "where", "why", "who",
        "which", "can", "could", "would", "should",
        "is", "are", "do", "does", "did",
    ]
    lower = query.lower()
    for word in question_words:
        pattern = rf"\b{re.escape(word)}\b"
        count += len(re.findall(pattern, lower))
    return count


def _contains_code_blocks(query: str) -> bool:
    """Check if query contains fenced code blocks.

    Args:
        query: Input query string.

    Returns:
        True if ```...``` fences are found.
    """
    return bool(_RE_CODE_FENCE.search(query))


def _has_embedded_images(query: str) -> bool:
    """Check if query references images or attachments.

    Args:
        query: Input query string.

    Returns:
        True if image/attachment markers found.
    """
    markers = ["[image]", "[attachment]", "[file]", "[photo]"]
    lower = query.lower()
    return any(m in lower for m in markers)


# ══════════════════════════════════════════════════════════════════
# CONCRETE HANDLERS (20 total)
# ══════════════════════════════════════════════════════════════════


class EmptyQueryHandler(EdgeCaseHandler):
    """Handle empty or whitespace-only queries.

    Priority 1 — fastest possible rejection.
    """

    @property
    def handler_type(self) -> str:
        return "empty_query"

    @property
    def priority(self) -> int:
        return 1

    def can_handle(self, query: str, context: Dict[str, Any]) -> bool:
        return len(query.strip()) == 0

    def handle(
        self, query: str, context: Dict[str, Any],
    ) -> EdgeCaseResult:
        return EdgeCaseResult(
            handler_type=self.handler_type,
            action=EdgeCaseAction.BLOCK,
            severity=EdgeCaseSeverity.LOW.value,
            reason="Query is empty or whitespace-only",
            metadata={"original_length": len(query)},
        )


class TooLongQueryHandler(EdgeCaseHandler):
    """Truncate queries exceeding MAX_QUERY_LENGTH (10000 chars).

    Priority 2 — prevents downstream token budget issues.
    """

    @property
    def handler_type(self) -> str:
        return "too_long_query"

    @property
    def priority(self) -> int:
        return 2

    def can_handle(self, query: str, context: Dict[str, Any]) -> bool:
        return len(query) > MAX_QUERY_LENGTH

    def handle(
        self, query: str, context: Dict[str, Any],
    ) -> EdgeCaseResult:
        truncated = query[:MAX_QUERY_LENGTH]
        return EdgeCaseResult(
            handler_type=self.handler_type,
            action=EdgeCaseAction.REWRITE,
            severity=EdgeCaseSeverity.MEDIUM.value,
            rewritten_query=truncated,
            reason=(
                f"Query truncated from {len(query)} to "
                f"{MAX_QUERY_LENGTH} characters"
            ),
            metadata={
                "original_length": len(query),
                "truncated_length": len(truncated),
            },
        )


class UnsupportedLanguageHandler(EdgeCaseHandler):
    """Detect non-supported (non-Latin) scripts in query.

    Priority 3 — early rejection of unsupported languages.
    """

    @property
    def handler_type(self) -> str:
        return "unsupported_language"

    @property
    def priority(self) -> int:
        return 3

    def can_handle(self, query: str, context: Dict[str, Any]) -> bool:
        script = _detect_script(query.strip())
        return script is not None

    def handle(
        self, query: str, context: Dict[str, Any],
    ) -> EdgeCaseResult:
        script = _detect_script(query.strip()) or "unknown"
        return EdgeCaseResult(
            handler_type=self.handler_type,
            action=EdgeCaseAction.REDIRECT,
            severity=EdgeCaseSeverity.HIGH.value,
            redirect_target="language_support",
            reason=f"Unsupported language detected: {script}",
            metadata={"detected_script": script},
        )


class EmojisOnlyHandler(EdgeCaseHandler):
    """Block queries that consist solely of emojis.

    Priority 4.
    """

    @property
    def handler_type(self) -> str:
        return "emojis_only"

    @property
    def priority(self) -> int:
        return 4

    def can_handle(self, query: str, context: Dict[str, Any]) -> bool:
        return _has_only_emojis(query)

    def handle(
        self, query: str, context: Dict[str, Any],
    ) -> EdgeCaseResult:
        return EdgeCaseResult(
            handler_type=self.handler_type,
            action=EdgeCaseAction.BLOCK,
            severity=EdgeCaseSeverity.LOW.value,
            reason="Query contains only emojis, no actionable text",
            metadata={"original_length": len(query)},
        )


class CodeBlocksHandler(EdgeCaseHandler):
    """Flag queries containing fenced code blocks.

    Priority 5 — code queries may need specialized routing.
    """

    @property
    def handler_type(self) -> str:
        return "code_blocks"

    @property
    def priority(self) -> int:
        return 5

    def can_handle(self, query: str, context: Dict[str, Any]) -> bool:
        return _contains_code_blocks(query)

    def handle(
        self, query: str, context: Dict[str, Any],
    ) -> EdgeCaseResult:
        blocks = _RE_CODE_FENCE.findall(query)
        return EdgeCaseResult(
            handler_type=self.handler_type,
            action=EdgeCaseAction.PROCEED,
            severity=EdgeCaseSeverity.LOW.value,
            reason=(
                f"Query contains {len(blocks)} code block(s) "
                f"— consider specialized routing"
            ),
            metadata={"code_block_count": len(blocks)},
        )


class DuplicateQueryHandler(EdgeCaseHandler):
    """Detect near-duplicate of recent query in context.

    Priority 6 — uses SequenceMatcher with threshold 0.9.

    Context key: recent_queries (List[str]).
    """

    @property
    def handler_type(self) -> str:
        return "duplicate_query"

    @property
    def priority(self) -> int:
        return 6

    def can_handle(self, query: str, context: Dict[str, Any]) -> bool:
        recent = context.get("recent_queries", [])
        if not isinstance(recent, list) or not recent:
            return False
        for prev in recent:
            if not isinstance(prev, str):
                continue
            ratio = SequenceMatcher(None, query, prev).ratio()
            if ratio > DUPLICATE_SIMILARITY_THRESHOLD:
                return True
        return False

    def handle(
        self, query: str, context: Dict[str, Any],
    ) -> EdgeCaseResult:
        recent = context.get("recent_queries", [])
        best_ratio = 0.0
        for prev in recent:
            if not isinstance(prev, str):
                continue
            ratio = SequenceMatcher(None, query, prev).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
        return EdgeCaseResult(
            handler_type=self.handler_type,
            action=EdgeCaseAction.REWRITE,
            severity=EdgeCaseSeverity.LOW.value,
            rewritten_query=query,
            reason=(
                f"Near-duplicate query detected "
                f"(similarity: {best_ratio:.2f})"
            ),
            metadata={
                "similarity_ratio": round(best_ratio, 4),
                "recent_query_count": len(recent),
            },
        )


class EmbeddedImagesHandler(EdgeCaseHandler):
    """Flag queries referencing images or attachments.

    Priority 7.
    """

    @property
    def handler_type(self) -> str:
        return "embedded_images"

    @property
    def priority(self) -> int:
        return 7

    def can_handle(self, query: str, context: Dict[str, Any]) -> bool:
        return _has_embedded_images(query)

    def handle(
        self, query: str, context: Dict[str, Any],
    ) -> EdgeCaseResult:
        markers_found = []
        for marker in ["[image]", "[attachment]", "[file]", "[photo]"]:
            if marker in query.lower():
                markers_found.append(marker)
        return EdgeCaseResult(
            handler_type=self.handler_type,
            action=EdgeCaseAction.PROCEED,
            severity=EdgeCaseSeverity.LOW.value,
            reason=(
                f"Query references attachments: "
                f"{', '.join(markers_found)}"
            ),
            metadata={"markers_found": markers_found},
        )


class MultiQuestionHandler(EdgeCaseHandler):
    """Flag queries containing multiple questions.

    Priority 8 — triggers at > 3 questions detected.
    """

    @property
    def handler_type(self) -> str:
        return "multi_question"

    @property
    def priority(self) -> int:
        return 8

    def can_handle(self, query: str, context: Dict[str, Any]) -> bool:
        return _count_questions(query) > MULTI_QUESTION_THRESHOLD

    def handle(
        self, query: str, context: Dict[str, Any],
    ) -> EdgeCaseResult:
        count = _count_questions(query)
        return EdgeCaseResult(
            handler_type=self.handler_type,
            action=EdgeCaseAction.PROCEED,
            severity=EdgeCaseSeverity.MEDIUM.value,
            reason=(
                f"Query contains {count} questions "
                f"(threshold: {MULTI_QUESTION_THRESHOLD})"
            ),
            metadata={"question_count": count},
        )


class NonExistentTicketHandler(EdgeCaseHandler):
    """Flag references to tickets that don't exist.

    Priority 9.

    Context keys: referenced_ticket_id (str), ticket_exists (bool).
    If ticket_exists is False, this handler fires.
    """

    @property
    def handler_type(self) -> str:
        return "non_existent_ticket"

    @property
    def priority(self) -> int:
        return 9

    def can_handle(self, query: str, context: Dict[str, Any]) -> bool:
        ticket_id = context.get("referenced_ticket_id")
        if not ticket_id:
            return False
        exists = context.get("ticket_exists", True)
        return exists is False

    def handle(
        self, query: str, context: Dict[str, Any],
    ) -> EdgeCaseResult:
        ticket_id = context.get("referenced_ticket_id", "unknown")
        return EdgeCaseResult(
            handler_type=self.handler_type,
            action=EdgeCaseAction.REWRITE,
            severity=EdgeCaseSeverity.MEDIUM.value,
            rewritten_query=query,
            reason=(
                f"Referenced ticket {ticket_id} does not exist"
            ),
            metadata={"referenced_ticket_id": ticket_id},
        )


class MaliciousHTMLHandler(EdgeCaseHandler):
    """Block HTML/script injection attempts.

    Priority 10 — security-critical, checked early.
    """

    @property
    def handler_type(self) -> str:
        return "malicious_html"

    @property
    def priority(self) -> int:
        return 10

    def can_handle(self, query: str, context: Dict[str, Any]) -> bool:
        return bool(_RE_MALICIOUS_HTML.search(query))

    def handle(
        self, query: str, context: Dict[str, Any],
    ) -> EdgeCaseResult:
        match = _RE_MALICIOUS_HTML.search(query)
        matched_text = match.group(0) if match else "unknown"
        return EdgeCaseResult(
            handler_type=self.handler_type,
            action=EdgeCaseAction.BLOCK,
            severity=EdgeCaseSeverity.CRITICAL.value,
            reason=(
                f"Malicious HTML/script injection detected: "
                f"{matched_text}"
            ),
            metadata={"matched_pattern": matched_text},
        )


class FAQMatchHandler(EdgeCaseHandler):
    """Match exact or near-exact FAQ queries and redirect.

    Priority 11 — offloads known questions from AI pipeline.

    Context key: faq_table (optional override dict).
    """

    @property
    def handler_type(self) -> str:
        return "faq_match"

    @property
    def priority(self) -> int:
        return 11

    def can_handle(self, query: str, context: Dict[str, Any]) -> bool:
        table = context.get("faq_table", _FAQ_TABLE)
        lower = query.strip().lower()
        for faq_key in table:
            if lower == faq_key:
                return True
        return False

    def handle(
        self, query: str, context: Dict[str, Any],
    ) -> EdgeCaseResult:
        table = context.get("faq_table", _FAQ_TABLE)
        lower = query.strip().lower()
        for faq_key, faq_answer in table.items():
            if lower == faq_key:
                return EdgeCaseResult(
                    handler_type=self.handler_type,
                    action=EdgeCaseAction.REDIRECT,
                    severity=EdgeCaseSeverity.LOW.value,
                    redirect_target="faq",
                    reason="Exact FAQ match found",
                    metadata={
                        "matched_faq": faq_key,
                        "faq_answer": faq_answer,
                    },
                )
        return EdgeCaseResult(
            handler_type=self.handler_type,
            action=EdgeCaseAction.PROCEED,
            reason="No FAQ match found",
        )


class BelowConfidenceHandler(EdgeCaseHandler):
    """Flag queries where classification confidence is low.

    Priority 12.

    Context key: confidence_score (float).
    """

    @property
    def handler_type(self) -> str:
        return "below_confidence"

    @property
    def priority(self) -> int:
        return 12

    def can_handle(self, query: str, context: Dict[str, Any]) -> bool:
        score = context.get("confidence_score")
        if score is None:
            return False
        return float(score) < CONFIDENCE_THRESHOLD

    def handle(
        self, query: str, context: Dict[str, Any],
    ) -> EdgeCaseResult:
        score = float(context.get("confidence_score", 0.0))
        return EdgeCaseResult(
            handler_type=self.handler_type,
            action=EdgeCaseAction.ESCALATE,
            severity=EdgeCaseSeverity.HIGH.value,
            reason=(
                f"Classification confidence below threshold: "
                f"{score:.2f} < {CONFIDENCE_THRESHOLD}"
            ),
            metadata={
                "confidence_score": score,
                "threshold": CONFIDENCE_THRESHOLD,
            },
        )


class MaintenanceModeHandler(EdgeCaseHandler):
    """Block queries when system is in maintenance mode.

    Priority 13.

    Context keys: maintenance_mode (bool), system_status (dict).
    """

    @property
    def handler_type(self) -> str:
        return "maintenance_mode"

    @property
    def priority(self) -> int:
        return 13

    def can_handle(self, query: str, context: Dict[str, Any]) -> bool:
        if context.get("maintenance_mode") is True:
            return True
        status = context.get("system_status", {})
        if isinstance(status, dict):
            return status.get("maintenance") is True
        return False

    def handle(
        self, query: str, context: Dict[str, Any],
    ) -> EdgeCaseResult:
        status = context.get("system_status", {})
        message = "System is currently in maintenance mode"
        if isinstance(status, dict):
            message = status.get(
                "maintenance_message", message,
            )
        return EdgeCaseResult(
            handler_type=self.handler_type,
            action=EdgeCaseAction.BLOCK,
            severity=EdgeCaseSeverity.HIGH.value,
            reason=message,
            metadata={"maintenance_mode": True},
        )


class ExpiredContextHandler(EdgeCaseHandler):
    """Flag stale conversation context.

    Priority 14.

    Context key: context_timestamp (ISO 8601 string or datetime).
    """

    @property
    def handler_type(self) -> str:
        return "expired_context"

    @property
    def priority(self) -> int:
        return 14

    def can_handle(self, query: str, context: Dict[str, Any]) -> bool:
        ts = context.get("context_timestamp")
        if ts is None:
            return False
        try:
            if isinstance(ts, str):
                ts = datetime.fromisoformat(ts)
            now = datetime.now(timezone.utc)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            delta = (now - ts).total_seconds()
            return delta > (CONTEXT_EXPIRY_MINUTES * 60)
        except (ValueError, TypeError, AttributeError):
            return False

    def handle(
        self, query: str, context: Dict[str, Any],
    ) -> EdgeCaseResult:
        ts = context.get("context_timestamp", "")
        return EdgeCaseResult(
            handler_type=self.handler_type,
            action=EdgeCaseAction.REWRITE,
            severity=EdgeCaseSeverity.MEDIUM.value,
            rewritten_query=query,
            reason=(
                f"Conversation context expired "
                f"(older than {CONTEXT_EXPIRY_MINUTES} minutes)"
            ),
            metadata={
                "context_timestamp": str(ts),
                "expiry_minutes": CONTEXT_EXPIRY_MINUTES,
            },
        )


class BlockedUserHandler(EdgeCaseHandler):
    """Block queries from blocked/suspended users.

    Priority 15 — security-critical.

    Context keys: user_status (str), is_blocked (bool).
    """

    @property
    def handler_type(self) -> str:
        return "blocked_user"

    @property
    def priority(self) -> int:
        return 15

    def can_handle(self, query: str, context: Dict[str, Any]) -> bool:
        if context.get("is_blocked") is True:
            return True
        status = context.get("user_status", "")
        return str(status).lower() in (
            "blocked", "suspended", "banned",
        )

    def handle(
        self, query: str, context: Dict[str, Any],
    ) -> EdgeCaseResult:
        status = context.get("user_status", "blocked")
        return EdgeCaseResult(
            handler_type=self.handler_type,
            action=EdgeCaseAction.BLOCK,
            severity=EdgeCaseSeverity.CRITICAL.value,
            reason=f"User is blocked/suspended: {status}",
            metadata={"user_status": status},
        )


class PricingRequestHandler(EdgeCaseHandler):
    """Redirect pricing/billing queries to specialized handler.

    Priority 16.
    """

    @property
    def handler_type(self) -> str:
        return "pricing_request"

    @property
    def priority(self) -> int:
        return 16

    def can_handle(self, query: str, context: Dict[str, Any]) -> bool:
        lower = query.lower()
        return any(
            kw in lower for kw in _PRICING_KEYWORDS
        )

    def handle(
        self, query: str, context: Dict[str, Any],
    ) -> EdgeCaseResult:
        matched = []
        lower = query.lower()
        for kw in _PRICING_KEYWORDS:
            if kw in lower:
                matched.append(kw)
        return EdgeCaseResult(
            handler_type=self.handler_type,
            action=EdgeCaseAction.REDIRECT,
            severity=EdgeCaseSeverity.LOW.value,
            redirect_target="billing_support",
            reason="Pricing/billing query detected",
            metadata={"matched_keywords": matched},
        )


class LegalTerminologyHandler(EdgeCaseHandler):
    """Flag legal terms requiring special handling.

    Priority 17.
    """

    @property
    def handler_type(self) -> str:
        return "legal_terminology"

    @property
    def priority(self) -> int:
        return 17

    def can_handle(self, query: str, context: Dict[str, Any]) -> bool:
        lower = query.lower()
        return any(
            kw in lower for kw in _LEGAL_KEYWORDS
        )

    def handle(
        self, query: str, context: Dict[str, Any],
    ) -> EdgeCaseResult:
        matched = []
        lower = query.lower()
        for kw in _LEGAL_KEYWORDS:
            if kw in lower:
                matched.append(kw)
        return EdgeCaseResult(
            handler_type=self.handler_type,
            action=EdgeCaseAction.ESCALATE,
            severity=EdgeCaseSeverity.HIGH.value,
            reason=(
                f"Legal terminology detected: "
                f"{', '.join(matched)}"
            ),
            metadata={"matched_keywords": matched},
        )


class CompetitorMentionHandler(EdgeCaseHandler):
    """Flag mentions of competitor products.

    Priority 18.

    Context key: competitors (optional set to override defaults).
    """

    @property
    def handler_type(self) -> str:
        return "competitor_mention"

    @property
    def priority(self) -> int:
        return 18

    def can_handle(self, query: str, context: Dict[str, Any]) -> bool:
        competitors = context.get(
            "competitors", DEFAULT_COMPETITORS,
        )
        if not isinstance(competitors, (list, set)):
            competitors = DEFAULT_COMPETITORS
        lower = query.lower()
        return any(c in lower for c in competitors)

    def handle(
        self, query: str, context: Dict[str, Any],
    ) -> EdgeCaseResult:
        competitors = context.get(
            "competitors", DEFAULT_COMPETITORS,
        )
        if not isinstance(competitors, (list, set)):
            competitors = DEFAULT_COMPETITORS
        matched = [
            c for c in competitors if c in query.lower()
        ]
        return EdgeCaseResult(
            handler_type=self.handler_type,
            action=EdgeCaseAction.PROCEED,
            severity=EdgeCaseSeverity.LOW.value,
            reason=(
                f"Competitor mention detected: "
                f"{', '.join(matched)}"
            ),
            metadata={
                "competitors_mentioned": matched,
                "competitor_list": list(DEFAULT_COMPETITORS),
            },
        )


class SystemCommandsHandler(EdgeCaseHandler):
    """Block attempts to issue system commands via chat.

    Priority 19 — security-critical.
    """

    @property
    def handler_type(self) -> str:
        return "system_commands"

    @property
    def priority(self) -> int:
        return 19

    def can_handle(self, query: str, context: Dict[str, Any]) -> bool:
        return bool(_RE_SYSTEM_COMMANDS.search(query))

    def handle(
        self, query: str, context: Dict[str, Any],
    ) -> EdgeCaseResult:
        match = _RE_SYSTEM_COMMANDS.search(query)
        matched_text = match.group(0) if match else "unknown"
        return EdgeCaseResult(
            handler_type=self.handler_type,
            action=EdgeCaseAction.BLOCK,
            severity=EdgeCaseSeverity.CRITICAL.value,
            reason=(
                f"System command attempt detected: "
                f"{matched_text}"
            ),
            metadata={"matched_pattern": matched_text},
        )


class TimeoutHandler(EdgeCaseHandler):
    """Processing timeout handler — wraps chain execution.

    Priority 20 — always runs last as a safety net.

    Context key: _processing_elapsed_ms (set by registry).
    """

    @property
    def handler_type(self) -> str:
        return "timeout"

    @property
    def priority(self) -> int:
        return 20

    def can_handle(self, query: str, context: Dict[str, Any]) -> bool:
        elapsed = context.get("_processing_elapsed_ms", 0)
        return elapsed > (CHAIN_TIMEOUT_SECONDS * 1000)

    def handle(
        self, query: str, context: Dict[str, Any],
    ) -> EdgeCaseResult:
        elapsed = context.get("_processing_elapsed_ms", 0)
        return EdgeCaseResult(
            handler_type=self.handler_type,
            action=EdgeCaseAction.ESCALATE,
            severity=EdgeCaseSeverity.HIGH.value,
            reason=(
                f"Edge-case handler chain exceeded timeout: "
                f"{elapsed:.0f}ms > "
                f"{CHAIN_TIMEOUT_SECONDS * 1000:.0f}ms"
            ),
            metadata={
                "elapsed_ms": elapsed,
                "timeout_ms": CHAIN_TIMEOUT_SECONDS * 1000,
            },
        )


# ══════════════════════════════════════════════════════════════════
# REGISTRY
# ══════════════════════════════════════════════════════════════════


class EdgeCaseRegistry:
    """Central registry that runs the full handler chain.

    Handlers are sorted by priority (lower number = runs first).
    Stops immediately on any BLOCK action.
    Collects all REWRITE suggestions (last rewrite wins).
    Supports variant-specific handler whitelists (GAP-023).

    Usage:
        registry = EdgeCaseRegistry(variant="parwa")
        result = registry.process(
            "Hello", context={"company_id": "acme"},
        )
    """

    def __init__(
        self,
        variant: str = "parwa",
        extra_handlers: Optional[List[EdgeCaseHandler]] = None,
    ) -> None:
        """Initialize registry and register all handlers.

        Args:
            variant: PARWA variant (mini_parwa, parwa, parwa_high).
            extra_handlers: Additional custom handlers to include.
        """
        self._variant = variant
        self._handlers: List[EdgeCaseHandler] = []
        self._handler_map: Dict[str, EdgeCaseHandler] = {}

        # Register built-in handlers
        built_in = [
            EmptyQueryHandler(),
            TooLongQueryHandler(),
            UnsupportedLanguageHandler(),
            EmojisOnlyHandler(),
            CodeBlocksHandler(),
            DuplicateQueryHandler(),
            EmbeddedImagesHandler(),
            MultiQuestionHandler(),
            NonExistentTicketHandler(),
            MaliciousHTMLHandler(),
            FAQMatchHandler(),
            BelowConfidenceHandler(),
            MaintenanceModeHandler(),
            ExpiredContextHandler(),
            BlockedUserHandler(),
            PricingRequestHandler(),
            LegalTerminologyHandler(),
            CompetitorMentionHandler(),
            SystemCommandsHandler(),
            TimeoutHandler(),
        ]

        for handler in built_in:
            self.register(handler)

        if extra_handlers:
            for handler in extra_handlers:
                self.register(handler)

        # Apply variant whitelist (GAP-023)
        whitelist = VARIANT_HANDLER_WHITELIST.get(variant)
        if whitelist is not None:
            self._handlers = [
                h for h in self._handlers
                if h.handler_type in whitelist
            ]

        # Sort by priority
        self._handlers.sort(key=lambda h: h.priority)

        logger.info(
            "edge_case_registry_initialized",
            extra={
                "variant": variant,
                "handler_count": len(self._handlers),
                "handler_types": [
                    h.handler_type for h in self._handlers
                ],
            },
        )

    def register(self, handler: EdgeCaseHandler) -> None:
        """Register a handler, replacing any with the same type.

        Args:
            handler: An EdgeCaseHandler instance.
        """
        if handler.handler_type in self._handler_map:
            existing = self._handler_map[handler.handler_type]
            self._handlers = [
                h for h in self._handlers
                if h is not existing
            ]
        self._handler_map[handler.handler_type] = handler
        self._handlers.append(handler)

    def get_handler(
        self, handler_type: str,
    ) -> Optional[EdgeCaseHandler]:
        """Look up a handler by type string.

        Args:
            handler_type: The handler_type to look up.

        Returns:
            Handler instance or None.
        """
        return self._handler_map.get(handler_type)

    def process(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> EdgeCaseProcessingResult:
        """Run the full handler chain on a query.

        Stops on first BLOCK action. Collects all REWRITE
        suggestions (last rewrite wins for final_query).
        Enforces per-handler timeout (GAP-022).

        Args:
            query: The user's query string.
            context: Optional context dict with metadata.

        Returns:
            EdgeCaseProcessingResult with aggregated outcome.
        """
        if context is None:
            context = {}

        chain_start = time.monotonic()
        results: List[EdgeCaseResult] = []
        triggered: List[str] = []
        current_query = query
        rewritten = False
        blocked = False
        final_action = EdgeCaseAction.PROCEED

        for handler in self._handlers:
            # GAP-022: Check chain timeout
            elapsed_ms = (time.monotonic() - chain_start) * 1000
            if elapsed_ms > (CHAIN_TIMEOUT_SECONDS * 1000):
                logger.warning(
                    "edge_case_chain_timeout",
                    extra={
                        "variant": self._variant,
                        "elapsed_ms": round(elapsed_ms, 1),
                        "timeout_ms": CHAIN_TIMEOUT_SECONDS * 1000,
                    },
                )
                break

            try:
                # GAP-022: Per-handler timeout wrapper
                result = self._run_with_timeout(
                    handler, current_query, context,
                )
            except Exception:
                logger.warning(
                    "edge_case_handler_error",
                    extra={
                        "handler_type": handler.handler_type,
                        "variant": self._variant,
                    },
                )
                continue

            if result is None:
                continue

            results.append(result)
            triggered.append(result.handler_type)

            # Apply rewrite if action is REWRITE
            if (
                result.action == EdgeCaseAction.REWRITE
                and result.rewritten_query is not None
            ):
                current_query = result.rewritten_query
                rewritten = True

            # Stop on BLOCK
            if result.action == EdgeCaseAction.BLOCK:
                blocked = True
                final_action = EdgeCaseAction.BLOCK
                logger.info(
                    "edge_case_blocked",
                    extra={
                        "handler_type": result.handler_type,
                        "reason": result.reason,
                        "severity": result.severity,
                        "company_id": context.get("company_id"),
                    },
                )
                break

            # Track escalation as higher priority
            if result.action == EdgeCaseAction.ESCALATE:
                if final_action != EdgeCaseAction.BLOCK:
                    final_action = EdgeCaseAction.ESCALATE

            # Track redirect as higher priority than proceed
            if result.action == EdgeCaseAction.REDIRECT:
                if final_action == EdgeCaseAction.PROCEED:
                    final_action = EdgeCaseAction.REDIRECT

        total_ms = (time.monotonic() - chain_start) * 1000

        if not results:
            final_action = EdgeCaseAction.PROCEED

        return EdgeCaseProcessingResult(
            final_action=final_action,
            final_query=current_query,
            handlers_triggered=triggered,
            blocked=blocked,
            rewritten=rewritten,
            processing_time_ms=round(total_ms, 2),
            results=results,
        )

    @staticmethod
    def _run_with_timeout(
        handler: EdgeCaseHandler,
        query: str,
        context: Dict[str, Any],
    ) -> Optional[EdgeCaseResult]:
        """Run a single handler with timeout enforcement.

        Since we cannot easily interrupt sync Python code in a
        cross-platform way without threads, we use a time check
        around can_handle + handle as a cooperative timeout.
        For true async timeout, the caller should wrap process().

        GAP-022: 2s per handler.

        Args:
            handler: The handler to run.
            query: The query string.
            context: Context dict.

        Returns:
            EdgeCaseResult or None if skipped/timed out.
        """
        handler_start = time.monotonic()

        if not handler.can_handle(query, context):
            return None

        elapsed = time.monotonic() - handler_start
        if elapsed > HANDLER_TIMEOUT_SECONDS:
            logger.warning(
                "edge_case_handler_can_handle_timeout",
                extra={
                    "handler_type": handler.handler_type,
                    "elapsed_ms": round(elapsed * 1000, 1),
                },
            )
            return None

        result = handler.handle(query, context)

        total_elapsed = time.monotonic() - handler_start
        if total_elapsed > HANDLER_TIMEOUT_SECONDS:
            logger.warning(
                "edge_case_handler_slow",
                extra={
                    "handler_type": handler.handler_type,
                    "elapsed_ms": round(total_elapsed * 1000, 1),
                    "timeout_ms": HANDLER_TIMEOUT_SECONDS * 1000,
                },
            )

        return result
