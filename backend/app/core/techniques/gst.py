"""
F-143: GST (Guided Sequential Thinking) — Tier 3 Premium AI Reasoning Technique

Activates when state.signals.is_strategic_decision == True. Uses deterministic
heuristic-based sequential analysis (no LLM calls) to guide strategic decisions:

  1. Problem Definition — Define the strategic decision clearly
  2. Option Generation — Generate possible approaches
  3. Impact Analysis — Evaluate each option on multiple dimensions
  4. Risk Assessment — Identify risks per option
  5. Recommendation — Select best option with justification

Performance target: ~1100 tokens, sub-8000ms processing.

Building Codes: BC-001 (company isolation), BC-008 (never crash),
               BC-012 (graceful degradation)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, FrozenSet, List, Optional, Set, Tuple

from app.core.technique_router import TechniqueID
from app.core.techniques.base import (
    BaseTechniqueNode,
    ConversationState,
)
from app.logger import get_logger

logger = get_logger("gst")


# ── Enums ─────────────────────────────────────────────────────────────


class DecisionScope(str, Enum):
    """Categories of strategic decisions."""
    CONTRACT_MODIFICATION = "contract_modification"
    FEATURE_REQUEST = "feature_request"
    POLICY_CHANGE = "policy_change"
    ESCALATION = "escalation"
    PRICING = "pricing"
    GENERAL = "general"


class RiskCategory(str, Enum):
    """Risk categories for option evaluation."""
    COMPLIANCE = "compliance"
    CUSTOMER_CHURN = "customer_churn"
    FINANCIAL = "financial"
    OPERATIONAL = "operational"


class RiskSeverity(str, Enum):
    """Risk severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ── Scope Pattern Matching ────────────────────────────────────────────


_SCOPE_PATTERNS: List[Tuple[re.Pattern, DecisionScope]] = [
    (re.compile(r"\b(contract|amendment|modify|renew|terminate|sla|agreement|terms)\b", re.I),
     DecisionScope.CONTRACT_MODIFICATION),
    (re.compile(r"\b(feature|request|enhancement|addition|capability|functionality|roadmap)\b", re.I),
     DecisionScope.FEATURE_REQUEST),
    (re.compile(r"\b(policy|compliance|regulation|standard|guideline|procedure|rule)\b", re.I),
     DecisionScope.POLICY_CHANGE),
    (re.compile(r"\b(escalat|urgent|priority|management|supervisor|senior|executive)\b", re.I),
     DecisionScope.ESCALATION),
    (re.compile(r"\b(pric(e|ing|e\s*change)|discount|surcharge|tier|plan\s*cost|rate|fee)\b", re.I),
     DecisionScope.PRICING),
]

_DEFAULT_SCOPE = DecisionScope.GENERAL


# ── Stakeholder Templates ─────────────────────────────────────────────

_SCOPE_STAKEHOLDERS: Dict[DecisionScope, List[str]] = {
    DecisionScope.CONTRACT_MODIFICATION: [
        "customer", "company", "legal", "finance",
    ],
    DecisionScope.FEATURE_REQUEST: [
        "customer", "product", "engineering", "support",
    ],
    DecisionScope.POLICY_CHANGE: [
        "customer", "company", "legal", "compliance",
    ],
    DecisionScope.ESCALATION: [
        "customer", "support", "management", "engineering",
    ],
    DecisionScope.PRICING: [
        "customer", "finance", "sales", "product",
    ],
    DecisionScope.GENERAL: [
        "customer", "company",
    ],
}


# ── Constraint Templates ──────────────────────────────────────────────

_SCOPE_CONSTRAINTS: Dict[DecisionScope, List[str]] = {
    DecisionScope.CONTRACT_MODIFICATION: [
        "timeline", "budget", "existing terms", "legal requirements",
    ],
    DecisionScope.FEATURE_REQUEST: [
        "development capacity", "timeline", "technical feasibility", "budget",
    ],
    DecisionScope.POLICY_CHANGE: [
        "regulatory requirements", "communication timeline", "customer impact",
    ],
    DecisionScope.ESCALATION: [
        "response timeline", "resolution SLA", "available resources",
    ],
    DecisionScope.PRICING: [
        "market conditions", "contract lock-in", "competitive landscape", "budget",
    ],
    DecisionScope.GENERAL: [
        "timeline", "budget", "resources",
    ],
}


# ── Option Generation Templates ───────────────────────────────────────


_SCOPE_OPTIONS: Dict[DecisionScope, List[Dict[str, Any]]] = {
    DecisionScope.CONTRACT_MODIFICATION: [
        {
            "description": "Approve the contract modification as requested by the customer.",
            "base_scores": {
                "customer_satisfaction": 0.9,
                "cost_impact": 0.3,
                "policy_compliance": 0.5,
                "implementation_feasibility": 0.7,
            },
            "risks": [
                {"category": RiskCategory.FINANCIAL, "severity": RiskSeverity.MEDIUM,
                 "description": "Potential revenue loss from modified terms."},
                {"category": RiskCategory.COMPLIANCE, "severity": RiskSeverity.LOW,
                 "description": "Modification must be documented per policy."},
            ],
        },
        {
            "description": "Propose a counter-offer with adjusted terms balancing both parties.",
            "base_scores": {
                "customer_satisfaction": 0.7,
                "cost_impact": 0.6,
                "policy_compliance": 0.8,
                "implementation_feasibility": 0.6,
            },
            "risks": [
                {"category": RiskCategory.CUSTOMER_CHURN, "severity": RiskSeverity.MEDIUM,
                 "description": "Customer may reject counter-offer."},
            ],
        },
        {
            "description": "Maintain current contract terms with no modifications.",
            "base_scores": {
                "customer_satisfaction": 0.3,
                "cost_impact": 0.9,
                "policy_compliance": 1.0,
                "implementation_feasibility": 1.0,
            },
            "risks": [
                {"category": RiskCategory.CUSTOMER_CHURN, "severity": RiskSeverity.HIGH,
                 "description": "Customer may churn if modification is important to them."},
            ],
        },
    ],
    DecisionScope.FEATURE_REQUEST: [
        {
            "description": "Add the requested feature to the product roadmap for next release.",
            "base_scores": {
                "customer_satisfaction": 0.95,
                "cost_impact": 0.4,
                "policy_compliance": 0.8,
                "implementation_feasibility": 0.5,
            },
            "risks": [
                {"category": RiskCategory.OPERATIONAL, "severity": RiskSeverity.MEDIUM,
                 "description": "Development resource allocation may impact other features."},
                {"category": RiskCategory.FINANCIAL, "severity": RiskSeverity.LOW,
                 "description": "Development cost for the new feature."},
            ],
        },
        {
            "description": "Add the feature to the backlog with a future timeline estimate.",
            "base_scores": {
                "customer_satisfaction": 0.6,
                "cost_impact": 0.7,
                "policy_compliance": 0.9,
                "implementation_feasibility": 0.8,
            },
            "risks": [
                {"category": RiskCategory.CUSTOMER_CHURN, "severity": RiskSeverity.LOW,
                 "description": "Customer may be dissatisfied with the wait."},
            ],
        },
        {
            "description": "Provide an existing workaround or alternative that addresses the need.",
            "base_scores": {
                "customer_satisfaction": 0.5,
                "cost_impact": 0.9,
                "policy_compliance": 1.0,
                "implementation_feasibility": 0.9,
            },
            "risks": [
                {"category": RiskCategory.CUSTOMER_CHURN, "severity": RiskSeverity.MEDIUM,
                 "description": "Workaround may not fully meet customer expectations."},
            ],
        },
    ],
    DecisionScope.POLICY_CHANGE: [
        {
            "description": "Implement the policy change as requested with full rollout.",
            "base_scores": {
                "customer_satisfaction": 0.7,
                "cost_impact": 0.5,
                "policy_compliance": 0.9,
                "implementation_feasibility": 0.6,
            },
            "risks": [
                {"category": RiskCategory.COMPLIANCE, "severity": RiskSeverity.MEDIUM,
                 "description": "Must verify regulatory alignment of new policy."},
                {"category": RiskCategory.OPERATIONAL, "severity": RiskSeverity.LOW,
                 "description": "Staff training required for new policy."},
            ],
        },
        {
            "description": "Implement a phased policy change with gradual rollout and feedback.",
            "base_scores": {
                "customer_satisfaction": 0.8,
                "cost_impact": 0.6,
                "policy_compliance": 0.8,
                "implementation_feasibility": 0.7,
            },
            "risks": [
                {"category": RiskCategory.OPERATIONAL, "severity": RiskSeverity.LOW,
                 "description": "Phased approach requires extended coordination."},
            ],
        },
        {
            "description": "Maintain current policy with enhanced communication to customers.",
            "base_scores": {
                "customer_satisfaction": 0.4,
                "cost_impact": 0.8,
                "policy_compliance": 1.0,
                "implementation_feasibility": 0.9,
            },
            "risks": [
                {"category": RiskCategory.CUSTOMER_CHURN, "severity": RiskSeverity.MEDIUM,
                 "description": "Customers expecting change may be dissatisfied."},
            ],
        },
    ],
    DecisionScope.ESCALATION: [
        {
            "description": "Immediate escalation to senior management with full context.",
            "base_scores": {
                "customer_satisfaction": 0.85,
                "cost_impact": 0.5,
                "policy_compliance": 0.7,
                "implementation_feasibility": 0.9,
            },
            "risks": [
                {"category": RiskCategory.OPERATIONAL, "severity": RiskSeverity.LOW,
                 "description": "Senior management availability may affect response time."},
            ],
        },
        {
            "description": "Attempt front-line resolution first, escalate if unresolved within SLA.",
            "base_scores": {
                "customer_satisfaction": 0.6,
                "cost_impact": 0.7,
                "policy_compliance": 0.9,
                "implementation_feasibility": 0.7,
            },
            "risks": [
                {"category": RiskCategory.CUSTOMER_CHURN, "severity": RiskSeverity.MEDIUM,
                 "description": "Delayed escalation may increase customer frustration."},
                {"category": RiskCategory.COMPLIANCE, "severity": RiskSeverity.LOW,
                 "description": "Must still escalate if SLA-breach risk exists."},
            ],
        },
        {
            "description": "Engage cross-functional team for collaborative resolution.",
            "base_scores": {
                "customer_satisfaction": 0.8,
                "cost_impact": 0.4,
                "policy_compliance": 0.8,
                "implementation_feasibility": 0.5,
            },
            "risks": [
                {"category": RiskCategory.OPERATIONAL, "severity": RiskSeverity.MEDIUM,
                 "description": "Cross-functional coordination may slow initial response."},
                {"category": RiskCategory.FINANCIAL, "severity": RiskSeverity.LOW,
                 "description": "Additional resource allocation required."},
            ],
        },
    ],
    DecisionScope.PRICING: [
        {
            "description": "Apply the requested pricing adjustment for the customer.",
            "base_scores": {
                "customer_satisfaction": 0.9,
                "cost_impact": 0.3,
                "policy_compliance": 0.5,
                "implementation_feasibility": 0.8,
            },
            "risks": [
                {"category": RiskCategory.FINANCIAL, "severity": RiskSeverity.HIGH,
                 "description": "Revenue impact from pricing adjustment."},
                {"category": RiskCategory.COMPLIANCE, "severity": RiskSeverity.MEDIUM,
                 "description": "Must verify pricing change aligns with policy limits."},
            ],
        },
        {
            "description": "Offer a temporary promotional pricing with defined end date.",
            "base_scores": {
                "customer_satisfaction": 0.8,
                "cost_impact": 0.5,
                "policy_compliance": 0.7,
                "implementation_feasibility": 0.7,
            },
            "risks": [
                {"category": RiskCategory.FINANCIAL, "severity": RiskSeverity.MEDIUM,
                 "description": "Temporary discount may set pricing expectations."},
            ],
        },
        {
            "description": "Maintain current pricing with value-add justification.",
            "base_scores": {
                "customer_satisfaction": 0.4,
                "cost_impact": 0.9,
                "policy_compliance": 1.0,
                "implementation_feasibility": 0.9,
            },
            "risks": [
                {"category": RiskCategory.CUSTOMER_CHURN, "severity": RiskSeverity.HIGH,
                 "description": "Customer may churn due to pricing concerns."},
            ],
        },
    ],
    DecisionScope.GENERAL: [
        {
            "description": "Approve the request and proceed with standard implementation.",
            "base_scores": {
                "customer_satisfaction": 0.8,
                "cost_impact": 0.6,
                "policy_compliance": 0.8,
                "implementation_feasibility": 0.7,
            },
            "risks": [
                {"category": RiskCategory.OPERATIONAL, "severity": RiskSeverity.LOW,
                 "description": "Standard implementation may require additional resources."},
            ],
        },
        {
            "description": "Review the request with stakeholders before making a decision.",
            "base_scores": {
                "customer_satisfaction": 0.5,
                "cost_impact": 0.8,
                "policy_compliance": 0.9,
                "implementation_feasibility": 0.8,
            },
            "risks": [
                {"category": RiskCategory.CUSTOMER_CHURN, "severity": RiskSeverity.LOW,
                 "description": "Delay in response may affect customer satisfaction."},
            ],
        },
        {
            "description": "Deny the request and explain the reasoning clearly to the customer.",
            "base_scores": {
                "customer_satisfaction": 0.2,
                "cost_impact": 0.9,
                "policy_compliance": 1.0,
                "implementation_feasibility": 1.0,
            },
            "risks": [
                {"category": RiskCategory.CUSTOMER_CHURN, "severity": RiskSeverity.HIGH,
                 "description": "Denial may lead to customer churn."},
            ],
        },
    ],
}


# ── Impact Score Weights ──────────────────────────────────────────────

_DEFAULT_WEIGHTS: Dict[str, float] = {
    "customer_satisfaction": 0.35,
    "cost_impact": 0.25,
    "policy_compliance": 0.25,
    "implementation_feasibility": 0.15,
}


# ── Data Structures ──────────────────────────────────────────────────


@dataclass(frozen=True)
class GSTConfig:
    """
    Immutable configuration for GST processing (BC-001).

    Attributes:
        company_id: Tenant identifier for company isolation.
        max_options: Maximum number of options to generate per decision.
        risk_threshold: Threshold (0-1) above which risk score blocks recommendation.
    """

    company_id: str = ""
    max_options: int = 5
    risk_threshold: float = 0.7


@dataclass
class GSTCheckpoint:
    """
    A single checkpoint in the GST sequential thinking pipeline.

    Attributes:
        checkpoint_number: Sequential number (1-5).
        name: Human-readable checkpoint name.
        result: Checkpoint output data.
    """

    checkpoint_number: int = 0
    name: str = ""
    result: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize checkpoint to dictionary."""
        return {
            "checkpoint_number": self.checkpoint_number,
            "name": self.name,
            "result": self.result,
        }


@dataclass
class GSTOption:
    """
    A single option generated for the strategic decision.

    Attributes:
        option_id: Unique identifier for this option.
        description: Human-readable description of the approach.
        impact_scores: Dict of dimension scores (0-1).
        risks: List of risk assessments for this option.
        total_score: Weighted total impact score.
    """

    option_id: str = ""
    description: str = ""
    impact_scores: Dict[str, float] = field(default_factory=dict)
    risks: List[Dict[str, Any]] = field(default_factory=list)
    total_score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Serialize option to dictionary."""
        return {
            "option_id": self.option_id,
            "description": self.description,
            "impact_scores": self.impact_scores,
            "risks": self.risks,
            "total_score": round(self.total_score, 4),
        }


@dataclass
class GSTResult:
    """
    Output of the full GST pipeline.

    Attributes:
        problem_definition: Dict with scope, stakeholders, constraints.
        options: List of GSTOption objects evaluated.
        recommendation: Best option selected with rationale.
        checkpoints: List of GSTCheckpoint objects for the pipeline.
        steps_applied: Names of pipeline steps that were executed.
        risk_summary: Consolidated risk information.
    """

    problem_definition: Dict[str, Any] = field(default_factory=dict)
    options: List[GSTOption] = field(default_factory=list)
    recommendation: Dict[str, Any] = field(default_factory=dict)
    checkpoints: List[GSTCheckpoint] = field(default_factory=list)
    steps_applied: List[str] = field(default_factory=list)
    risk_summary: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize result to dictionary for recording in state."""
        return {
            "problem_definition": self.problem_definition,
            "options": [o.to_dict() for o in self.options],
            "recommendation": self.recommendation,
            "checkpoints": [c.to_dict() for c in self.checkpoints],
            "steps_applied": self.steps_applied,
            "risk_summary": self.risk_summary,
        }


# ── GST Processor ────────────────────────────────────────────────────


class GSTProcessor:
    """
    Deterministic Guided Sequential Thinking processor (F-143).

    Uses pattern matching and heuristic rules to simulate structured
    sequential analysis without any LLM calls.

    Pipeline:
      1. Problem Definition  — scope, stakeholders, constraints
      2. Option Generation   — template-based option generation
      3. Impact Analysis     — weighted scoring across dimensions
      4. Risk Assessment     — risk identification and severity
      5. Recommendation      — best option selection with justification
    """

    def __init__(
        self, config: Optional[GSTConfig] = None,
    ):
        self.config = config or GSTConfig()

    # ── Step 1: Problem Definition ──────────────────────────────────

    async def define_problem(self, query: str) -> Dict[str, Any]:
        """
        Define the strategic decision clearly.

        Identifies decision scope, extracts stakeholders, and determines
        constraints using pattern matching and template-based analysis.

        Args:
            query: The customer query text.

        Returns:
            Dict with scope, stakeholders, and constraints.
        """
        if not query or not query.strip():
            return {}

        scope = self._classify_scope(query)
        stakeholders = _SCOPE_STAKEHOLDERS.get(scope, _SCOPE_STAKEHOLDERS[DecisionScope.GENERAL])
        constraints = _SCOPE_CONSTRAINTS.get(scope, _SCOPE_CONSTRAINTS[DecisionScope.GENERAL])

        return {
            "scope": scope.value,
            "description": f"Strategic decision: {query}",
            "stakeholders": stakeholders,
            "constraints": constraints,
        }

    # ── Step 2: Option Generation ───────────────────────────────────

    async def generate_options(
        self,
        scope: DecisionScope,
    ) -> List[GSTOption]:
        """
        Generate possible approaches for the decision.

        Uses template-based option generation per decision scope.
        Returns at least 2-3 options per decision type.

        Args:
            scope: The classified decision scope.

        Returns:
            List of GSTOption objects with base scores and risks.
        """
        templates = _SCOPE_OPTIONS.get(scope, _SCOPE_OPTIONS[DecisionScope.GENERAL])

        # Limit by max_options config
        selected = templates[: self.config.max_options]

        options: List[GSTOption] = []
        for idx, template in enumerate(selected, start=1):
            option = GSTOption(
                option_id=f"{scope.value}_opt_{idx}",
                description=template["description"],
                impact_scores=dict(template["base_scores"]),
                risks=list(template["risks"]),
                total_score=0.0,
            )
            options.append(option)

        return options

    # ── Step 3: Impact Analysis ─────────────────────────────────────

    async def analyze_impact(
        self,
        options: List[GSTOption],
        weights: Optional[Dict[str, float]] = None,
    ) -> List[GSTOption]:
        """
        Evaluate each option using weighted scoring.

        Score each option on: customer_satisfaction (0-1),
        cost_impact (0-1), policy_compliance (0-1),
        implementation_feasibility (0-1). Calculate weighted total.

        Args:
            options: List of GSTOption objects to evaluate.
            weights: Optional custom weights. Uses defaults if None.

        Returns:
            Updated list of GSTOption objects with total_score calculated.
        """
        w = weights or _DEFAULT_WEIGHTS

        for option in options:
            total = 0.0
            for dimension, weight in w.items():
                score = option.impact_scores.get(dimension, 0.0)
                total += score * weight
            option.total_score = round(total, 4)

        return options

    # ── Step 4: Risk Assessment ─────────────────────────────────────

    async def assess_risks(
        self,
        options: List[GSTOption],
    ) -> Dict[str, Any]:
        """
        Identify and evaluate risks per option.

        Risk categories: compliance, customer_churn, financial, operational.
        Risk severity: low/medium/high/critical.

        Args:
            options: List of GSTOption objects with associated risks.

        Returns:
            Risk summary dict with per-option and overall risk assessment.
        """
        severity_order = {
            RiskSeverity.LOW: 1,
            RiskSeverity.MEDIUM: 2,
            RiskSeverity.HIGH: 3,
            RiskSeverity.CRITICAL: 4,
        }

        option_risks: List[Dict[str, Any]] = []
        overall_max_severity = RiskSeverity.LOW
        overall_risk_categories: Set[str] = set()

        for option in options:
            if not option.risks:
                option_risks.append({
                    "option_id": option.option_id,
                    "risk_count": 0,
                    "max_severity": "none",
                    "risk_score": 0.0,
                })
                continue

            max_sev = RiskSeverity.LOW
            risk_score = 0.0

            for risk in option.risks:
                cat = risk.get("category", "")
                sev = risk.get("severity", RiskSeverity.LOW)

                if isinstance(cat, RiskCategory):
                    cat = cat.value
                if isinstance(sev, RiskSeverity):
                    sev = sev.value
                    sev_enum = RiskSeverity(sev)
                else:
                    sev_enum = RiskSeverity(sev)

                if severity_order.get(sev_enum, 0) > severity_order.get(max_sev, 0):
                    max_sev = sev_enum

                risk_score += severity_order.get(sev_enum, 0) * 0.25
                overall_risk_categories.add(str(cat))

            risk_score = min(risk_score, 1.0)

            if severity_order.get(max_sev, 0) > severity_order.get(overall_max_severity, 0):
                overall_max_severity = max_sev

            option_risks.append({
                "option_id": option.option_id,
                "risk_count": len(option.risks),
                "max_severity": max_sev.value if isinstance(max_sev, RiskSeverity) else str(max_sev),
                "risk_score": round(risk_score, 4),
            })

        return {
            "per_option": option_risks,
            "overall_max_severity": overall_max_severity.value if isinstance(overall_max_severity, RiskSeverity) else str(overall_max_severity),
            "risk_categories": sorted(overall_risk_categories),
            "overall_risk_score": round(
                max((r["risk_score"] for r in option_risks), default=0.0),
                4,
            ),
        }

    # ── Step 5: Recommendation ──────────────────────────────────────

    async def recommend(
        self,
        options: List[GSTOption],
        risk_summary: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Select the best option with structured justification.

        Picks the highest-scored option that passes the risk threshold.
        Generates a structured recommendation with rationale.

        Args:
            options: List of scored GSTOption objects.
            risk_summary: Risk assessment output from assess_risks().

        Returns:
            Recommendation dict with selected option and rationale.
        """
        if not options:
            return {
                "selected_option": None,
                "rationale": "No options available for recommendation.",
            }

        # Build risk score lookup
        risk_lookup: Dict[str, float] = {}
        for orisk in risk_summary.get("per_option", []):
            risk_lookup[orisk["option_id"]] = orisk["risk_score"]

        # Filter options that pass risk threshold
        safe_options = [
            o for o in options
            if (1.0 - risk_lookup.get(o.option_id, 0.0)) >= self.config.risk_threshold
        ]

        # If no safe options, pick the one with lowest risk
        if not safe_options:
            safe_options = options[:]
            fallback_reason = (
                "No option met the risk threshold; "
                "recommending the highest-scored option."
            )
        else:
            fallback_reason = ""

        # Sort by total_score descending
        safe_options.sort(key=lambda o: o.total_score, reverse=True)
        best = safe_options[0]

        # Build rationale
        rationale_parts = [
            f"Selected option '{best.option_id}' with the highest weighted "
            f"score of {best.total_score:.2f}.",
        ]

        if fallback_reason:
            rationale_parts.append(f"Note: {fallback_reason}")

        # Add top scoring dimensions
        sorted_dims = sorted(
            best.impact_scores.items(),
            key=lambda x: x[1],
            reverse=True,
        )
        if sorted_dims:
            top_dim, top_val = sorted_dims[0]
            rationale_parts.append(
                f"Strongest dimension: {top_dim} ({top_val:.2f})."
            )

        # Add risk info
        risk_info = risk_lookup.get(best.option_id, 0.0)
        rationale_parts.append(f"Risk score: {risk_info:.2f}.")

        return {
            "selected_option": best.to_dict(),
            "rationale": " ".join(rationale_parts),
        }

    # ── Full Pipeline ──────────────────────────────────────────────

    async def process(
        self, query: str,
    ) -> GSTResult:
        """
        Run the full 5-checkpoint GST pipeline.

        Args:
            query: The strategic decision query.

        Returns:
            GSTResult with all pipeline outputs.
        """
        checkpoints: List[GSTCheckpoint] = []
        steps_applied: List[str] = []

        if not query or not query.strip():
            return GSTResult(
                steps_applied=["empty_input"],
            )

        try:
            # Checkpoint 1: Problem Definition
            problem_definition = await self.define_problem(query)
            checkpoint1 = GSTCheckpoint(
                checkpoint_number=1,
                name="problem_definition",
                result=problem_definition,
            )
            checkpoints.append(checkpoint1)
            if problem_definition:
                steps_applied.append("problem_definition")

            # Checkpoint 2: Option Generation
            scope = DecisionScope(problem_definition.get("scope", "general"))
            options = await self.generate_options(scope)
            checkpoint2 = GSTCheckpoint(
                checkpoint_number=2,
                name="option_generation",
                result={
                    "scope": scope.value,
                    "options_generated": len(options),
                },
            )
            checkpoints.append(checkpoint2)
            if options:
                steps_applied.append("option_generation")

            # Checkpoint 3: Impact Analysis
            options = await self.analyze_impact(options)
            checkpoint3 = GSTCheckpoint(
                checkpoint_number=3,
                name="impact_analysis",
                result={
                    "options_scored": len(options),
                    "scores": [
                        {"option_id": o.option_id, "total_score": o.total_score}
                        for o in options
                    ],
                },
            )
            checkpoints.append(checkpoint3)
            steps_applied.append("impact_analysis")

            # Checkpoint 4: Risk Assessment
            risk_summary = await self.assess_risks(options)
            checkpoint4 = GSTCheckpoint(
                checkpoint_number=4,
                name="risk_assessment",
                result=risk_summary,
            )
            checkpoints.append(checkpoint4)
            steps_applied.append("risk_assessment")

            # Checkpoint 5: Recommendation
            recommendation = await self.recommend(options, risk_summary)
            checkpoint5 = GSTCheckpoint(
                checkpoint_number=5,
                name="recommendation",
                result=recommendation,
            )
            checkpoints.append(checkpoint5)
            steps_applied.append("recommendation")

        except Exception as exc:
            # BC-008: Never crash — return graceful fallback
            logger.warning(
                "gst_processing_error",
                error=str(exc),
                company_id=self.config.company_id,
            )
            return GSTResult(
                problem_definition=problem_definition if 'problem_definition' in dir() else {},
                options=options if 'options' in dir() else [],
                checkpoints=checkpoints if 'checkpoints' in dir() else [],
                steps_applied=steps_applied + ["error_fallback"]
                if 'steps_applied' in dir() else ["error_fallback"],
                risk_summary=risk_summary if 'risk_summary' in dir() else {},
            )

        return GSTResult(
            problem_definition=problem_definition,
            options=options,
            recommendation=recommendation,
            checkpoints=checkpoints,
            steps_applied=steps_applied,
            risk_summary=risk_summary,
        )

    # ── Utility Methods ───────────────────────────────────────────

    @staticmethod
    def _classify_scope(query: str) -> DecisionScope:
        """
        Classify a query into a decision scope using pattern matching.

        Args:
            query: The customer query text.

        Returns:
            Matched DecisionScope, or GENERAL if no match.
        """
        for pattern, scope in _SCOPE_PATTERNS:
            if pattern.search(query):
                return scope
        return _DEFAULT_SCOPE


# ── GST Node (LangGraph compatible) ──────────────────────────────────


class GSTNode(BaseTechniqueNode):
    """
    F-143: GST (Guided Sequential Thinking) Engine — Tier 3 Premium.

    Extends BaseTechniqueNode for integration into the LangGraph
    pipeline (F-060).

    Activation trigger:
      - state.signals.is_strategic_decision == True
    """

    def __init__(
        self, config: Optional[GSTConfig] = None,
    ):
        self._config = config or GSTConfig()
        self._processor = GSTProcessor(config=self._config)
        # Call parent init after config is set (reads TECHNIQUE_REGISTRY)
        super().__init__()

    @property
    def technique_id(self) -> TechniqueID:
        """Return the TechniqueID for this node."""
        return TechniqueID.GST

    async def should_activate(self, state: ConversationState) -> bool:
        """
        Check if GST should activate.

        Triggers when is_strategic_decision is True.
        """
        return state.signals.is_strategic_decision

    async def execute(self, state: ConversationState) -> ConversationState:
        """
        Execute the full 5-checkpoint GST pipeline.

        Implements:
          1. Problem Definition
          2. Option Generation
          3. Impact Analysis
          4. Risk Assessment
          5. Recommendation

        On error (BC-008), returns the original state unchanged.
        """
        original_state = state

        try:
            result = await self._processor.process(state.query)

            # Record result in state
            self.record_result(state, result.to_dict())

            # If we have a recommendation, append to response parts
            if result.recommendation and result.recommendation.get("selected_option"):
                rec_text = result.recommendation.get("rationale", "")
                if rec_text:
                    state.response_parts.append(rec_text)

            return state

        except Exception as exc:
            # BC-008: Never crash — return original state
            logger.warning(
                "gst_execute_error",
                error=str(exc),
                company_id=self._config.company_id,
            )
            return original_state
