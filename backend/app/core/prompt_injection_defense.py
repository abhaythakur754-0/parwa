"""
SG-36: Tenant-Specific Prompt Injection Defense (BC-011, BC-007, BC-010)

Multi-layer prompt injection detection and defense system.
Logs every attempt per tenant. Builds per-tenant blocklists.
Escalates repeated attempts (3+ in 1 hour → alert).

Detection Methods:
1. Pattern matching — known injection signatures
2. Anomaly scoring — unusual query characteristics
3. Rate limiting — frequency of suspicious queries per tenant/user
4. Tenant blocklist — per-tenant custom block patterns

BC-001: All operations scoped by company_id.
BC-010: Injection logs retained per GDPR policy.
BC-011: Security — first line of defense against prompt attacks.
BC-012: Never crashes — fail-open with logging on Redis/DB failure.
"""

from __future__ import annotations

import base64
import hashlib
import json
import math
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from app.logger import get_logger

logger = get_logger("prompt_injection_defense")


# ── Data Classes ────────────────────────────────────────────────────


@dataclass
class InjectionMatch:
    """Describes a single detected injection pattern."""

    pattern_type: str
    severity: str
    confidence: float
    matched_text: str
    rule_id: str
    description: str


@dataclass
class InjectionScanResult:
    """Full result from a prompt injection scan."""

    is_injection: bool
    matches: List[InjectionMatch]
    action: str
    reason: str
    query_hash: str


# ── Compiled Detection Patterns ─────────────────────────────────────
# All regex patterns compiled at module level for performance.


# ── Category 1: Command Injection ──
_COMMAND_INJECTION_RULES: List[Dict[str, Any]] = [
    {
        "pattern": re.compile(
            r"\bignore\s+(?:all\s+(?:previous|prior|above|earlier)\s+"
            r"|(?:previous|prior|above|earlier)\s+|all\s+)"
            r"(instructions?|prompts?|directives?|rules?|messages?)\b",
            re.IGNORECASE,
        ),
        "rule_id": "CMD-001",
        "severity": "high",
        "confidence": 0.95,
        "description": "Instructs model to ignore prior instructions",
    },
    {
        "pattern": re.compile(
            r"\bforget\s+(everything|all|all of)\s+(above|before|previous|prior)\b",
            re.IGNORECASE,
        ),
        "rule_id": "CMD-002",
        "severity": "high",
        "confidence": 0.95,
        "description": "Attempts to reset model context",
    },
    {
        "pattern": re.compile(
            r"\byou\s+are\s+now\b",
            re.IGNORECASE,
        ),
        "rule_id": "CMD-003",
        "severity": "high",
        "confidence": 0.90,
        "description": "Role hijacking via 'you are now' directive",
    },
    {
        "pattern": re.compile(
            r"\b(pretend|act|roleplay|imagine)\s+(you\s+are|as\s+if|as)\b",
            re.IGNORECASE,
        ),
        "rule_id": "CMD-004",
        "severity": "medium",
        "confidence": 0.80,
        "description": "Role-switching attempt via pretend/act directive",
    },
    {
        "pattern": re.compile(
            r"\bsystem\s+prompt\b",
            re.IGNORECASE,
        ),
        "rule_id": "CMD-005",
        "severity": "critical",
        "confidence": 0.98,
        "description": "Direct reference to system prompt — likely extraction attempt",
    },
    {
        "pattern": re.compile(
            r"\b(your\s+instructions?|your\s+role|your\s+rules?)\s+(are|is|says?)\b",
            re.IGNORECASE,
        ),
        "rule_id": "CMD-006",
        "severity": "high",
        "confidence": 0.88,
        "description": "Probing for system instructions",
    },
    {
        "pattern": re.compile(
            r"\bdeveloper\s+mode\b",
            re.IGNORECASE,
        ),
        "rule_id": "CMD-007",
        "severity": "high",
        "confidence": 0.90,
        "description": "Developer mode escalation attempt",
    },
    {
        "pattern": re.compile(
            r"\bdisregard\s+(your|the|all|any|these|those)?\s*"
            r"(training|instructions?|rules?|guidelines?|directives?|"
            r"restrictions?|limitations?|safety|guardrails?)\b",
            re.IGNORECASE,
        ),
        "rule_id": "CMD-008",
        "severity": "high",
        "confidence": 0.92,
        "description": "Attempts to disregard training or safety constraints",
    },
]

# ── Category 2: Context Manipulation ──
_CONTEXT_MANIPULATION_RULES: List[Dict[str, Any]] = [
    {
        "pattern": re.compile(
            r"\bnew\s+context\s*:",
            re.IGNORECASE,
        ),
        "rule_id": "CTX-001",
        "severity": "high",
        "confidence": 0.92,
        "description": "Attempts to inject new context block",
    },
    {
        "pattern": re.compile(
            r"\b(updated|new|revised|changed)\s+instructions?\s*:",
            re.IGNORECASE,
        ),
        "rule_id": "CTX-002",
        "severity": "high",
        "confidence": 0.90,
        "description": "Attempts to override instructions",
    },
    {
        "pattern": re.compile(
            r"\boverride\s*:",
            re.IGNORECASE,
        ),
        "rule_id": "CTX-003",
        "severity": "high",
        "confidence": 0.93,
        "description": "Explicit override directive",
    },
    {
        "pattern": re.compile(
            r"[<\u27e8]assistant[>\u27e9}]|[<\u27e8]/assistant[>\u27e9}]|"
            r"\|assistant\||<\|assistant\|>",
            re.IGNORECASE,
        ),
        "rule_id": "CTX-004",
        "severity": "critical",
        "confidence": 0.99,
        "description": "LLM chat format injection marker",
    },
    {
        "pattern": re.compile(
            r"[<\u27e8]system[>\u27e9}]",
            re.IGNORECASE,
        ),
        "rule_id": "CTX-005",
        "severity": "critical",
        "confidence": 0.99,
        "description": "LLM system message format injection",
    },
    {
        "pattern": re.compile(
            r"\[INST\].*?\[/INST\]",
            re.DOTALL | re.IGNORECASE,
        ),
        "rule_id": "CTX-006",
        "severity": "critical",
        "confidence": 0.99,
        "description": "Llama instruction format injection",
    },
    {
        "pattern": re.compile(
            r"\|\|.*?(SYSTEM|HUMAN|ASSISTANT).*?\|\|",
            re.IGNORECASE,
        ),
        "rule_id": "CTX-007",
        "severity": "critical",
        "confidence": 0.97,
        "description": "ChatML-style message format injection",
    },
    {
        "pattern": re.compile(
            r"\bnew\s+rules?\s*:",
            re.IGNORECASE,
        ),
        "rule_id": "CTX-008",
        "severity": "high",
        "confidence": 0.90,
        "description": "Attempts to inject new rules directive",
    },
]

# ── Category 3: Data Extraction ──
_DATA_EXTRACTION_RULES: List[Dict[str, Any]] = [
    {
        "pattern": re.compile(
            r"\b(repeat|show|print|output|reveal|display|dump|echo)\s+"
            r"(?:(?:me|us|them|it)\s+)?"
            r"(?:your|the|all)\s+"
            r"(?:(?:full|entire|complete|exact)\s+)?"
            r"(?:system\s+)?(instructions?|prompt|rules?|directives?|guidelines?)\b",
            re.IGNORECASE,
        ),
        "rule_id": "EXT-001",
        "severity": "critical",
        "confidence": 0.95,
        "description": "Direct prompt extraction request",
    },
    {
        "pattern": re.compile(
            r"\bwhat\s+are\s+your\s+(instructions?|rules?|guidelines?)\b",
            re.IGNORECASE,
        ),
        "rule_id": "EXT-002",
        "severity": "high",
        "confidence": 0.88,
        "description": "Probing for system instructions",
    },
    {
        "pattern": re.compile(
            r"\breveal\s+your\s+(prompt|instructions?|system)\b",
            re.IGNORECASE,
        ),
        "rule_id": "EXT-003",
        "severity": "critical",
        "confidence": 0.96,
        "description": "Direct prompt revelation request",
    },
    {
        "pattern": re.compile(
            r"\bdisplay\s+(the\s+)?(full|entire|complete)\s+(prompt|text|message)\b",
            re.IGNORECASE,
        ),
        "rule_id": "EXT-004",
        "severity": "high",
        "confidence": 0.90,
        "description": "Full prompt display request",
    },
    {
        "pattern": re.compile(
            r"\bdump\s+your\s+(prompt|memory|knowledge|context)\b",
            re.IGNORECASE,
        ),
        "rule_id": "EXT-005",
        "severity": "critical",
        "confidence": 0.95,
        "description": "Memory/context dump request",
    },
    {
        "pattern": re.compile(
            r"\bwhat\s+(instructions?|rules?|guidelines?|directives?)\s+"
            r"(?:have\s+you\s+been\s+given|were\s+you\s+given|"
            r"are\s+you\s+following|do\s+you\s+have|"
            r"were\s+you\s+told|have\s+you\s+received)\b",
            re.IGNORECASE,
        ),
        "rule_id": "EXT-006",
        "severity": "high",
        "confidence": 0.85,
        "description": "Probing for given/received instructions",
    },
]

# ── Category 4: Privilege Escalation ──
_PRIVILEGE_ESCALATION_RULES: List[Dict[str, Any]] = [
    {
        "pattern": re.compile(
            r"\badmin\s+mode\b",
            re.IGNORECASE,
        ),
        "rule_id": "PRV-001",
        "severity": "high",
        "confidence": 0.92,
        "description": "Admin mode escalation attempt",
    },
    {
        "pattern": re.compile(
            r"\b(sudo|root\s+access|elevated\s+privileges?)\b",
            re.IGNORECASE,
        ),
        "rule_id": "PRV-002",
        "severity": "high",
        "confidence": 0.90,
        "description": "Unix-style privilege escalation language",
    },
    {
        "pattern": re.compile(
            r"\b(unlock|bypass|override|disable)\s+"
            r"(?:(?:all|the|these|those|your)\s+)?"
            r"(safety|security|guardrails?|"
            r"restrictions?|filters?|protections?)\b",
            re.IGNORECASE,
        ),
        "rule_id": "PRV-003",
        "severity": "critical",
        "confidence": 0.95,
        "description": "Safety mechanism bypass attempt",
    },
    {
        "pattern": re.compile(
            r"\bdisable\s+(your|the|all|safety|security|guardrails?)\b",
            re.IGNORECASE,
        ),
        "rule_id": "PRV-004",
        "severity": "critical",
        "confidence": 0.96,
        "description": "Disable safety mechanism request",
    },
    {
        "pattern": re.compile(
            r"\byou\s+are\s+now\s+a\s+superuser\b",
            re.IGNORECASE,
        ),
        "rule_id": "PRV-005",
        "severity": "critical",
        "confidence": 0.97,
        "description": "Superuser privilege claim",
    },
    {
        "pattern": re.compile(
            r"\bgod\s+mode\b",
            re.IGNORECASE,
        ),
        "rule_id": "PRV-006",
        "severity": "high",
        "confidence": 0.90,
        "description": "God mode escalation attempt",
    },
]

# ── Category 5: Jailbreaking ──
_JAILBREAK_RULES: List[Dict[str, Any]] = [
    {
        "pattern": re.compile(
            r"\bDAN\s+mode\b",
            re.IGNORECASE,
        ),
        "rule_id": "JBR-001",
        "severity": "critical",
        "confidence": 0.98,
        "description": "DAN (Do Anything Now) jailbreak attempt",
    },
    {
        "pattern": re.compile(
            r"\bdo\s+anything\s+now\b",
            re.IGNORECASE,
        ),
        "rule_id": "JBR-002",
        "severity": "high",
        "confidence": 0.92,
        "description": "Do Anything Now jailbreak phrase",
    },
    {
        "pattern": re.compile(
            r"\bno\s+(limitations?|restrictions?|limits?|rules?|bounds?)\b",
            re.IGNORECASE,
        ),
        "rule_id": "JBR-003",
        "severity": "medium",
        "confidence": 0.75,
        "description": "Remove restrictions request",
    },
    {
        "pattern": re.compile(
            r"\bin\s+a\s+hypothetical\s+(scenario|situation|case|world)\b",
            re.IGNORECASE,
        ),
        "rule_id": "JBR-004",
        "severity": "medium",
        "confidence": 0.70,
        "description": "Hypothetical scenario bypass framing",
    },
    {
        "pattern": re.compile(
            r"\bfor\s+(educational|research|academic|testing)\s+purposes?\b",
            re.IGNORECASE,
        ),
        "rule_id": "JBR-005",
        "severity": "low",
        "confidence": 0.55,
        "description": "Educational/research framing for bypass",
    },
    {
        "pattern": re.compile(
            r"\bas\s+an?\s+AI\s+(without|with\s+no)\s+(restrictions?|"
            r"limitations?|filters?|rules?)\b",
            re.IGNORECASE,
        ),
        "rule_id": "JBR-006",
        "severity": "high",
        "confidence": 0.90,
        "description": "AI without restrictions jailbreak",
    },
    {
        "pattern": re.compile(
            r"\bbypass\s+all\s+filters?\b",
            re.IGNORECASE,
        ),
        "rule_id": "JBR-007",
        "severity": "critical",
        "confidence": 0.96,
        "description": "Direct filter bypass attempt",
    },
]

# ── Category 6: Encoding Tricks ──
_ENCODING_TRICK_RULES: List[Dict[str, Any]] = [
    {
        "pattern": re.compile(
            r"(?:^|\s)[A-Za-z0-9+/]{20,}={0,2}(?:\s|$)",
        ),
        "rule_id": "ENC-001",
        "severity": "high",
        "confidence": 0.85,
        "description": "Suspicious Base64-encoded content (20+ chars)",
    },
    {
        "pattern": re.compile(
            r"[\u0400-\u04ff]",
        ),
        "rule_id": "ENC-002",
        "severity": "medium",
        "confidence": 0.70,
        "description": "Cyrillic characters — possible Unicode homoglyph attack",
    },
    {
        "pattern": re.compile(
            r"[\u200b\u200c\u200d\u200e\u200f\ufeff\u2060\u2061\u2062"
            r"\u2063\u2064]",
        ),
        "rule_id": "ENC-003",
        "severity": "medium",
        "confidence": 0.80,
        "description": "Zero-width / invisible Unicode characters detected",
    },
    {
        "pattern": re.compile(
            r"(.)\1{10,}",
        ),
        "rule_id": "ENC-004",
        "severity": "low",
        "confidence": 0.60,
        "description": "Excessive repeated characters (11+ same in a row)",
    },
    {
        "pattern": re.compile(
            r"[\u202a\u202b\u202c\u202d\u202e]"
        ),
        "rule_id": "ENC-005",
        "severity": "high",
        "confidence": 0.85,
        "description": "Bidirectional text override characters (RTL/LTR) detected",
    },
    {
        "pattern": re.compile(
            r"%[0-9a-fA-F]{2}(?:[^%]*%[0-9a-fA-F]{2}){2,}"
        ),
        "rule_id": "ENC-006",
        "severity": "high",
        "confidence": 0.80,
        "description": "URL-encoded payload detected (3+ percent-encoded bytes in query)",
    },
    {
        "pattern": re.compile(
            r"(?:^|\s)(?:\\x[0-9a-fA-F]{2}){3,}"
        ),
        "rule_id": "ENC-007",
        "severity": "high",
        "confidence": 0.80,
        "description": "Hex-escaped payload detected (3+ consecutive \\xNN sequences)",
    },
]

# ── Category 7: Multi-turn Manipulation ──
_MULTI_TURN_RULES: List[Dict[str, Any]] = [
    {
        "pattern": re.compile(
            r"\bin\s+our\s+(previous|earlier|last|prior)\s+(conversation|"
            r"chat|discussion|talk|exchange)\b",
            re.IGNORECASE,
        ),
        "rule_id": "MTR-001",
        "severity": "medium",
        "confidence": 0.65,
        "description": "References previous conversation context",
    },
    {
        "pattern": re.compile(
            r"\bcontinu(e|ing)\s+from\s+where\s+we\s+(left\s+off|stopped|ended)\b",
            re.IGNORECASE,
        ),
        "rule_id": "MTR-002",
        "severity": "medium",
        "confidence": 0.65,
        "description": "Continuation hijack attempt",
    },
    {
        "pattern": re.compile(
            r"\b(as\s+a\s+different|switch\s+to|change\s+your|new\s+role|"
            r"stop\s+being)\s+(a\s+)?(different\s+)?(new\s+)?"
            r"(persona?|role|character|identity)\b",
            re.IGNORECASE,
        ),
        "rule_id": "MTR-003",
        "severity": "high",
        "confidence": 0.85,
        "description": "Mid-conversation role-switching attempt",
    },
]

# Consolidated rule list for fast iteration
_ALL_RULES: List[Dict[str, Any]] = (
    _COMMAND_INJECTION_RULES
    + _CONTEXT_MANIPULATION_RULES
    + _DATA_EXTRACTION_RULES
    + _PRIVILEGE_ESCALATION_RULES
    + _JAILBREAK_RULES
    + _ENCODING_TRICK_RULES
    + _MULTI_TURN_RULES
)

# Anomaly detection thresholds
_ANOMALY_QUERY_LENGTH_THRESHOLD = 2000
_ANOMALY_SPECIAL_CHAR_RATIO = 0.4
_ANOMALY_UPPERCASE_RATIO = 0.6
_ANOMALY_ENTROPY_THRESHOLD = 4.2

# Rate limiting thresholds
_RATE_LIMIT_WINDOW_SECONDS = 3600  # 1 hour
_RATE_LIMIT_ESCALATE_THRESHOLD = 3
_RATE_LIMIT_BLOCK_THRESHOLD = 5

# Redis key patterns for tenant-scoped rate limiting
# Uses the parwa:injection_rate:{company_id}:{user_id} pattern per BC-001
_REDIS_RATE_LIMIT_KEY_TEMPLATE = "parwa:{company_id}:injection_rate:{user_id}"
_REDIS_TENANT_BLOCKLIST_KEY_TEMPLATE = "parwa:{company_id}:tenant_blocklist"


# ── Utility Functions ───────────────────────────────────────────────


def hash_query(query: str) -> str:
    """SHA-256 hash of the query for deduplication.

    Normalizes whitespace before hashing so trivially different
    spacing does not create separate entries.

    Args:
        query: Raw query string.

    Returns:
        Hex-encoded SHA-256 digest.
    """
    normalized = " ".join(query.split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def sanitize_query(query: str) -> str:
    """Strip zero-width chars, normalize unicode, collapse whitespace.

    Args:
        query: Raw query string.

    Returns:
        Sanitized query string.
    """
    # Remove zero-width and invisible characters
    invisible_chars = (
        "\u200b\u200c\u200d\u200e\u200f"
        "\ufeff\u2060\u2061\u2062\u2063\u2064"
        "\u202a\u202b\u202c\u202d\u202e"
    )
    cleaned = "".join(c for c in query if c not in invisible_chars)

    # Normalize unicode (NFKC decomposes compatibility characters)
    cleaned = unicodedata.normalize("NFKC", cleaned)

    # Collapse whitespace
    cleaned = " ".join(cleaned.split())

    return cleaned.strip()


def get_severity_weights() -> Dict[str, float]:
    """Return severity → weight mapping for scoring.

    Higher weight = more dangerous.

    Returns:
        Dict mapping severity level to numeric weight.
    """
    return {
        "low": 1.0,
        "medium": 3.0,
        "high": 7.0,
        "critical": 10.0,
    }


def _shannon_entropy(text: str) -> float:
    """Calculate Shannon entropy of a string.

    High entropy suggests encoded or random content.

    Args:
        text: Input string.

    Returns:
        Entropy value (0 = no randomness, higher = more random).
    """
    if not text:
        return 0.0
    length = len(text)
    counts = Counter(text)
    entropy = 0.0
    for count in counts.values():
        probability = count / length
        if probability > 0:
            entropy -= probability * math.log2(probability)
    return entropy


def _truncate_preview(query: str, max_length: int = 500) -> str:
    """Truncate query for safe storage in database.

    Args:
        query: Raw query string.
        max_length: Maximum preview length.

    Returns:
        Truncated string with ellipsis if needed.
    """
    if len(query) <= max_length:
        return query
    return query[: max_length - 3] + "..."


def _classify_pattern_type(rule_id: str) -> str:
    """Map rule_id prefix to human-readable pattern type.

    Args:
        rule_id: Rule identifier (e.g. 'CMD-001').

    Returns:
        Human-readable pattern type string.
    """
    prefix_map: Dict[str, str] = {
        "CMD": "command_injection",
        "CTX": "context_manipulation",
        "EXT": "data_extraction",
        "PRV": "privilege_escalation",
        "JBR": "jailbreak",
        "ENC": "encoding_trick",
        "MTR": "multi_turn",
        "RATE": "rate_limit",
        "TBLK": "tenant_blocklist",
        "ANOM": "anomaly",
    }
    prefix = rule_id.split("-")[0] if "-" in rule_id else rule_id
    return prefix_map.get(prefix, "unknown")


# ── Prompt Injection Detector ───────────────────────────────────────


class PromptInjectionDetector:
    """Multi-layer prompt injection detector.

    Runs all detection layers in sequence:
    1. Known pattern matching (regex)
    2. Anomaly scoring (statistical heuristics)
    3. Rate limiting (Redis-based, async-safe wrapper)
    4. Tenant blocklist (Redis-based, async-safe wrapper)

    Pure CPU-bound detection — no async calls inside this class.
    Rate limiting and tenant blocklist accept pre-fetched Redis data
    so the caller can decide sync vs async.

    BC-001: Every scan requires company_id.
    BC-008: Never crashes — returns safe defaults on error.
    """

    def scan(
        self,
        query: str,
        company_id: str,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        *,
        rate_limit_count: Optional[int] = None,
        tenant_blocklist_patterns: Optional[List[str]] = None,
    ) -> InjectionScanResult:
        """Run all detection layers on a query.

        Args:
            query: The user query to scan.
            company_id: Tenant identifier (BC-001).
            user_id: Optional user identifier for rate limiting.
            ip_address: Optional IP address for logging.
            rate_limit_count: Pre-fetched rate limit count from Redis.
                If None, rate limit check is skipped (safe default).
            tenant_blocklist_patterns: Pre-fetched tenant blocklist
                patterns from Redis. If None, blocklist check is skipped.

        Returns:
            InjectionScanResult with action recommendation.
        """
        try:
            return self._scan_safe(
                query=query,
                company_id=company_id,
                user_id=user_id,
                ip_address=ip_address,
                rate_limit_count=rate_limit_count,
                tenant_blocklist_patterns=tenant_blocklist_patterns,
            )
        except Exception:
            logger.exception(
                "prompt_injection_scan_error",
                extra={
                    "company_id": company_id,
                    "user_id": user_id,
                    "query_length": len(query) if query else 0,
                },
            )
            # BC-008: Never crash — fail-open with logged action
            return InjectionScanResult(
                is_injection=False,
                matches=[],
                action="allow",
                reason="scan_error_failed_open",
                query_hash=hash_query(query or ""),
            )

    def _scan_safe(
        self,
        query: str,
        company_id: str,
        user_id: Optional[str],
        ip_address: Optional[str],
        rate_limit_count: Optional[int],
        tenant_blocklist_patterns: Optional[List[str]],
    ) -> InjectionScanResult:
        """Internal scan with all layers.

        Layers run in sequence; first critical match can short-circuit
        to 'blocked' for maximum safety.
        """
        query_hash = hash_query(query)
        all_matches: List[InjectionMatch] = []

        # Layer 1: Known patterns
        pattern_matches = self._detect_known_patterns(query)
        all_matches.extend(pattern_matches)

        # Layer 2: Anomaly detection
        anomaly_match = self._detect_anomaly(query, company_id)
        if anomaly_match is not None:
            all_matches.append(anomaly_match)

        # Layer 3: Rate limiting (uses pre-fetched data)
        if rate_limit_count is not None:
            rate_match = self._check_rate_limit(
                rate_limit_count, company_id, user_id,
            )
            if rate_match is not None:
                all_matches.append(rate_match)

        # Layer 4: Tenant blocklist (uses pre-fetched data)
        if tenant_blocklist_patterns is not None:
            blocklist_match = self._check_tenant_blocklist(
                query, company_id, tenant_blocklist_patterns,
            )
            if blocklist_match is not None:
                all_matches.append(blocklist_match)

        # Determine action based on matches
        action, reason = self._determine_action(all_matches)

        return InjectionScanResult(
            is_injection=action != "allow",
            matches=all_matches,
            action=action,
            reason=reason,
            query_hash=query_hash,
        )

    def _detect_known_patterns(self, query: str) -> List[InjectionMatch]:
        """Layer 1: Match against 25+ known injection signatures.

        Organized by category (command injection, context manipulation,
        data extraction, privilege escalation, jailbreaking, encoding
        tricks, multi-turn manipulation).

        Args:
            query: User query string.

        Returns:
            List of InjectionMatch for all matched patterns.
        """
        matches: List[InjectionMatch] = []
        for rule in _ALL_RULES:
            compiled: re.Pattern = rule["pattern"]
            match = compiled.search(query)
            if match:
                matched_text = match.group(0)
                # Limit matched text length for logging
                if len(matched_text) > 200:
                    matched_text = matched_text[:200] + "..."
                matches.append(
                    InjectionMatch(
                        pattern_type=_classify_pattern_type(rule["rule_id"]),
                        severity=rule["severity"],
                        confidence=rule["confidence"],
                        matched_text=matched_text,
                        rule_id=rule["rule_id"],
                        description=rule["description"],
                    )
                )
        return matches

    def _detect_anomaly(
        self, query: str, company_id: str,
    ) -> Optional[InjectionMatch]:
        """Layer 2: Detect unusual query characteristics.

        Checks:
        - Query length (>2000 chars suspicious for support queries)
        - Special character to alphanumeric ratio
        - Uppercase to lowercase ratio
        - Repeated character patterns
        - Shannon entropy (high entropy = suspicious)

        Args:
            query: User query string.
            company_id: Tenant identifier.

        Returns:
            InjectionMatch if anomaly detected, None otherwise.
        """
        if not query:
            return None

        anomalies: List[str] = []
        anomaly_score = 0.0

        # Length check
        query_len = len(query)
        if query_len > _ANOMALY_QUERY_LENGTH_THRESHOLD:
            anomalies.append(
                f"query_length={query_len} (threshold="
                f"{_ANOMALY_QUERY_LENGTH_THRESHOLD})"
            )
            anomaly_score += 2.0

        # Special character ratio
        alpha_count = sum(1 for c in query if c.isalnum())
        total_count = len(query) if query else 1
        special_ratio = (total_count - alpha_count) / total_count
        if special_ratio > _ANOMALY_SPECIAL_CHAR_RATIO:
            anomalies.append(
                f"special_char_ratio={special_ratio:.2f} "
                f"(threshold={_ANOMALY_SPECIAL_CHAR_RATIO})"
            )
            anomaly_score += 2.5

        # Uppercase ratio (only on alpha characters)
        if alpha_count > 5:
            upper_count = sum(1 for c in query if c.isupper())
            upper_ratio = upper_count / alpha_count
            if upper_ratio > _ANOMALY_UPPERCASE_RATIO:
                anomalies.append(
                    f"uppercase_ratio={upper_ratio:.2f} "
                    f"(threshold={_ANOMALY_UPPERCASE_RATIO})"
                )
                anomaly_score += 1.5

        # Entropy check
        entropy = _shannon_entropy(query)
        if entropy > _ANOMALY_ENTROPY_THRESHOLD:
            anomalies.append(
                f"entropy={entropy:.2f} "
                f"(threshold={_ANOMALY_ENTROPY_THRESHOLD})"
            )
            anomaly_score += 2.0

        if anomalies:
            severity = "low"
            if anomaly_score >= 5.0:
                severity = "medium"
            elif anomaly_score >= 8.0:
                severity = "high"

            return InjectionMatch(
                pattern_type="anomaly",
                severity=severity,
                confidence=min(0.5 + anomaly_score * 0.05, 0.95),
                matched_text=query[:100] + ("..." if len(query) > 100 else ""),
                rule_id="ANOM-001",
                description=f"Anomalous query characteristics: "
                           f"{'; '.join(anomalies)}",
            )

        return None

    def _check_rate_limit(
        self,
        rate_limit_count: int,
        company_id: str,
        user_id: Optional[str],
    ) -> Optional[InjectionMatch]:
        """Layer 3: Check rate of suspicious queries per tenant/user.

        Uses pre-fetched count from Redis. The caller is responsible
        for fetching the count and updating it.

        Thresholds:
        - 3+ attempts in 1 hour → escalate (alert)
        - 5+ attempts in 1 hour → block

        Args:
            rate_limit_count: Number of injection attempts in the
                current window (pre-fetched from Redis).
            company_id: Tenant identifier.
            user_id: User identifier or None for anonymous.

        Returns:
            InjectionMatch if rate limit exceeded, None otherwise.
        """
        if rate_limit_count >= _RATE_LIMIT_BLOCK_THRESHOLD:
            return InjectionMatch(
                pattern_type="rate_limit",
                severity="critical",
                confidence=0.99,
                matched_text=(
                    f"rate_limit_count={rate_limit_count} "
                    f"(block_threshold={_RATE_LIMIT_BLOCK_THRESHOLD})"
                ),
                rule_id="RATE-002",
                description=(
                    f"User has {rate_limit_count} injection attempts in "
                    f"{_RATE_LIMIT_WINDOW_SECONDS}s window — BLOCKED"
                ),
            )
        elif rate_limit_count >= _RATE_LIMIT_ESCALATE_THRESHOLD:
            return InjectionMatch(
                pattern_type="rate_limit",
                severity="high",
                confidence=0.95,
                matched_text=(
                    f"rate_limit_count={rate_limit_count} "
                    f"(escalate_threshold={_RATE_LIMIT_ESCALATE_THRESHOLD})"
                ),
                rule_id="RATE-001",
                description=(
                    f"User has {rate_limit_count} injection attempts in "
                    f"{_RATE_LIMIT_WINDOW_SECONDS}s window — ESCALATED"
                ),
            )
        return None

    def _check_tenant_blocklist(
        self,
        query: str,
        company_id: str,
        tenant_blocklist_patterns: List[str],
    ) -> Optional[InjectionMatch]:
        """Layer 4: Check query against per-tenant custom block patterns.

        Admin-configured patterns specific to a tenant stored in Redis.

        Args:
            query: User query string.
            company_id: Tenant identifier.
            tenant_blocklist_patterns: List of regex pattern strings
                from the tenant's blocklist.

        Returns:
            InjectionMatch if a blocklist pattern matched, None otherwise.
        """
        for idx, pattern_str in enumerate(tenant_blocklist_patterns):
            try:
                compiled = re.compile(pattern_str, re.IGNORECASE)
                match = compiled.search(query)
                if match:
                    matched_text = match.group(0)
                    if len(matched_text) > 200:
                        matched_text = matched_text[:200] + "..."
                    return InjectionMatch(
                        pattern_type="tenant_blocklist",
                        severity="high",
                        confidence=0.95,
                        matched_text=matched_text,
                        rule_id=f"TBLK-{idx + 1:03d}",
                        description=(
                            f"Matched tenant blocklist pattern #{idx + 1}"
                        ),
                    )
            except re.error:
                # Invalid regex in blocklist — skip and log
                logger.warning(
                    "tenant_blocklist_invalid_regex",
                    extra={
                        "company_id": company_id,
                        "pattern_index": idx,
                        "pattern": pattern_str[:100],
                    },
                )
                continue
        return None

    def _determine_action(
        self, matches: List[InjectionMatch],
    ) -> tuple[str, str]:
        """Determine the action based on all detected matches.

        Decision logic:
        - No matches → allow
        - Any critical severity → blocked
        - Any high severity → blocked
        - Rate limit critical → blocked
        - Rate limit high → escalated
        - Any medium → logged
        - Any low → logged

        Args:
            matches: List of all detected InjectionMatch objects.

        Returns:
            Tuple of (action, reason).
        """
        if not matches:
            return "allow", "no_injection_detected"

        severity_weights = get_severity_weights()

        # Check for any critical or high severity match (not anomaly)
        for match in matches:
            if match.severity in ("critical", "high"):
                if match.pattern_type == "rate_limit" and match.rule_id == "RATE-001":
                    return "escalated", match.description
                return "blocked", match.description

        # Check for rate limit escalation
        for match in matches:
            if match.pattern_type == "rate_limit":
                return "escalated", match.description

        # Calculate weighted score
        total_score = sum(
            severity_weights.get(m.severity, 1.0) * m.confidence
            for m in matches
        )

        if total_score >= 5.0:
            return "blocked", (
                f"weighted_score={total_score:.2f} exceeds threshold"
            )
        elif total_score >= 2.0:
            return "logged", (
                f"weighted_score={total_score:.2f} — logged for monitoring"
            )

        return "logged", "low_risk_patterns_detected"


# ── Injection Defense Service ───────────────────────────────────────


class InjectionDefenseService:
    """Orchestration + persistence layer for prompt injection defense.

    Bridges sync detection (CPU-bound) with async Redis (rate limiting,
    tenant blocklists) and sync database (injection attempt logging).

    BC-001: Every method requires company_id.
    BC-010: Injection logs retained per GDPR retention policy.
    BC-012: Never crashes — graceful degradation on Redis/DB failure.

    Usage:
        service = InjectionDefenseService()
        result = await service.scan_and_respond(
            query="hello", company_id="acme",
            user_id="u1", ip_address="1.2.3.4",
        )
    """

    def __init__(self) -> None:
        """Initialize the service with a detector instance."""
        self._detector = PromptInjectionDetector()
        logger.info("injection_defense_service_initialized")

    # ── Public API (async — for use in FastAPI endpoints) ────────

    async def scan_and_respond(
        self,
        query: str,
        company_id: str,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> InjectionScanResult:
        """Scan a query and persist the result if injection detected.

        Fetches Redis data asynchronously, runs sync detection,
        then logs the attempt and updates rate limits.

        BC-001: company_id is always second parameter.
        BC-008: Never crashes.

        Args:
            query: User query to scan.
            company_id: Tenant identifier (BC-001).
            user_id: Optional user identifier.
            ip_address: Optional IP address.

        Returns:
            InjectionScanResult with action recommendation.
        """
        try:
            return await self._scan_and_respond_safe(
                query=query,
                company_id=company_id,
                user_id=user_id,
                ip_address=ip_address,
            )
        except Exception:
            logger.exception(
                "injection_defense_scan_error",
                extra={
                    "company_id": company_id,
                    "user_id": user_id,
                },
            )
            # BC-008: Fail-open
            return InjectionScanResult(
                is_injection=False,
                matches=[],
                action="allow",
                reason="service_error_failed_open",
                query_hash=hash_query(query or ""),
            )

    async def _scan_and_respond_safe(
        self,
        query: str,
        company_id: str,
        user_id: Optional[str],
        ip_address: Optional[str],
    ) -> InjectionScanResult:
        """Internal safe scan with Redis + DB integration."""
        # Pre-fetch Redis data for rate limiting and blocklist
        rate_limit_count, tenant_blocklist = await self._fetch_redis_data(
            company_id, user_id,
        )

        # Run sync detection with pre-fetched data
        result = self._detector.scan(
            query=query,
            company_id=company_id,
            user_id=user_id,
            ip_address=ip_address,
            rate_limit_count=rate_limit_count,
            tenant_blocklist_patterns=tenant_blocklist,
        )

        # Persist and update Redis if injection detected
        if result.is_injection:
            await self._persist_and_update(
                company_id=company_id,
                user_id=user_id,
                ip_address=ip_address,
                result=result,
                query=query,
            )

        return result

    # ── Redis Data Fetching ─────────────────────────────────────

    async def _fetch_redis_data(
        self,
        company_id: str,
        user_id: Optional[str],
    ) -> tuple[Optional[int], Optional[List[str]]]:
        """Fetch rate limit count and tenant blocklist from Redis.

        BC-012: Redis failure → return None for both (safe defaults).

        Args:
            company_id: Tenant identifier.
            user_id: Optional user identifier.

        Returns:
            Tuple of (rate_limit_count, tenant_blocklist_patterns).
            Either may be None if Redis is unavailable.
        """
        rate_limit_count: Optional[int] = None
        tenant_blocklist: Optional[List[str]] = None

        try:
            from app.core.redis import get_redis, make_key

            redis_client = await get_redis()

            # Fetch rate limit count
            user_key = user_id or "anon"
            rate_key = make_key(
                company_id, "injection_rate", user_key,
            )
            raw_count = await redis_client.get(rate_key)
            if raw_count is not None:
                rate_limit_count = int(raw_count)

            # Fetch tenant blocklist
            blocklist_key = make_key(company_id, "tenant_blocklist")
            raw_blocklist = await redis_client.get(blocklist_key)
            if raw_blocklist is not None:
                try:
                    tenant_blocklist = json.loads(raw_blocklist)
                except (json.JSONDecodeError, TypeError):
                    tenant_blocklist = None

        except Exception:
            logger.warning(
                "injection_defense_redis_fetch_error",
                extra={"company_id": company_id},
            )
            # BC-012: Redis failure → safe defaults

        return rate_limit_count, tenant_blocklist

    # ── Persistence + Redis Update ──────────────────────────────

    async def _persist_and_update(
        self,
        company_id: str,
        user_id: Optional[str],
        ip_address: Optional[str],
        result: InjectionScanResult,
        query: str,
    ) -> None:
        """Log injection attempt to DB and update Redis rate limit.

        BC-001: company_id on every DB write.
        BC-012: Individual failures don't affect each other.
        """
        # Find the highest-severity match for logging
        severity_weights = get_severity_weights()
        best_match: Optional[InjectionMatch] = None
        best_weight = -1.0
        for match in result.matches:
            weight = severity_weights.get(match.severity, 1.0)
            if weight > best_weight:
                best_weight = weight
                best_match = match

        detection_method = "multi_layer"
        if len(result.matches) == 1:
            m = result.matches[0]
            if m.pattern_type == "anomaly":
                detection_method = "anomaly"
            elif m.pattern_type == "rate_limit":
                detection_method = "rate_limit"
            elif m.pattern_type == "tenant_blocklist":
                detection_method = "tenant_blocklist"
            else:
                detection_method = "regex"

        # Log to database (sync — fire and forget with error handling)
        try:
            self.log_attempt(
                company_id=company_id,
                pattern_type=(
                    best_match.pattern_type if best_match else "unknown"
                ),
                severity=(
                    best_match.severity if best_match else "medium"
                ),
                query_hash=result.query_hash,
                query_preview=_truncate_preview(query),
                detection_method=detection_method,
                action_taken=result.action,
                user_id=user_id,
                ip_address=ip_address,
            )
        except Exception:
            logger.exception(
                "injection_defense_db_log_error",
                extra={"company_id": company_id},
            )

        # Update Redis rate limit counter (async)
        try:
            await self._increment_rate_limit(company_id, user_id)
        except Exception:
            logger.warning(
                "injection_defense_redis_rate_update_error",
                extra={"company_id": company_id},
            )

        # GAP FIX: Log escalation events for monitoring/alerting.
        # When action is "escalated", emit a structured warning log
        # that can be picked up by the monitoring/alerting pipeline.
        if result.action == "escalated":
            logger.warning(
                "injection_attempt_escalated",
                extra={
                    "company_id": company_id,
                    "user_id": user_id,
                    "ip_address": ip_address,
                    "query_hash": result.query_hash,
                    "match_count": len(result.matches),
                    "reason": result.reason,
                    "severity": "HIGH",
                },
            )

    # ── Database Operations (sync) ──────────────────────────────

    def log_attempt(
        self,
        company_id: str,
        pattern_type: str,
        severity: str,
        query_hash: str,
        query_preview: str,
        detection_method: str,
        action_taken: str,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> str:
        """Log an injection attempt to the database.

        Writes to prompt_injection_attempts table.

        BC-001: company_id is required on every record.
        BC-010: Retained per GDPR retention policy.

        Args:
            company_id: Tenant identifier (BC-001).
            pattern_type: Type of injection pattern detected.
            severity: Severity level (low/medium/high/critical).
            query_hash: SHA-256 hash of the query.
            query_preview: Truncated query text (max 500 chars).
            detection_method: How the injection was detected.
            action_taken: Action taken (logged/blocked/escalated).
            user_id: Optional user identifier.
            ip_address: Optional IP address.

        Returns:
            The ID of the created record.
        """
        from database.base import SessionLocal
        from database.models.variant_engine import PromptInjectionAttempt

        db = SessionLocal()
        try:
            attempt = PromptInjectionAttempt(
                company_id=company_id,
                pattern_type=pattern_type,
                severity=severity,
                query_hash=query_hash,
                query_preview=query_preview,
                detection_method=detection_method,
                action_taken=action_taken,
                user_id=user_id,
                ip_address=ip_address,
            )
            db.add(attempt)
            db.commit()
            db.refresh(attempt)
            attempt_id = attempt.id

            logger.info(
                "injection_attempt_logged",
                extra={
                    "company_id": company_id,
                    "attempt_id": attempt_id,
                    "pattern_type": pattern_type,
                    "severity": severity,
                    "action": action_taken,
                    "user_id": user_id,
                },
            )
            return attempt_id
        except Exception:
            db.rollback()
            logger.exception(
                "injection_attempt_log_failed",
                extra={
                    "company_id": company_id,
                    "pattern_type": pattern_type,
                },
            )
            raise
        finally:
            db.close()

    def get_injection_history(
        self,
        company_id: str,
        hours: int = 24,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get recent injection attempts for a tenant.

        BC-001: Scoped by company_id.

        Args:
            company_id: Tenant identifier.
            hours: How many hours back to look.
            limit: Maximum number of records to return.

        Returns:
            List of dicts with attempt details.
        """
        from database.base import SessionLocal
        from database.models.variant_engine import PromptInjectionAttempt

        db = SessionLocal()
        try:
            since = datetime.now(timezone.utc) - timedelta(hours=hours)
            attempts = (
                db.query(PromptInjectionAttempt)
                .filter(
                    PromptInjectionAttempt.company_id == company_id,
                    PromptInjectionAttempt.created_at >= since,
                )
                .order_by(PromptInjectionAttempt.created_at.desc())
                .limit(limit)
                .all()
            )
            return [
                {
                    "id": a.id,
                    "company_id": a.company_id,
                    "instance_id": a.instance_id,
                    "pattern_type": a.pattern_type,
                    "severity": a.severity,
                    "query_hash": a.query_hash,
                    "query_preview": a.query_preview,
                    "detection_method": a.detection_method,
                    "action_taken": a.action_taken,
                    "user_id": a.user_id,
                    "ip_address": a.ip_address,
                    "created_at": (
                        a.created_at.isoformat() if a.created_at else None
                    ),
                }
                for a in attempts
            ]
        except Exception:
            logger.exception(
                "injection_history_fetch_error",
                extra={"company_id": company_id},
            )
            return []
        finally:
            db.close()

    def get_injection_stats(
        self,
        company_id: str,
        days: int = 7,
    ) -> Dict[str, Any]:
        """Get injection statistics for a tenant.

        BC-001: Scoped by company_id.

        Args:
            company_id: Tenant identifier.
            days: Number of days to analyze.

        Returns:
            Dict with total_attempts, by_severity, by_pattern_type,
            by_hour, and escalated_count.
        """
        from database.base import SessionLocal
        from database.models.variant_engine import PromptInjectionAttempt

        db = SessionLocal()
        try:
            since = datetime.now(timezone.utc) - timedelta(days=days)
            attempts = (
                db.query(PromptInjectionAttempt)
                .filter(
                    PromptInjectionAttempt.company_id == company_id,
                    PromptInjectionAttempt.created_at >= since,
                )
                .all()
            )

            total_attempts = len(attempts)
            by_severity: Dict[str, int] = {}
            by_pattern_type: Dict[str, int] = {}
            by_hour: Dict[str, int] = {}
            escalated_count = 0

            for a in attempts:
                by_severity[a.severity] = by_severity.get(a.severity, 0) + 1
                by_pattern_type[a.pattern_type] = (
                    by_pattern_type.get(a.pattern_type, 0) + 1
                )
                if a.action_taken in ("escalated", "blocked"):
                    escalated_count += 1
                if a.created_at:
                    hour_key = a.created_at.strftime("%Y-%m-%dT%H:00")
                    by_hour[hour_key] = by_hour.get(hour_key, 0) + 1

            return {
                "company_id": company_id,
                "period_days": days,
                "total_attempts": total_attempts,
                "by_severity": by_severity,
                "by_pattern_type": by_pattern_type,
                "by_hour": by_hour,
                "escalated_count": escalated_count,
            }
        except Exception:
            logger.exception(
                "injection_stats_fetch_error",
                extra={"company_id": company_id},
            )
            return {
                "company_id": company_id,
                "period_days": days,
                "total_attempts": 0,
                "by_severity": {},
                "by_pattern_type": {},
                "by_hour": {},
                "escalated_count": 0,
            }
        finally:
            db.close()

    # ── Redis Rate Limiting ─────────────────────────────────────

    async def _increment_rate_limit(
        self,
        company_id: str,
        user_id: Optional[str],
    ) -> None:
        """Increment the injection rate limit counter in Redis.

        Uses a sliding window of _RATE_LIMIT_WINDOW_SECONDS.
        Key: parwa:{company_id}:injection_rate:{user_id or anon}

        BC-001: Key is tenant-scoped.

        Args:
            company_id: Tenant identifier.
            user_id: Optional user identifier.
        """
        from app.core.redis import get_redis, make_key

        redis_client = await get_redis()
        user_key = user_id or "anon"
        rate_key = make_key(company_id, "injection_rate", user_key)

        # Increment counter with TTL
        pipe = redis_client.pipeline(transaction=True)
        pipe.incr(rate_key)
        pipe.expire(rate_key, _RATE_LIMIT_WINDOW_SECONDS)
        await pipe.execute()

    # ── Tenant Blocklist Management (async) ─────────────────────

    async def add_tenant_blocklist_pattern(
        self,
        company_id: str,
        pattern: str,
        description: str = "",
    ) -> bool:
        """Add a custom block pattern to a tenant's blocklist.

        Patterns are stored as a JSON list in Redis.
        Key: parwa:{company_id}:tenant_blocklist

        BC-001: Scoped by company_id.

        Args:
            company_id: Tenant identifier.
            pattern: Regex pattern string to block.
            description: Human-readable description of the pattern.

        Returns:
            True if added successfully, False otherwise.
        """
        try:
            # Validate the regex pattern before storing
            re.compile(pattern)

            from app.core.redis import get_redis, make_key

            redis_client = await get_redis()
            blocklist_key = make_key(company_id, "tenant_blocklist")

            # Fetch existing blocklist
            raw = await redis_client.get(blocklist_key)
            existing: List[Dict[str, str]] = []
            if raw:
                try:
                    existing = json.loads(raw)
                except (json.JSONDecodeError, TypeError):
                    existing = []

            # Check for duplicates
            for entry in existing:
                if entry.get("pattern") == pattern:
                    logger.info(
                        "tenant_blocklist_pattern_already_exists",
                        extra={
                            "company_id": company_id,
                            "pattern": pattern[:100],
                        },
                    )
                    return True

            # Add new pattern
            existing.append({
                "pattern": pattern,
                "description": description,
                "added_at": datetime.now(timezone.utc).isoformat(),
            })

            await redis_client.set(
                blocklist_key,
                json.dumps(existing),
            )

            logger.info(
                "tenant_blocklist_pattern_added",
                extra={
                    "company_id": company_id,
                    "pattern": pattern[:100],
                    "description": description,
                    "total_patterns": len(existing),
                },
            )
            return True

        except re.error:
            logger.warning(
                "tenant_blocklist_invalid_pattern",
                extra={
                    "company_id": company_id,
                    "pattern": pattern[:100],
                },
            )
            return False
        except Exception:
            logger.exception(
                "tenant_blocklist_add_error",
                extra={"company_id": company_id},
            )
            return False

    async def remove_tenant_blocklist_pattern(
        self,
        company_id: str,
        pattern: str,
    ) -> bool:
        """Remove a pattern from a tenant's blocklist.

        BC-001: Scoped by company_id.

        Args:
            company_id: Tenant identifier.
            pattern: Exact pattern string to remove.

        Returns:
            True if removed, False if not found or error.
        """
        try:
            from app.core.redis import get_redis, make_key

            redis_client = await get_redis()
            blocklist_key = make_key(company_id, "tenant_blocklist")

            raw = await redis_client.get(blocklist_key)
            if raw is None:
                return False

            existing: List[Dict[str, str]] = json.loads(raw)
            original_len = len(existing)

            existing = [
                entry for entry in existing
                if entry.get("pattern") != pattern
            ]

            if len(existing) == original_len:
                return False

            await redis_client.set(
                blocklist_key,
                json.dumps(existing),
            )

            logger.info(
                "tenant_blocklist_pattern_removed",
                extra={
                    "company_id": company_id,
                    "pattern": pattern[:100],
                    "remaining_patterns": len(existing),
                },
            )
            return True

        except Exception:
            logger.exception(
                "tenant_blocklist_remove_error",
                extra={"company_id": company_id},
            )
            return False

    async def get_tenant_blocklist(
        self,
        company_id: str,
    ) -> List[Dict[str, str]]:
        """Get all patterns in a tenant's blocklist.

        BC-001: Scoped by company_id.

        Args:
            company_id: Tenant identifier.

        Returns:
            List of dicts with 'pattern', 'description', 'added_at'.
        """
        try:
            from app.core.redis import get_redis, make_key

            redis_client = await get_redis()
            blocklist_key = make_key(company_id, "tenant_blocklist")

            raw = await redis_client.get(blocklist_key)
            if raw is None:
                return []

            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return parsed
            return []

        except Exception:
            logger.exception(
                "tenant_blocklist_fetch_error",
                extra={"company_id": company_id},
            )
            return []

    # ── GDPR Cleanup ────────────────────────────────────────────

    def clear_injection_history(
        self,
        company_id: str,
        older_than_days: int = 90,
    ) -> int:
        """Delete injection attempts older than the retention period.

        BC-001: Scoped by company_id.
        BC-010: Injection logs retained per GDPR policy (default 90 days).

        Args:
            company_id: Tenant identifier.
            older_than_days: Delete records older than this many days.

        Returns:
            Number of deleted records.
        """
        from database.base import SessionLocal
        from database.models.variant_engine import PromptInjectionAttempt

        db = SessionLocal()
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)
            deleted = (
                db.query(PromptInjectionAttempt)
                .filter(
                    PromptInjectionAttempt.company_id == company_id,
                    PromptInjectionAttempt.created_at < cutoff,
                )
                .delete(synchronize_session="fetch")
            )
            db.commit()

            logger.info(
                "injection_history_cleared",
                extra={
                    "company_id": company_id,
                    "deleted_count": deleted,
                    "older_than_days": older_than_days,
                },
            )
            return deleted
        except Exception:
            db.rollback()
            logger.exception(
                "injection_history_clear_error",
                extra={"company_id": company_id},
            )
            return 0
        finally:
            db.close()
