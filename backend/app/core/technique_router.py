"""
Technique Router (BC-013)

Analyzes query signals and determines which reasoning technique(s)
should activate. Operates as a classification and orchestration layer
between query intake and response generation.

CRITICAL DISTINCTION:
  - Smart Router (F-054)  → selects which AI MODEL to use
  - Technique Router (BC-013) → selects which REASONING TECHNIQUE to apply
  - Both work independently but execute together within LangGraph (F-060).

Architecture:
  Tier 1 (Always Active):  CLARA, CRP, GSD
  Tier 2 (Conditional):    CoT, Reverse Thinking, ReAct, Step-Back, ThoT
  Tier 3 (Premium):        GST, UoT, ToT, Self-Consistency, Reflexion, Least-to-Most

Parent Framework: TRIVYA Optimization Framework
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set


# ── Enums ──────────────────────────────────────────────────────────


class TechniqueTier(str, Enum):
    TIER_1 = "tier_1"
    TIER_2 = "tier_2"
    TIER_3 = "tier_3"


class TechniqueID(str, Enum):
    # Tier 1 — Always Active
    CLARA = "clara"
    CRP = "crp"
    GSD = "gsd"

    # Tier 2 — Conditional
    CHAIN_OF_THOUGHT = "chain_of_thought"
    REVERSE_THINKING = "reverse_thinking"
    REACT = "react"
    STEP_BACK = "step_back"
    THREAD_OF_THOUGHT = "thread_of_thought"

    # Tier 3 — Premium
    GST = "gst"
    UNIVERSE_OF_THOUGHTS = "universe_of_thoughts"
    TREE_OF_THOUGHTS = "tree_of_thoughts"
    SELF_CONSISTENCY = "self_consistency"
    REFLEXION = "reflexion"
    LEAST_TO_MOST = "least_to_most"


class TriggerRuleID(str, Enum):
    R1_COMPLEXITY_GT_04 = "r1"
    R2_CONFIDENCE_LT_07 = "r2"
    R3_CUSTOMER_VIP = "r3"
    R4_SENTIMENT_LT_03 = "r4"
    R5_MONETARY_GT_100 = "r5"
    R6_TURNS_GT_5 = "r6"
    R7_EXTERNAL_DATA = "r7"
    R8_RESOLUTION_PATHS_GE_3 = "r8"
    R9_STRATEGIC_DECISION = "r9"
    R10_COMPLEXITY_GT_07 = "r10"
    R11_RESPONSE_REJECTED = "r11"
    R12_REASONING_LOOP = "r12"
    R13_INTENT_BILLING = "r13"
    R14_INTENT_TECHNICAL = "r14"


class CustomerTier(str, Enum):
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"
    VIP = "vip"


class ExecutionResultStatus(str, Enum):
    SUCCESS = "success"
    FALLBACK = "fallback"
    TIMEOUT = "timeout"
    ERROR = "error"
    SKIPPED_BUDGET = "skipped_budget"


# ── Token Budget ───────────────────────────────────────────────────


@dataclass(frozen=True)
class TokenBudget:
    """Token budget allocation for technique processing per model tier."""

    total: int
    tier1_reserve: int = 100
    tier2_pool: int = 0
    tier3_pool: int = 0

    def __post_init__(self):
        # tier2 gets up to 50% of remaining, tier3 gets the rest
        remaining = self.total - self.tier1_reserve
        t2 = min(remaining, int(remaining * 0.5))
        object.__setattr__(self, 'tier2_pool', t2)
        object.__setattr__(self, 'tier3_pool', remaining - t2)


# Pre-defined budgets per model tier
TOKEN_BUDGETS = {
    "light": TokenBudget(total=500),
    "medium": TokenBudget(total=1500),
    "heavy": TokenBudget(total=3000),
}


# ── Tier 3 → Tier 2 Fallback Mapping ─────────────────────────────

FALLBACK_MAP: Dict[TechniqueID, List[TechniqueID]] = {
    TechniqueID.GST: [TechniqueID.CHAIN_OF_THOUGHT],
    TechniqueID.UNIVERSE_OF_THOUGHTS: [
        TechniqueID.CHAIN_OF_THOUGHT, TechniqueID.STEP_BACK,
    ],
    TechniqueID.TREE_OF_THOUGHTS: [TechniqueID.CHAIN_OF_THOUGHT],
    TechniqueID.SELF_CONSISTENCY: [TechniqueID.CHAIN_OF_THOUGHT],
    TechniqueID.REFLEXION: [TechniqueID.STEP_BACK],
    TechniqueID.LEAST_TO_MOST: [
        TechniqueID.CHAIN_OF_THOUGHT, TechniqueID.THREAD_OF_THOUGHT,
    ],
}


# ── Technique Metadata ────────────────────────────────────────────


@dataclass
class TechniqueInfo:
    id: TechniqueID
    tier: TechniqueTier
    estimated_tokens: int
    time_budget_ms: int
    description: str


TECHNIQUE_REGISTRY: Dict[TechniqueID, TechniqueInfo] = {
    # Tier 1
    TechniqueID.CLARA: TechniqueInfo(
        id=TechniqueID.CLARA, tier=TechniqueTier.TIER_1,
        estimated_tokens=50, time_budget_ms=100,
        description="Concise Logical Adaptive Response Architecture — quality gate",
    ),
    TechniqueID.CRP: TechniqueInfo(
        id=TechniqueID.CRP, tier=TechniqueTier.TIER_1,
        estimated_tokens=30, time_budget_ms=50,
        description="Concise Response Protocol — token waste elimination",
    ),
    TechniqueID.GSD: TechniqueInfo(
        id=TechniqueID.GSD, tier=TechniqueTier.TIER_1,
        estimated_tokens=20, time_budget_ms=30,
        description="Guided Support Dialogue — state machine",
    ),
    # Tier 2
    TechniqueID.CHAIN_OF_THOUGHT: TechniqueInfo(
        id=TechniqueID.CHAIN_OF_THOUGHT, tier=TechniqueTier.TIER_2,
        estimated_tokens=350, time_budget_ms=3000,
        description="Chain of Thought — step-by-step reasoning",
    ),
    TechniqueID.REVERSE_THINKING: TechniqueInfo(
        id=TechniqueID.REVERSE_THINKING, tier=TechniqueTier.TIER_2,
        estimated_tokens=300, time_budget_ms=2000,
        description="Reverse Thinking — inversion-based reasoning",
    ),
    TechniqueID.REACT: TechniqueInfo(
        id=TechniqueID.REACT, tier=TechniqueTier.TIER_2,
        estimated_tokens=300, time_budget_ms=5000,
        description="ReAct — reasoning + acting with tool calls",
    ),
    TechniqueID.STEP_BACK: TechniqueInfo(
        id=TechniqueID.STEP_BACK, tier=TechniqueTier.TIER_2,
        estimated_tokens=300, time_budget_ms=1000,
        description="Step-Back Prompting — broader context seeking",
    ),
    TechniqueID.THREAD_OF_THOUGHT: TechniqueInfo(
        id=TechniqueID.THREAD_OF_THOUGHT, tier=TechniqueTier.TIER_2,
        estimated_tokens=150, time_budget_ms=500,
        description="Thread of Thought — multi-turn continuity",
    ),
    # Tier 3
    TechniqueID.GST: TechniqueInfo(
        id=TechniqueID.GST, tier=TechniqueTier.TIER_3,
        estimated_tokens=1100, time_budget_ms=8000,
        description="GST — Guided Sequential Thinking with checkpoints",
    ),
    TechniqueID.UNIVERSE_OF_THOUGHTS: TechniqueInfo(
        id=TechniqueID.UNIVERSE_OF_THOUGHTS, tier=TechniqueTier.TIER_3,
        estimated_tokens=1400, time_budget_ms=10000,
        description="UoT — multi-solution generation with evaluation matrix",
    ),
    TechniqueID.TREE_OF_THOUGHTS: TechniqueInfo(
        id=TechniqueID.TREE_OF_THOUGHTS, tier=TechniqueTier.TIER_3,
        estimated_tokens=1150, time_budget_ms=8000,
        description="ToT — branching decision tree with pruning",
    ),
    TechniqueID.SELF_CONSISTENCY: TechniqueInfo(
        id=TechniqueID.SELF_CONSISTENCY, tier=TechniqueTier.TIER_3,
        estimated_tokens=950, time_budget_ms=7000,
        description="Self-Consistency — multi-answer verification",
    ),
    TechniqueID.REFLEXION: TechniqueInfo(
        id=TechniqueID.REFLEXION, tier=TechniqueTier.TIER_3,
        estimated_tokens=400, time_budget_ms=3000,
        description="Reflexion — self-correction engine",
    ),
    TechniqueID.LEAST_TO_MOST: TechniqueInfo(
        id=TechniqueID.LEAST_TO_MOST, tier=TechniqueTier.TIER_3,
        estimated_tokens=1050, time_budget_ms=8000,
        description="Least-to-Most — complex query decomposition",
    ),
}


# ── Query Signals ──────────────────────────────────────────────────


@dataclass
class QuerySignals:
    """Input signals extracted for the Technique Router decision."""

    query_complexity: float = 0.0          # F-062, range 0.0-1.0
    confidence_score: float = 1.0          # F-059, range 0.0-1.0
    sentiment_score: float = 0.7           # F-063, range 0.0-1.0
    frustration_score: float = 0.0         # Frustration level, range 0.0-100.0
    customer_tier: str = "free"            # Free/Pro/Enterprise/VIP
    monetary_value: float = 0.0            # $0.00+
    turn_count: int = 0                    # 0+
    intent_type: str = "general"           # billing/technical/general/etc.
    previous_response_status: str = "none"  # accepted/rejected/corrected/none
    reasoning_loop_detected: bool = False
    resolution_path_count: int = 1         # 1+
    external_data_required: bool = False
    is_strategic_decision: bool = False


# ── Trigger Rules ──────────────────────────────────────────────────


@dataclass
class TriggerRule:
    rule_id: TriggerRuleID
    evaluate: callable  # noqa: E731
    activates: List[TechniqueID]
    tier: TechniqueTier


TRIGGER_RULES: List[TriggerRule] = [
    TriggerRule(
        rule_id=TriggerRuleID.R1_COMPLEXITY_GT_04,
        evaluate=lambda s: s.query_complexity > 0.4,
        activates=[TechniqueID.CHAIN_OF_THOUGHT],
        tier=TechniqueTier.TIER_2,
    ),
    TriggerRule(
        rule_id=TriggerRuleID.R2_CONFIDENCE_LT_07,
        evaluate=lambda s: s.confidence_score < 0.7,
        activates=[TechniqueID.REVERSE_THINKING, TechniqueID.STEP_BACK],
        tier=TechniqueTier.TIER_2,
    ),
    TriggerRule(
        rule_id=TriggerRuleID.R3_CUSTOMER_VIP,
        evaluate=lambda s: s.customer_tier == "vip",
        activates=[
            TechniqueID.UNIVERSE_OF_THOUGHTS, TechniqueID.REFLEXION,
        ],
        tier=TechniqueTier.TIER_3,
    ),
    TriggerRule(
        rule_id=TriggerRuleID.R4_SENTIMENT_LT_03,
        evaluate=lambda s: s.sentiment_score < 0.3,
        activates=[
            TechniqueID.UNIVERSE_OF_THOUGHTS, TechniqueID.STEP_BACK,
        ],
        tier=TechniqueTier.TIER_3,
    ),
    TriggerRule(
        rule_id=TriggerRuleID.R5_MONETARY_GT_100,
        evaluate=lambda s: s.monetary_value > 100,
        activates=[TechniqueID.SELF_CONSISTENCY],
        tier=TechniqueTier.TIER_3,
    ),
    TriggerRule(
        rule_id=TriggerRuleID.R6_TURNS_GT_5,
        evaluate=lambda s: s.turn_count > 5,
        activates=[TechniqueID.THREAD_OF_THOUGHT],
        tier=TechniqueTier.TIER_2,
    ),
    TriggerRule(
        rule_id=TriggerRuleID.R7_EXTERNAL_DATA,
        evaluate=lambda s: s.external_data_required,
        activates=[TechniqueID.REACT],
        tier=TechniqueTier.TIER_2,
    ),
    TriggerRule(
        rule_id=TriggerRuleID.R8_RESOLUTION_PATHS_GE_3,
        evaluate=lambda s: s.resolution_path_count >= 3,
        activates=[TechniqueID.TREE_OF_THOUGHTS],
        tier=TechniqueTier.TIER_3,
    ),
    TriggerRule(
        rule_id=TriggerRuleID.R9_STRATEGIC_DECISION,
        evaluate=lambda s: s.is_strategic_decision,
        activates=[TechniqueID.GST],
        tier=TechniqueTier.TIER_3,
    ),
    TriggerRule(
        rule_id=TriggerRuleID.R10_COMPLEXITY_GT_07,
        evaluate=lambda s: s.query_complexity > 0.7,
        activates=[TechniqueID.LEAST_TO_MOST],
        tier=TechniqueTier.TIER_3,
    ),
    TriggerRule(
        rule_id=TriggerRuleID.R11_RESPONSE_REJECTED,
        evaluate=lambda s: s.previous_response_status in ("rejected", "corrected"),
        activates=[TechniqueID.REFLEXION],
        tier=TechniqueTier.TIER_3,
    ),
    TriggerRule(
        rule_id=TriggerRuleID.R12_REASONING_LOOP,
        evaluate=lambda s: s.reasoning_loop_detected,
        activates=[TechniqueID.STEP_BACK],
        tier=TechniqueTier.TIER_2,
    ),
    TriggerRule(
        rule_id=TriggerRuleID.R13_INTENT_BILLING,
        evaluate=lambda s: s.intent_type == "billing",
        activates=[TechniqueID.SELF_CONSISTENCY],
        tier=TechniqueTier.TIER_3,
    ),
    TriggerRule(
        rule_id=TriggerRuleID.R14_INTENT_TECHNICAL,
        evaluate=lambda s: s.intent_type == "technical",
        activates=[TechniqueID.CHAIN_OF_THOUGHT, TechniqueID.REACT],
        tier=TechniqueTier.TIER_2,
    ),
]


# ── Router Result ──────────────────────────────────────────────────


@dataclass
class TechniqueActivation:
    technique_id: TechniqueID
    triggered_by: List[str]  # rule IDs
    tier: TechniqueTier


@dataclass
class RouterResult:
    """Output of the Technique Router for a single query."""

    activated_techniques: List[TechniqueActivation] = field(
        default_factory=list)
    skipped_techniques: List[Dict[str, Any]] = field(default_factory=list)
    trigger_rules_evaluated: int = 0
    trigger_rules_matched: int = 0
    total_estimated_tokens: int = 0
    total_estimated_time_ms: int = 0
    model_tier: str = "medium"
    budget: Optional[TokenBudget] = None
    fallback_applied: bool = False


# ── Technique Router ───────────────────────────────────────────────


class TechniqueRouter:
    """
    The Technique Router (BC-013) analyzes query signals and determines
    which reasoning technique(s) should activate.

    Execution order: Tier 1 → Tier 2 → Tier 3 (always, in that order).
    Deduplication: same technique triggered by multiple rules = runs once.
    """

    def __init__(
        self,
        model_tier: str = "medium",
        enabled_techniques: Optional[Set[TechniqueID]] = None,
    ):
        self.model_tier = model_tier
        self.budget = TOKEN_BUDGETS.get(model_tier, TOKEN_BUDGETS["medium"])
        self.enabled_techniques = enabled_techniques  # None = all enabled

    def route(self, signals: QuerySignals) -> RouterResult:
        """
        Main entry point. Evaluates all trigger rules, compiles
        activated techniques, deduplicates, checks budget, and returns
        the execution plan.
        """
        result = RouterResult(
            model_tier=self.model_tier,
            budget=self.budget,
        )

        # 1. Always activate Tier 1 techniques
        t1_techniques = [
            TechniqueID.CLARA, TechniqueID.CRP, TechniqueID.GSD,
        ]
        for tid in t1_techniques:
            result.activated_techniques.append(
                TechniqueActivation(
                    technique_id=tid,
                    triggered_by=["always_active_tier_1"],
                    tier=TechniqueTier.TIER_1,
                )
            )

        # 2. Evaluate trigger rules for Tier 2 and Tier 3
        activated_map: Dict[TechniqueID, List[str]] = {}

        for rule in TRIGGER_RULES:
            result.trigger_rules_evaluated += 1
            if rule.evaluate(signals):
                result.trigger_rules_matched += 1
                for tid in rule.activates:
                    if tid not in activated_map:
                        activated_map[tid] = []
                    activated_map[tid].append(rule.rule_id.value)

        # 3. Add activated techniques in tier order
        for tid, rules in activated_map.items():
            info = TECHNIQUE_REGISTRY.get(tid)
            if info is None:
                continue
            if self.enabled_techniques is not None and tid not in self.enabled_techniques:
                result.skipped_techniques.append({
                    "technique_id": tid.value,
                    "reason": "disabled_by_tenant_config",
                })
                continue
            result.activated_techniques.append(
                TechniqueActivation(
                    technique_id=tid,
                    triggered_by=rules,
                    tier=info.tier,
                )
            )

        # 4. Calculate totals
        for activation in result.activated_techniques:
            info = TECHNIQUE_REGISTRY[activation.technique_id]
            result.total_estimated_tokens += info.estimated_tokens
            result.total_estimated_time_ms += info.time_budget_ms

        # 5. Budget check — fallback T3 → T2 if over budget
        if result.total_estimated_tokens > self.budget.total:
            result = self._apply_fallback(result)

        return result

    def _apply_fallback(self, result: RouterResult) -> RouterResult:
        """
        If total tokens exceed budget, replace Tier 3 techniques
        with their Tier 2 fallback equivalents.
        """
        result.fallback_applied = True
        new_activations: List[TechniqueActivation] = []
        new_skipped: List[Dict[str, Any]] = list(result.skipped_techniques)
        savings = 0

        for activation in result.activated_techniques:
            if activation.tier == TechniqueTier.TIER_3:
                fallbacks = FALLBACK_MAP.get(activation.technique_id, [])
                original_tokens = TECHNIQUE_REGISTRY[activation.technique_id].estimated_tokens

                # Check if adding fallbacks would fit
                fallback_tokens = sum(
                    TECHNIQUE_REGISTRY[f].estimated_tokens for f in fallbacks
                    if f in TECHNIQUE_REGISTRY
                )

                if savings + original_tokens - fallback_tokens >= 0:
                    savings += original_tokens - fallback_tokens
                    for fb_tid in fallbacks:
                        fb_info = TECHNIQUE_REGISTRY.get(fb_tid)
                        if fb_info:
                            new_activations.append(
                                TechniqueActivation(
                                    technique_id=fb_tid,
                                    triggered_by=[
                                        f"fallback_from_{
                                            activation.technique_id.value}"],
                                    tier=TechniqueTier.TIER_2,
                                ))
                    new_skipped.append({
                        "technique_id": activation.technique_id.value,
                        "reason": "token_budget_exceeded",
                        "fallback_to": [f.value for f in fallbacks],
                    })
                else:
                    # Can't even fit fallback — skip entirely
                    new_skipped.append({
                        "technique_id": activation.technique_id.value,
                        "reason": "token_budget_exceeded_no_fallback",
                    })
                    savings += original_tokens
            else:
                new_activations.append(activation)

        result.activated_techniques = new_activations
        result.skipped_techniques = new_skipped

        # Recalculate totals
        result.total_estimated_tokens = sum(
            TECHNIQUE_REGISTRY[a.technique_id].estimated_tokens
            for a in result.activated_techniques
        )
        result.total_estimated_time_ms = sum(
            TECHNIQUE_REGISTRY[a.technique_id].time_budget_ms
            for a in result.activated_techniques
        )

        return result

    @staticmethod
    def get_available_techniques_for_plan(plan: str) -> Set[TechniqueID]:
        """Return available techniques based on tenant plan."""
        tier_1 = {TechniqueID.CLARA, TechniqueID.CRP, TechniqueID.GSD}
        tier_2 = {
            TechniqueID.CHAIN_OF_THOUGHT, TechniqueID.REVERSE_THINKING,
            TechniqueID.REACT, TechniqueID.STEP_BACK,
            TechniqueID.THREAD_OF_THOUGHT,
        }
        tier_3 = {
            TechniqueID.GST, TechniqueID.UNIVERSE_OF_THOUGHTS,
            TechniqueID.TREE_OF_THOUGHTS, TechniqueID.SELF_CONSISTENCY,
            TechniqueID.REFLEXION, TechniqueID.LEAST_TO_MOST,
        }

        if plan in ("enterprise", "vip"):
            return tier_1 | tier_2 | tier_3
        elif plan == "pro":
            return tier_1 | tier_2
        return tier_1
