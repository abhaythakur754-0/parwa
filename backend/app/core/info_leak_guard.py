"""
Information Leakage Prevention Guard (Day 4 Security Audit)

Scans AI responses for accidental disclosure of internal system details:
- LLM model names / versions being used
- Routing strategy and model selection logic
- Internal workflow / pipeline details
- System prompts and instructions
- Other tenants' existence or data

Provides a canned refusal response when leaks are detected.

BC-001: All checks scoped by company_id.
BC-012: Never crashes — returns pass on error.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set

from app.logger import get_logger

logger = get_logger("info_leak_guard")


# ══════════════════════════════════════════════════════════════════
# COMPILED REGEX PATTERNS
# ══════════════════════════════════════════════════════════════════


# ── Category 1: LLM Model Name Disclosure ──
_RE_LLM_NAMES = re.compile(
    r"\b(?:I(?:'m| am)\s+(?:powered by|running on|built (?:on|with|using))\s+)"
    r"|(?:we use|our system uses?|powered by|running on|built with|using)\s+"
    r"(?:OpenAI|GPT-4|GPT-4o|GPT-4-turbo|GPT-3\.5|GPT-3|ChatGPT|"
    r"Claude|Claude-3|Claude-3\.5|Claude-2|Anthropic|"
    r"Gemini|Gemini Pro|Gemini Ultra|Google AI|PaLM|Bard|"
    r"Llama|Llama-2|Llama-3|Llama-3\.1|Meta AI|"
    r"Mistral|Mistral Large|Mistral Medium|Mixtral|"
    r"Cohere|Command R|Command R\+|"
    r"grok|xAI|DeepSeek|Qwen|Yi|"
    r"o1-preview|o1-mini|o3-mini|"
    r"GPT-[0-9]|Claude-[0-9]|Llama-[0-9])\b"
    r"|\byou\s+are\s+(?:ChatGPT|GPT|Claude|Gemini|Bard|Llama)\b",
    re.IGNORECASE,
)

# ── Category 2: Routing Strategy Disclosure ──
_RE_ROUTING_STRATEGY = re.compile(
    r"\b(?:our (?:routing|routing strategy|model selection|smart routing|"
    r"intelligent routing|load balancing|fallback|failover) "
    r"(?:strategy|logic|algorithm|mechanism|system|engine|policy))"
    r"|(?:we route (?:to|your query to|requests to))"
    r"|(?:the (?:model|system) (?:was|is) (?:chosen|selected|routed|assigned)"
    r"\s+(?:based on|because of|due to|according to))"
    r"|(?:model (?:selection|routing|switching|fallback) (?:is|was|happens))"
    r"|(?:we (?:use|employ|have) a (?:smart|intelligent|tiered) (?:router|routing))"
    r"|(?:GPT-\d|Claude|Llama)\b.*?(?:based on|chosen|selected|routed)\b"
    r"|(?:chosen|selected|routed)\s+(?:GPT-\d|Claude|Llama)\b",
    re.IGNORECASE,
)

# ── Category 3: Internal Workflow Disclosure ──
_RE_WORKFLOW_DETAILS = re.compile(
    r"\b(?:our internal (?:workflow|pipeline|process|system|architecture))"
    r"|(?:the AI (?:pipeline|engine|backend|processing chain))"
    r"|(?:we process your (?:request|query|message) (?:through|via|using))"
    r"|(?:our (?:prompt|system) (?:template|chain|engineering|architecture))"
    r"|(?:RAG|retrieval.augmented|knowledge base|vector (?:search|store|database))"
    r"|(?:our (?:guardrails?|safety (?:layer|check|system)))\b",
    re.IGNORECASE,
)

# ── Category 4: System Prompt Disclosure ──
_RE_SYSTEM_PROMPT = re.compile(
    r"\b(?:my (?:system |hidden |initial )?(?:instructions?|prompt|rules?|guidelines?|directives?))"
    r"|(?:the (?:system |hidden |initial )?(?:instructions?|prompt|rules?|guidelines?))"
    r"|(?:I was (?:told|instructed|programmed|configured) to)"
    r"|(?:my (?:creator|developer|engineer|designer) (?:told|set|configured))"
    r"|(?:according to (?:my )?(?:system |hidden )?(?:prompt|instructions?|rules?))\b",
    re.IGNORECASE,
)

# ── Category 5: Other Tenant Disclosure ──
_RE_TENANT_DISCLOSURE = re.compile(
    r"\b(?:other (?:companies?|organizations?|tenants?|clients?|customers?)"
    r"\s+(?:on (?:our )?(?:platform|system|service)|use (?:our )?(?:service)))"
    r"|(?:we (?:also serve|have|support) (?:other )?(?:companies?|clients?|customers?|tenants?))"
    r"|(?:another (?:tenant|company|client|customer) (?:on|using) (?:our )?(?:platform|system))"
    r"|(?:other (?:users?|organizations?) (?:have (?:also )?|on our platform))"
    r"|(?:across (?:all )?(?:our )?(?:tenants?|clients?|customers?|organizations?))\b",
    re.IGNORECASE,
)

# ── Category 6: Internal Metrics / Stats Disclosure ──
_RE_INTERNAL_METRICS = re.compile(
    r"\b(?:we (?:have|serve|process|handle) (?:over|about|approximately|around)\s+\d[\d,]*\s+"
    r"(?:requests?|queries?|users?|customers?|tenants?|messages?|tickets?))"
    r"|(?:our (?:accuracy|success rate|response time|latency|uptime) (?:is|was|stands at))"
    r"|(?:our (?:system|platform|service) (?:processes?|handles?) (?:approximately|about|around))\b",
    re.IGNORECASE,
)

# ══════════════════════════════════════════════════════════════════
# CONSTANTS
# ══════════════════════════════════════════════════════════════════

CANNED_REFUSAL_RESPONSE: str = "I cannot discuss PARWA's internal systems."

# All detection patterns in order of check priority
_ALL_INFO_LEAK_PATTERNS: List[Dict[str, Any]] = [
    {
        "pattern": _RE_SYSTEM_PROMPT,
        "category": "system_prompt",
        "severity": "critical",
        "confidence": 0.92,
    },
    {
        "pattern": _RE_LLM_NAMES,
        "category": "llm_model_names",
        "severity": "high",
        "confidence": 0.88,
    },
    {
        "pattern": _RE_ROUTING_STRATEGY,
        "category": "routing_strategy",
        "severity": "high",
        "confidence": 0.85,
    },
    {
        "pattern": _RE_WORKFLOW_DETAILS,
        "category": "internal_workflow",
        "severity": "medium",
        "confidence": 0.72,
    },
    {
        "pattern": _RE_TENANT_DISCLOSURE,
        "category": "tenant_disclosure",
        "severity": "critical",
        "confidence": 0.90,
    },
    {
        "pattern": _RE_INTERNAL_METRICS,
        "category": "internal_metrics",
        "severity": "medium",
        "confidence": 0.68,
    },
]


# ══════════════════════════════════════════════════════════════════
# DATA CLASSES
# ══════════════════════════════════════════════════════════════════


@dataclass
class InfoLeakMatch:
    """Describes a single detected information leak."""

    category: str
    severity: str
    confidence: float
    matched_text: str
    description: str


@dataclass
class InfoLeakScanResult:
    """Result of an information leak scan."""

    has_leak: bool
    matches: List[InfoLeakMatch]
    action: str  # "allow" or "block"
    sanitized_response: Optional[str] = None
    reason: str = ""


# ══════════════════════════════════════════════════════════════════
# INFO LEAK GUARD
# ══════════════════════════════════════════════════════════════════


class InfoLeakGuard:
    """Scans AI responses for information leakage.

    Checks for accidental disclosure of:
    - LLM model names / versions
    - Routing strategy details
    - Internal workflow / pipeline architecture
    - System prompts and instructions
    - Other tenants' existence
    - Internal metrics and statistics

    When a leak is detected, returns a canned refusal response instead
    of the original AI output.

    BC-001: All checks scoped by company_id.
    BC-012: Never crashes — returns pass on error.
    """

    # Severity thresholds for action determination
    _BLOCK_SEVERITIES: Set[str] = {"critical", "high"}

    def __init__(self) -> None:
        self._patterns = _ALL_INFO_LEAK_PATTERNS
        logger.info("info_leak_guard_initialized")

    def scan(
        self,
        response: str,
        company_id: str,
        *,
        block_on_medium: bool = False,
    ) -> InfoLeakScanResult:
        """Scan an AI response for information leakage.

        Args:
            response: The AI-generated response text to scan.
            company_id: Tenant identifier (BC-001).
            block_on_medium: If True, also block on medium-severity leaks.

        Returns:
            InfoLeakScanResult with leak detection outcome.
        """
        try:
            return self._scan_safe(
                response=response,
                company_id=company_id,
                block_on_medium=block_on_medium,
            )
        except Exception:
            logger.exception(
                "info_leak_scan_error",
                extra={
                    "company_id": company_id,
                    "response_length": len(response) if response else 0,
                },
            )
            # BC-012: Never crash — fail-open
            return InfoLeakScanResult(
                has_leak=False,
                matches=[],
                action="allow",
                reason="scan_error_failed_open",
            )

    def _scan_safe(
        self,
        response: str,
        company_id: str,
        block_on_medium: bool,
    ) -> InfoLeakScanResult:
        """Internal scan implementation."""
        if not response or not response.strip():
            return InfoLeakScanResult(
                has_leak=False,
                matches=[],
                action="allow",
                reason="empty_response",
            )

        all_matches: List[InfoLeakMatch] = []

        for rule in self._patterns:
            compiled: re.Pattern = rule["pattern"]
            match = compiled.search(response)
            if match:
                matched_text = match.group()
                # Truncate for logging
                if len(matched_text) > 200:
                    matched_text = matched_text[:200] + "..."
                all_matches.append(
                    InfoLeakMatch(
                        category=rule["category"],
                        severity=rule["severity"],
                        confidence=rule["confidence"],
                        matched_text=matched_text,
                        description=f"Potential {rule['category']} disclosure",
                    )
                )

        if not all_matches:
            return InfoLeakScanResult(
                has_leak=False,
                matches=[],
                action="allow",
                reason="no_leak_detected",
            )

        # Determine action: block on critical/high, optionally on medium
        should_block = any(m.severity in self._BLOCK_SEVERITIES for m in all_matches)
        if block_on_medium:
            should_block = should_block or any(
                m.severity == "medium" for m in all_matches
            )

        if should_block:
            categories = sorted({m.category for m in all_matches})
            logger.warning(
                "info_leak_detected",
                extra={
                    "company_id": company_id,
                    "categories": categories,
                    "match_count": len(all_matches),
                    "action": "blocked",
                },
            )
            return InfoLeakScanResult(
                has_leak=True,
                matches=all_matches,
                action="block",
                sanitized_response=CANNED_REFUSAL_RESPONSE,
                reason=(
                    "Information leakage detected in categories: "
                    f"{', '.join(categories)}"
                ),
            )

        # Medium-severity leaks that didn't trigger block
        categories = sorted({m.category for m in all_matches})
        logger.info(
            "info_leak_detected_but_allowed",
            extra={
                "company_id": company_id,
                "categories": categories,
                "match_count": len(all_matches),
                "action": "flagged",
            },
        )
        return InfoLeakScanResult(
            has_leak=True,
            matches=all_matches,
            action="flagged",
            reason=(
                "Low-confidence leak detected in categories: "
                f"{', '.join(categories)}"
            ),
        )

    def sanitize(
        self,
        response: str,
        company_id: str,
    ) -> str:
        """Convenience method: scan and return sanitized response.

        If a leak is detected, returns the canned refusal.
        Otherwise returns the original response unchanged.

        Args:
            response: The AI response to scan.
            company_id: Tenant identifier.

        Returns:
            Either the original response or the canned refusal.
        """
        result = self.scan(response, company_id)
        if result.action == "block":
            return result.sanitized_response or CANNED_REFUSAL_RESPONSE
        return response

    def get_canned_response(self) -> str:
        """Return the default canned refusal response.

        Returns:
            Canned refusal string.
        """
        return CANNED_REFUSAL_RESPONSE
