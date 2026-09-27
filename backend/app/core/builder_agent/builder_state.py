"""
Builder Agent State — tracks chat history + collected agent config.

The Builder Agent runs as a mini-pipeline. This state object holds
everything collected during the multi-turn chat so the Builder can
design a complete agent config before finalizing.

According to the ROADMAP:
  - Builder uses 34 LLM calls across 4 model tiers for ~97% config accuracy
  - Builder enforces "Customer Care Only" rule
  - Builder decides attachment method automatically
  - Builder creates custom categories + keywords when needed
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from typing_extensions import TypedDict


class BuilderAgentConfig(TypedDict, total=False):
    """Collected config for a single agent being built.

    Populated incrementally during the 4-stage pipeline.
    All fields are optional until the REFINE stage completes.
    """

    # ── IDENTITY ────────────────────────────────────────────────────
    agent_name: str                    # e.g. "Refund Specialist"
    agent_role: str                    # e.g. "auto_created", "custom"
    domain: str                        # e.g. "Hospitality", "E-commerce"

    # ── CAPABILITIES ────────────────────────────────────────────────
    capabilities: List[str]            # e.g. ["refund_processing", "billing_inquiry"]
    instructions: str                  # system prompt for the agent
    restrictions: str                  # rules the agent must follow

    # ── ATTACHMENT (Builder decides) ────────────────────────────────
    attachment_method: str             # "existing_category", "custom_category", "keyword_trigger"
    attached_category: Optional[str]   # existing category key (e.g. "billing_payments")
    custom_category_name: Optional[str]  # new custom category name
    custom_category_keywords: Optional[List[str]]  # trigger keywords for custom category

    # ── KNOWLEDGE ───────────────────────────────────────────────────
    knowledge_sources: List[Dict[str, Any]]  # URLs or doc references
    guardrails: List[Dict[str, Any]]  # hard rules (max_refund, blocked_keywords, etc.)
    custom_actions: List[Dict[str, Any]]  # custom API actions

    # ── SCOPE ENFORCEMENT ───────────────────────────────────────────
    is_customer_care: bool             # True if agent is customer-care scoped
    scope_rejection_reason: Optional[str]  # why it was rejected if not customer-care


class BuilderState(TypedDict, total=False):
    """Full state for a Builder Agent session.

    Tracks the multi-turn chat + collected config across 4 stages.
    """

    # ── SESSION ─────────────────────────────────────────────────────
    session_id: str                    # unique builder session ID
    tenant_id: str                     # company_id of the tenant
    tier: str                          # tenant tier: mini_parwa, parwa, parwa_high

    # ── CHAT ────────────────────────────────────────────────────────
    chat_history: List[Dict[str, str]] # [{role: "user"|"assistant", content: "..."}]
    current_stage: str                 # "explore", "design", "verify", "refine", "complete"
    stage_iterations: Dict[str, int]   # how many LLM calls per stage

    # ── COLLECTED CONFIG ────────────────────────────────────────────
    config: BuilderAgentConfig

    # ── PIPELINE CONTEXT (from Node 1) ──────────────────────────────
    detected_capability: Optional[str]  # capability that triggered the Builder
    ticket_query: Optional[str]        # the original ticket text
    ticket_type: Optional[str]         # classified ticket type
    complexity: Optional[str]          # classified complexity

    # ── CANDIDATES (DESIGN stage generates 3) ───────────────────────
    candidates: List[BuilderAgentConfig]  # 3 candidate configs from DESIGN
    synthesized_config: Optional[BuilderAgentConfig]  # best of 3 after synthesis

    # ── VERIFICATION ────────────────────────────────────────────────
    verify_votes: List[Dict[str, Any]]    # 3 voter scores
    verify_consensus: Optional[Dict[str, Any]]  # what voters agree on
    verify_issues: List[str]           # problems found during verification
    guardrail_safe: bool               # Llama Guard safety scan result

    # ── REFINEMENT ──────────────────────────────────────────────────
    refine_iterations: int             # how many refine loops
    refine_quality_score: float        # 0.0-1.0

    # ── NON-LLM TECHNIQUE RESULTS (zero cost tracking) ─────────────
    non_llm_log: List[Dict[str, Any]]  # [{stage, technique, result_summary}]
    non_llm_scores: Dict[str, float]   # technique → score (0.0-1.0)
    non_llm_flags: List[str]           # issues found by non-LLM techniques
    smart_route_action: Optional[str]  # "full_build", "template_only", "clone_existing"

    # ── RESULT ──────────────────────────────────────────────────────
    agent_id: Optional[str]            # ID of the created agent (after finalize)
    status: str                        # "building", "complete", "rejected", "failed"
    error: Optional[str]              # error message if failed


# ── Scope enforcement: Customer Care Only ──────────────────────────

CUSTOM_CARE_KEYWORDS = [
    "refund", "return", "cancel", "billing", "payment", "invoice",
    "support", "help", "question", "complaint", "issue", "problem",
    "shipping", "delivery", "tracking", "order", "account", "login",
    "password", "subscription", "plan", "upgrade", "downgrade",
    "booking", "reservation", "claim", "coverage", "prescription",
    "technical", "bug", "error", "broken", "faq", "onboarding",
    "welcome", "setup", "guide", "tutorial", "how to", "what is",
    "policy", "quote", "loyalty", "reward", "port", "activation",
    "outage", "maintenance", "lease", "rental",
]

NON_CARE_KEYWORDS = [
    "write code", "marketing copy", "sales script", "blog post",
    "social media post", "ad campaign", "seo", "graphic design",
    "video editing", "music composition", "data analysis",
    "financial modeling", "legal document drafting",
]


def is_customer_care_request(description: str) -> tuple:
    """Check if the described agent falls within customer care scope.

    Returns (is_care: bool, reason: str).
    The Builder MUST refuse any request outside customer support,
    customer success, and onboarding (ROADMAP Section 2.1).
    """
    desc_lower = description.lower()

    # Check for explicit non-care requests
    for kw in NON_CARE_KEYWORDS:
        if kw in desc_lower:
            return False, f"Request involves '{kw}' which is outside customer care scope."

    # Check for care-related keywords
    care_score = sum(1 for kw in CUSTOM_CARE_KEYWORDS if kw in desc_lower)

    if care_score >= 1:
        return True, "Request is within customer care scope."

    # If no clear signal, lean toward allowing (with a note)
    return True, "Scope unclear — proceeding with caution. Agent will be flagged for review."
