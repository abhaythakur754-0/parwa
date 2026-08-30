"""
Dynamic Signal Updater — publishes Superglue tool signals to Redis
so the Smart Router discovers new tools and activates REACT technique.

BC-008: All functions fail-open (return 0/None/no-op on error).
"""

from __future__ import annotations

from typing import Any


_INTENT_KEYS = [
    "refund", "billing", "technical", "complaint", "cancellation",
    "shipping", "inquiry", "escalation", "account", "feedback",
    "feature_request",
]

_INTENT_STEMS = {
    "cancel": "cancellation", "ship": "shipping", "complain": "complaint",
    "escalate": "escalation", "enquire": "inquiry", "inquire": "inquiry",
    "refund": "refund", "bill": "billing", "account": "account",
}

_FINANCIAL_KEYWORDS = {"refund", "credit", "cashback", "payout", "charge", "payment", "billing", "invoice"}
_DESTRUCTIVE_KEYWORDS = {"delete", "remove", "cancel", "destroy", "purge", "drop", "terminate"}

_SIGNAL_TTL = 300

# In-memory fallback when Redis is unavailable (BC-008)
_memory_cache: dict[str, dict] = {}


def _detect_intents(tool_name: str) -> list[str]:
    name_lower = tool_name.lower()
    intents = [i for i in _INTENT_KEYS if i.replace("_", " ") in name_lower or i in name_lower]
    for stem, intent in _INTENT_STEMS.items():
        if stem in name_lower and intent not in intents:
            intents.append(intent)
    return intents


async def publish_superglue_signals(company_id: str, tools: list[dict]) -> int:
    """Publish Superglue tool signals to Redis. Returns intent count, 0 on error."""
    try:
        all_intents: list[str] = []
        has_financial = False
        has_destructive = False

        for tool in tools:
            name = tool.get("name", "")
            all_intents.extend(_detect_intents(name))
            name_lower = name.lower()
            if any(kw in name_lower for kw in _FINANCIAL_KEYWORDS):
                has_financial = True
            if any(kw in name_lower for kw in _DESTRUCTIVE_KEYWORDS):
                has_destructive = True

        unique_intents = list(dict.fromkeys(all_intents))
        signal = {
            "has_tools": len(tools) > 0,
            "tool_count": len(tools),
            "has_financial_tools": has_financial,
            "has_destructive_tools": has_destructive,
            "intents": unique_intents,
        }

        # Try Redis first, fall back to memory (BC-008)
        try:
            from app.core.redis import cache_set
            await cache_set(company_id, "superglue_signals", signal, ttl_seconds=_SIGNAL_TTL)
        except (ImportError, Exception):
            _memory_cache[company_id] = signal

        return len(unique_intents)
    except Exception:
        return 0


async def get_superglue_signals(company_id: str) -> dict | None:
    """Read Superglue signals from Redis. Falls back to memory cache."""
    try:
        try:
            from app.core.redis import cache_get
            result = await cache_get(company_id, "superglue_signals")
            if result is not None:
                return result
        except (ImportError, Exception):
            pass
        return _memory_cache.get(company_id)
    except Exception:
        return None


def enrich_query_signals(company_id: str, signals: Any) -> None:
    """Set external_data_required=True if Superglue tools exist for tenant.

    This is the sync variant called by the Smart Router.
    BC-008: no-op on error.
    """
    try:
        cached = _memory_cache.get(company_id)
        if cached and cached.get("has_tools"):
            signals.external_data_required = True
    except Exception:
        pass
