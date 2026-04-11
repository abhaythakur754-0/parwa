"""
F-144: Universe of Thoughts (UoT) — Tier 3 Premium AI Reasoning Technique

Activates when:
  - Customer is VIP tier, OR
  - Sentiment score < 0.3 (angry/frustrated), OR
  - Query involves > $100 monetary value, OR
  - Query flagged by Urgent Attention Panel (F-080)

Uses deterministic heuristic-based multi-solution generation and
evaluation (no LLM calls) to derive optimal resolution:

  1. Solution Space Generation — AI generates 3-5 diverse solution approaches
  2. Evaluation Matrix        — Each solution scored on CSAT, cost, policy,
                                 speed, and long-term relationship impact
  3. Scoring                  — Solutions scored and ranked via weighted totals
  4. Optimal Selection        — Highest-scoring solution selected
  5. Presentation             — Solution presented with rationale

Performance target: ~1,100-1,700 tokens, sub-10,000ms processing.

Building Codes: BC-001 (company isolation), BC-008 (never crash),
               BC-012 (graceful degradation)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from app.core.technique_router import TechniqueID
from app.core.techniques.base import (
    BaseTechniqueNode,
    ConversationState,
)
from app.logger import get_logger

logger = get_logger("universe_of_thoughts")


# ── Enums ─────────────────────────────────────────────────────────────


class SolutionCategory(str, Enum):
    """Categories of solution approaches for customer queries."""

    REFUND = "refund"
    CREDIT = "credit"
    FREE_SERVICE = "free_service"
    UPGRADE = "upgrade"
    POLICY_EXCEPTION = "policy_exception"
    ESCALATION = "escalation"
    GENERAL = "general"


class EvaluationCriterion(str, Enum):
    """Evaluation dimensions used in the UoT scoring matrix."""

    CSAT = "customer_satisfaction"
    COST = "financial_cost"
    POLICY = "policy_compliance"
    SPEED = "resolution_speed"
    LONG_TERM = "long_term_relationship"


# ── Category Pattern Matching ─────────────────────────────────────────


_CATEGORY_PATTERNS: List[Tuple[re.Pattern, SolutionCategory]] = [
    # Billing / refund patterns → REFUND
    (re.compile(
        r"\b(refund|money.?back|reimburse|return.?payment|chargeback|reverse.?charge|full.?refund|partial.?refund)\b",
        re.I,
    ), SolutionCategory.REFUND),
    # Credit / coupon / store credit patterns → CREDIT
    (re.compile(
        r"\b(credit|coupon|voucher|store.?credit|promotional.?credit|account.?credit|loyalty.?point|rebate|discount.?code)\b",
        re.I,
    ), SolutionCategory.CREDIT),
    # Free service / trial / complimentary patterns → FREE_SERVICE
    (re.compile(
        r"\b(free.?month|free.?trial|complimentary|waive.?fee|no.?charge|gratis|free.?upgrade|free.?access|bonus|courtesy)\b",
        re.I,
    ), SolutionCategory.FREE_SERVICE),
    # Upgrade / plan change patterns → UPGRADE
    (re.compile(
        r"\b(upgrade|plan.?change|premium|tier.?change|higher.?plan|better.?plan|plan.?switch|move.?up)\b",
        re.I,
    ), SolutionCategory.UPGRADE),
    # Exception / waiver / policy override patterns → POLICY_EXCEPTION
    (re.compile(
        r"\b(exception|waiver|override|policy.?bend|one.?time.?thing|special.?case|goodwill|accommodation|extenuating)\b",
        re.I,
    ), SolutionCategory.POLICY_EXCEPTION),
    # Escalation / manager / supervisor patterns → ESCALATION
    (re.compile(
        r"\b(escalat|manager|supervisor|senior.?agent|executive|complaint.?department|speak.?to.?someone|higher.?up)\b",
        re.I,
    ), SolutionCategory.ESCALATION),
]

_DEFAULT_CATEGORY = SolutionCategory.GENERAL


# ── Solution Templates (per category) ─────────────────────────────────
#
# Each template defines a solution candidate with pre-assigned scores:
#   - customer_satisfaction: 1-10 scale (higher = happier customer)
#   - financial_cost:        -200 to +200 (negative = cost to company)
#   - policy_compliance:     "yes" | "conditional" | "no"
#   - resolution_speed:      "instant" | "fast" | "moderate" | "slow"
#   - long_term_impact:      "positive" | "neutral" | "negative"
#   - rationale:             Human-readable justification


_SOLUTION_TEMPLATES: Dict[SolutionCategory, List[Dict[str, Any]]] = {
    # ── REFUND ────────────────────────────────────────────────────────
    SolutionCategory.REFUND: [
        {
            "name": "Full Refund",
            "description": (
                "Issue a complete refund of the disputed or unsatisfactory "
                "charge back to the customer's original payment method. "
                "Processing time: 3-10 business days."
            ),
            "scores": {
                "customer_satisfaction": 9,
                "financial_cost": -100,
                "policy_compliance": "yes",
                "resolution_speed": "fast",
                "long_term_impact": "neutral",
            },
            "rationale": (
                "Full refund maximizes immediate customer satisfaction. "
                "While the financial cost is highest, it removes all "
                "dispute friction and preserves the relationship for "
                "future transactions."
            ),
        },
        {
            "name": "Partial Refund",
            "description": (
                "Issue a partial refund covering the disputed portion "
                "of the charge (e.g., pro-rated for unused service). "
                "Processing time: 3-10 business days."
            ),
            "scores": {
                "customer_satisfaction": 6,
                "financial_cost": -40,
                "policy_compliance": "yes",
                "resolution_speed": "fast",
                "long_term_impact": "neutral",
            },
            "rationale": (
                "Partial refund balances financial exposure with customer "
                "goodwill. Appropriate when the service was partially "
                "delivered or the issue only affected part of the charge."
            ),
        },
        {
            "name": "Refund with Store Credit",
            "description": (
                "Convert the refund amount to store credit / account "
                "balance for immediate use. The customer receives the "
                "full value but it stays within the ecosystem."
            ),
            "scores": {
                "customer_satisfaction": 5,
                "financial_cost": -20,
                "policy_compliance": "yes",
                "resolution_speed": "instant",
                "long_term_impact": "positive",
            },
            "rationale": (
                "Store credit retains the full monetary value within the "
                "company ecosystem. Customers can use it immediately, "
                "encouraging continued engagement while limiting cash outflow."
            ),
        },
        {
            "name": "Conditional Refund Upon Review",
            "description": (
                "Initiate a formal review of the charge. If the review "
                "finds in the customer's favor, a full refund is issued. "
                "Estimated resolution: 5-7 business days."
            ),
            "scores": {
                "customer_satisfaction": 4,
                "financial_cost": -10,
                "policy_compliance": "yes",
                "resolution_speed": "slow",
                "long_term_impact": "neutral",
            },
            "rationale": (
                "Review-based approach demonstrates procedural fairness. "
                "Low immediate cost but may frustrate customers seeking "
                "quick resolution. Best when the dispute facts are unclear."
            ),
        },
    ],

    # ── CREDIT ────────────────────────────────────────────────────────
    SolutionCategory.CREDIT: [
        {
            "name": "Full Account Credit",
            "description": (
                "Apply a credit to the customer's account balance equal "
                "to the disputed or affected amount. Available for "
                "immediate use on next billing cycle."
            ),
            "scores": {
                "customer_satisfaction": 7,
                "financial_cost": -50,
                "policy_compliance": "yes",
                "resolution_speed": "instant",
                "long_term_impact": "positive",
            },
            "rationale": (
                "Immediate account credit provides fast resolution and "
                "keeps revenue within the ecosystem. Customers appreciate "
                "the speed even if they prefer cash refunds."
            ),
        },
        {
            "name": "Partial Credit with Apology",
            "description": (
                "Apply a partial credit (e.g., 50% of disputed amount) "
                "along with a personalized apology and explanation of "
                "what went wrong."
            ),
            "scores": {
                "customer_satisfaction": 5,
                "financial_cost": -25,
                "policy_compliance": "yes",
                "resolution_speed": "fast",
                "long_term_impact": "positive",
            },
            "rationale": (
                "A partial credit with transparency about the issue shows "
                "accountability. The personal touch of an apology often "
                "compensates for the lower monetary value."
            ),
        },
        {
            "name": "Loyalty Bonus Credit",
            "description": (
                "Issue a loyalty bonus credit exceeding the disputed "
                "amount (e.g., 120% value) as a goodwill gesture for "
                "long-standing customers."
            ),
            "scores": {
                "customer_satisfaction": 9,
                "financial_cost": -60,
                "policy_compliance": "conditional",
                "resolution_speed": "fast",
                "long_term_impact": "positive",
            },
            "rationale": (
                "Over-delivering on credit value transforms a negative "
                "experience into a loyalty-building moment. Best reserved "
                "for high-value or long-tenure customers."
            ),
        },
        {
            "name": "Deferred Credit on Next Invoice",
            "description": (
                "Apply the credit as a line-item reduction on the "
                "customer's next invoice rather than an immediate account "
                "balance change."
            ),
            "scores": {
                "customer_satisfaction": 4,
                "financial_cost": -30,
                "policy_compliance": "yes",
                "resolution_speed": "slow",
                "long_term_impact": "neutral",
            },
            "rationale": (
                "Deferred credit is operationally simple and integrates "
                "with standard billing. However, the delayed benefit "
                "reduces perceived responsiveness."
            ),
        },
    ],

    # ── FREE_SERVICE ──────────────────────────────────────────────────
    SolutionCategory.FREE_SERVICE: [
        {
            "name": "Free Month of Service",
            "description": (
                "Provide one complimentary month of the customer's current "
                "subscription tier at no charge. Applied to the next "
                "billing cycle automatically."
            ),
            "scores": {
                "customer_satisfaction": 8,
                "financial_cost": -30,
                "policy_compliance": "yes",
                "resolution_speed": "fast",
                "long_term_impact": "positive",
            },
            "rationale": (
                "A free month is a high-value gesture that directly "
                "addresses service dissatisfaction. It extends the "
                "relationship, giving the company time to restore trust "
                "and demonstrate value."
            ),
        },
        {
            "name": "Free Feature Unlock",
            "description": (
                "Temporarily unlock a premium feature or higher tier "
                "capability for 30 days, giving the customer access to "
                "additional value at no extra cost."
            ),
            "scores": {
                "customer_satisfaction": 8,
                "financial_cost": -15,
                "policy_compliance": "yes",
                "resolution_speed": "instant",
                "long_term_impact": "positive",
            },
            "rationale": (
                "Feature unlocks create a 'try before you buy' "
                "experience that can drive future upgrades. The "
                "incremental cost is low while perceived value is high."
            ),
        },
        {
            "name": "Extended Free Trial",
            "description": (
                "If the customer is in a trial period, extend it by "
                "an additional 14-30 days. If not in trial, offer a "
                "temporary return to trial-like access."
            ),
            "scores": {
                "customer_satisfaction": 7,
                "financial_cost": -10,
                "policy_compliance": "conditional",
                "resolution_speed": "fast",
                "long_term_impact": "positive",
            },
            "rationale": (
                "Extended trials give customers more time to realize "
                "value. Particularly effective for onboarding-related "
                "issues where the customer hasn't fully engaged yet."
            ),
        },
        {
            "name": "Complimentary Support Package",
            "description": (
                "Offer a complimentary priority support package for "
                "30-90 days, including dedicated account contact and "
                "faster response times."
            ),
            "scores": {
                "customer_satisfaction": 7,
                "financial_cost": -20,
                "policy_compliance": "yes",
                "resolution_speed": "fast",
                "long_term_impact": "positive",
            },
            "rationale": (
                "Elevating support level demonstrates commitment to "
                "the customer's success. The cost is primarily "
                "operational rather than revenue-impacting."
            ),
        },
    ],

    # ── UPGRADE ───────────────────────────────────────────────────────
    SolutionCategory.UPGRADE: [
        {
            "name": "Complimentary Tier Upgrade",
            "description": (
                "Move the customer to the next higher subscription tier "
                "at no additional cost for 1-3 billing cycles."
            ),
            "scores": {
                "customer_satisfaction": 9,
                "financial_cost": -40,
                "policy_compliance": "conditional",
                "resolution_speed": "fast",
                "long_term_impact": "positive",
            },
            "rationale": (
                "A complimentary upgrade provides significantly more "
                "value than the original service. Creates an upsell path "
                "since customers may choose to keep the higher tier."
            ),
        },
        {
            "name": "Upgrade with Prorated Discount",
            "description": (
                "Offer a discounted upgrade to a higher tier (e.g., 50% "
                "off the price difference for 3 months) to incentivize "
                "the customer to move up."
            ),
            "scores": {
                "customer_satisfaction": 7,
                "financial_cost": -15,
                "policy_compliance": "yes",
                "resolution_speed": "fast",
                "long_term_impact": "positive",
            },
            "rationale": (
                "Discounted upgrades create a revenue-positive path. "
                "The temporary discount lowers the barrier while "
                "building habit around premium features."
            ),
        },
        {
            "name": "Feature-Based Upgrade",
            "description": (
                "Rather than changing tiers, unlock specific premium "
                "features that directly address the customer's complaint "
                "at no additional cost."
            ),
            "scores": {
                "customer_satisfaction": 7,
                "financial_cost": -10,
                "policy_compliance": "yes",
                "resolution_speed": "instant",
                "long_term_impact": "neutral",
            },
            "rationale": (
                "Targeted feature unlocks are surgically precise — they "
                "solve the specific pain point without committing to a "
                "full tier change. Low cost, high relevance."
            ),
        },
        {
            "name": "Loyalty Upgrade Program",
            "description": (
                "Enroll the customer in a loyalty program that includes "
                "automatic tier progression based on tenure, with an "
                "immediate one-tier bump as a goodwill gesture."
            ),
            "scores": {
                "customer_satisfaction": 8,
                "financial_cost": -25,
                "policy_compliance": "conditional",
                "resolution_speed": "moderate",
                "long_term_impact": "positive",
            },
            "rationale": (
                "Loyalty-based upgrades embed the resolution in a "
                "longer-term retention strategy. The immediate bump "
                "solves the current issue while the program sustains "
                "engagement."
            ),
        },
    ],

    # ── POLICY_EXCEPTION ──────────────────────────────────────────────
    SolutionCategory.POLICY_EXCEPTION: [
        {
            "name": "One-Time Policy Waiver",
            "description": (
                "Grant a one-time exception to the standard policy as a "
                "goodwill gesture. Clearly documented in the account "
                "notes with approval reference."
            ),
            "scores": {
                "customer_satisfaction": 8,
                "financial_cost": -20,
                "policy_compliance": "conditional",
                "resolution_speed": "fast",
                "long_term_impact": "neutral",
            },
            "rationale": (
                "A documented one-time waiver shows flexibility while "
                "maintaining policy integrity for future interactions. "
                "Sets clear precedent that this is an exception."
            ),
        },
        {
            "name": "Alternative Resolution Path",
            "description": (
                "Within existing policy, identify an alternative resolution "
                "that satisfies the customer's need without requiring a "
                "formal exception. May involve creative interpretation."
            ),
            "scores": {
                "customer_satisfaction": 6,
                "financial_cost": -5,
                "policy_compliance": "yes",
                "resolution_speed": "moderate",
                "long_term_impact": "positive",
            },
            "rationale": (
                "Creative compliance avoids policy erosion while still "
                "delivering a positive outcome. Demonstrates agent "
                "expertise and customer-centric thinking."
            ),
        },
        {
            "name": "Escalated Policy Override",
            "description": (
                "Escalate to a supervisor or policy team for formal "
                "approval of a policy exception. Resolution may take "
                "longer but carries higher authority."
            ),
            "scores": {
                "customer_satisfaction": 7,
                "financial_cost": -15,
                "policy_compliance": "conditional",
                "resolution_speed": "slow",
                "long_term_impact": "neutral",
            },
            "rationale": (
                "Formal escalation ensures proper authorization and "
                "creates an audit trail. Best for high-value exceptions "
                "that require management sign-off."
            ),
        },
        {
            "name": "Policy Review with Follow-Up",
            "description": (
                "Acknowledge the policy gap, submit a formal policy "
                "review request, and provide interim accommodation "
                "while the review is pending."
            ),
            "scores": {
                "customer_satisfaction": 6,
                "financial_cost": -10,
                "policy_compliance": "yes",
                "resolution_speed": "slow",
                "long_term_impact": "positive",
            },
            "rationale": (
                "Submitting a policy review demonstrates systemic "
                "improvement. The interim accommodation provides "
                "immediate relief while the long-term fix is "
                "evaluated."
            ),
        },
    ],

    # ── ESCALATION ────────────────────────────────────────────────────
    SolutionCategory.ESCALATION: [
        {
            "name": "Immediate Manager Escalation",
            "description": (
                "Transfer the interaction to a senior agent or manager "
                "immediately with full context provided. The customer "
                "receives a callback within 15 minutes."
            ),
            "scores": {
                "customer_satisfaction": 8,
                "financial_cost": -10,
                "policy_compliance": "yes",
                "resolution_speed": "fast",
                "long_term_impact": "positive",
            },
            "rationale": (
                "Immediate escalation signals that the company takes "
                "the issue seriously. Manager authority often enables "
                "solutions beyond standard agent permissions."
            ),
        },
        {
            "name": "Scheduled Executive Callback",
            "description": (
                "Schedule a callback from a senior team member within "
                "a guaranteed time window. Customer receives a "
                "confirmation and case reference number."
            ),
            "scores": {
                "customer_satisfaction": 7,
                "financial_cost": -5,
                "policy_compliance": "yes",
                "resolution_speed": "moderate",
                "long_term_impact": "positive",
            },
            "rationale": (
                "Scheduled callbacks respect the customer's time while "
                "ensuring senior attention. The case reference provides "
                "accountability and continuity."
            ),
        },
        {
            "name": "Cross-Functional Resolution Team",
            "description": (
                "Engage a cross-functional team (support, billing, "
                "technical) for collaborative resolution. Customer "
                "receives a single point of contact for updates."
            ),
            "scores": {
                "customer_satisfaction": 8,
                "financial_cost": -15,
                "policy_compliance": "yes",
                "resolution_speed": "moderate",
                "long_term_impact": "positive",
            },
            "rationale": (
                "Cross-functional teams address complex, multi-department "
                "issues holistically. The single point of contact "
                "prevents the customer from being bounced around."
            ),
        },
        {
            "name": "Priority Support Channel Assignment",
            "description": (
                "Assign the customer to a dedicated priority support "
                "channel with reduced wait times and guaranteed "
                "first-response within 1 hour for the next 30 days."
            ),
            "scores": {
                "customer_satisfaction": 7,
                "financial_cost": -10,
                "policy_compliance": "yes",
                "resolution_speed": "fast",
                "long_term_impact": "positive",
            },
            "rationale": (
                "Priority channel access provides ongoing premium "
                "support beyond the immediate issue. Creates a "
                "safety net that builds confidence in the service."
            ),
        },
    ],

    # ── GENERAL ───────────────────────────────────────────────────────
    SolutionCategory.GENERAL: [
        {
            "name": "Standard Resolution with Follow-Up",
            "description": (
                "Apply the standard resolution process and schedule a "
                "proactive follow-up within 48 hours to confirm "
                "satisfaction."
            ),
            "scores": {
                "customer_satisfaction": 5,
                "financial_cost": -5,
                "policy_compliance": "yes",
                "resolution_speed": "moderate",
                "long_term_impact": "positive",
            },
            "rationale": (
                "Standard resolution with proactive follow-up adds a "
                "care layer beyond the baseline. The follow-up "
                "demonstrates ongoing commitment to the customer."
            ),
        },
        {
            "name": "Expedited Resolution Path",
            "description": (
                "Fast-track the resolution by bypassing standard queues "
                "and assigning dedicated resources. Target resolution "
                "within 24 hours."
            ),
            "scores": {
                "customer_satisfaction": 7,
                "financial_cost": -10,
                "policy_compliance": "yes",
                "resolution_speed": "fast",
                "long_term_impact": "positive",
            },
            "rationale": (
                "Expedited processing shows urgency and respect for "
                "the customer's time. Particularly effective when "
                "the customer has already waited or expressed frustration."
            ),
        },
        {
            "name": "Comprehensive Account Review",
            "description": (
                "Conduct a full account review to identify and resolve "
                "any related issues proactively. Includes a summary "
                "report of findings and actions taken."
            ),
            "scores": {
                "customer_satisfaction": 8,
                "financial_cost": -15,
                "policy_compliance": "yes",
                "resolution_speed": "slow",
                "long_term_impact": "positive",
            },
            "rationale": (
                "A holistic account review may surface additional issues "
                "the customer hasn't reported yet. Being proactive "
                "builds significant trust and prevents future complaints."
            ),
        },
        {
            "name": "Goodwill Package",
            "description": (
                "Offer a goodwill package combining a small credit, "
                "feature unlock, and personalized apology letter to "
                "address the overall experience."
            ),
            "scores": {
                "customer_satisfaction": 8,
                "financial_cost": -20,
                "policy_compliance": "yes",
                "resolution_speed": "fast",
                "long_term_impact": "positive",
            },
            "rationale": (
                "A bundled goodwill package creates a multi-dimensional "
                "positive impression. The combination of monetary and "
                "emotional gestures is more impactful than any single "
                "action."
            ),
        },
    ],
}


# ── Score Normalization Constants ────────────────────────────────────

# Speed mapping to normalized 1-10 scale
_SPEED_NORMALIZATION: Dict[str, int] = {
    "instant": 10,
    "fast": 8,
    "moderate": 5,
    "slow": 3,
}

# Long-term impact mapping to normalized 1-10 scale
_LONG_TERM_NORMALIZATION: Dict[str, int] = {
    "positive": 9,
    "neutral": 5,
    "negative": 2,
}

# Policy compliance mapping to normalized 1-10 scale
_POLICY_NORMALIZATION: Dict[str, int] = {
    "yes": 10,
    "conditional": 6,
    "no": 2,
}


# ── Data Structures ──────────────────────────────────────────────────


@dataclass(frozen=True)
class UoTConfig:
    """
    Immutable configuration for Universe of Thoughts processing (BC-001).

    Attributes:
        company_id: Tenant identifier for company isolation.
        min_solutions: Minimum number of solutions to generate.
        max_solutions: Maximum number of solutions to generate.
        weights: Weighting for each evaluation criterion. Must sum to 1.0.
    """

    company_id: str = ""
    min_solutions: int = 3
    max_solutions: int = 5
    weights: Dict[str, float] = field(default_factory=lambda: {
        "customer_satisfaction": 0.25,
        "financial_cost": 0.20,
        "policy_compliance": 0.25,
        "resolution_speed": 0.15,
        "long_term_relationship": 0.15,
    })


@dataclass
class SolutionCandidate:
    """
    A single solution candidate in the UoT evaluation pipeline.

    Attributes:
        name: Human-readable solution name (e.g., "Full Refund").
        category: The SolutionCategory this candidate belongs to.
        description: Detailed description of the solution approach.
        scores: Raw scores as defined in the template (mixed scales).
        rationale: Why this solution was proposed.
        total_score: Computed weighted total after normalization.
    """

    name: str = ""
    category: str = ""
    description: str = ""
    scores: Dict[str, Any] = field(default_factory=dict)
    rationale: str = ""
    total_score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Serialize solution candidate to dictionary."""
        return {
            "name": self.name,
            "category": self.category,
            "description": self.description,
            "scores": dict(self.scores),
            "rationale": self.rationale,
            "total_score": round(self.total_score, 4),
        }


@dataclass
class UoTResult:
    """
    Output of the full Universe of Thoughts pipeline.

    Attributes:
        solutions: List of all generated solution candidates.
        selected_solution: The highest-scoring solution (if any).
        evaluation_matrix: Full evaluation matrix rows for dashboard display.
        steps_applied: Names of pipeline steps that were executed.
        confidence_boost: Estimated confidence increase from this process.
    """

    solutions: List[SolutionCandidate] = field(default_factory=list)
    selected_solution: Optional[SolutionCandidate] = None
    evaluation_matrix: List[Dict[str, Any]] = field(default_factory=list)
    steps_applied: List[str] = field(default_factory=list)
    confidence_boost: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Serialize result to dictionary for recording in state."""
        return {
            "solutions": [s.to_dict() for s in self.solutions],
            "selected_solution": (
                self.selected_solution.to_dict()
                if self.selected_solution
                else None
            ),
            "evaluation_matrix": self.evaluation_matrix,
            "steps_applied": self.steps_applied,
            "confidence_boost": round(self.confidence_boost, 4),
        }


# ── UoT Processor ────────────────────────────────────────────────────


class UoTProcessor:
    """
    Deterministic Universe of Thoughts processor (F-144).

    Uses pattern matching and heuristic rules to simulate multi-solution
    generation and evaluation without any LLM calls.

    Pipeline:
      1. Solution Space Generation — template-based solution candidates
      2. Evaluation Matrix        — normalized scoring across dimensions
      3. Scoring                  — weighted total computation and ranking
      4. Optimal Selection        — highest-scoring solution identified
      5. Presentation             — solution with rationale formatted
    """

    def __init__(
        self,
        config: Optional[UoTConfig] = None,
    ):
        self.config = config or UoTConfig()

    # ── Step 1: Solution Space Generation ───────────────────────────

    async def generate_solution_space(
        self,
        query: str,
    ) -> List[SolutionCandidate]:
        """
        Generate 3-5 diverse solution approaches based on query category.

        Uses pattern matching to identify the solution category, then
        selects appropriate templates to create SolutionCandidate
        objects with pre-assigned scores.

        Args:
            query: The customer query text.

        Returns:
            List of SolutionCandidate objects (min_solutions to max_solutions).
        """
        if not query or not query.strip():
            return []

        category = self._categorize_query(query)
        templates = _SOLUTION_TEMPLATES.get(
            category, _SOLUTION_TEMPLATES[_DEFAULT_CATEGORY],
        )

        # Limit by config
        selected = templates[: self.config.max_solutions]

        # Ensure minimum count — if primary category has too few,
        # supplement from general category
        if len(selected) < self.config.min_solutions and category != SolutionCategory.GENERAL:
            general_templates = _SOLUTION_TEMPLATES[SolutionCategory.GENERAL]
            needed = self.config.min_solutions - len(selected)
            selected.extend(general_templates[:needed])

        # Trim to max_solutions
        selected = selected[: self.config.max_solutions]

        candidates: List[SolutionCandidate] = []
        for template in selected:
            candidate = SolutionCandidate(
                name=template["name"],
                category=category.value,
                description=template["description"],
                scores=dict(template["scores"]),
                rationale=template["rationale"],
                total_score=0.0,
            )
            candidates.append(candidate)

        logger.info(
            "uot_solution_space_generated",
            category=category.value,
            company_id=self.config.company_id,
            solution_count=len(candidates),
        )

        return candidates

    # ── Step 2: Evaluation Matrix ──────────────────────────────────

    async def evaluate_solutions(
        self,
        solutions: List[SolutionCandidate],
    ) -> Tuple[List[SolutionCandidate], List[Dict[str, Any]]]:
        """
        Build evaluation matrix with normalized, weighted scoring.

        Each raw score is normalized to a 1-10 scale:
          - customer_satisfaction: already 1-10
          - financial_cost: mapped from -200..+200 to 1..10
          - policy_compliance: mapped from text label to 1..10
          - resolution_speed: mapped from text label to 1..10
          - long_term_impact: mapped from text label to 1..10

        Then weighted totals are computed and solutions are ranked.

        Args:
            solutions: List of SolutionCandidate objects with raw scores.

        Returns:
            Tuple of (updated solutions with total_score, evaluation matrix rows).
        """
        if not solutions:
            return [], []

        weights = self.config.weights
        matrix_rows: List[Dict[str, Any]] = []

        for solution in solutions:
            raw = solution.scores

            # ── Normalize each dimension to 1-10 ─────────────────
            csat_score = self._normalize_1_to_10(
                raw.get("customer_satisfaction", 5), 1, 10,
            )

            cost_score = self._normalize_cost(
                raw.get("financial_cost", 0),
            )

            policy_score = self._normalize_by_lookup(
                raw.get("policy_compliance", "yes"),
                _POLICY_NORMALIZATION,
            )

            speed_score = self._normalize_by_lookup(
                raw.get("resolution_speed", "moderate"),
                _SPEED_NORMALIZATION,
            )

            long_term_score = self._normalize_by_lookup(
                raw.get("long_term_impact", "neutral"),
                _LONG_TERM_NORMALIZATION,
            )

            # ── Compute weighted total ────────────────────────────
            total = (
                csat_score * weights.get("customer_satisfaction", 0.25)
                + cost_score * weights.get("financial_cost", 0.20)
                + policy_score * weights.get("policy_compliance", 0.25)
                + speed_score * weights.get("resolution_speed", 0.15)
                + long_term_score * weights.get("long_term_relationship", 0.15)
            )

            solution.total_score = round(total, 4)

            # ── Build matrix row ──────────────────────────────────
            matrix_row = {
                "solution": solution.name,
                "category": solution.category,
                "customer_satisfaction": csat_score,
                "financial_cost": cost_score,
                "financial_cost_raw": raw.get("financial_cost", 0),
                "policy_compliance": policy_score,
                "policy_compliance_raw": raw.get("policy_compliance", "yes"),
                "resolution_speed": speed_score,
                "resolution_speed_raw": raw.get("resolution_speed", "moderate"),
                "long_term_impact": long_term_score,
                "long_term_impact_raw": raw.get("long_term_impact", "neutral"),
                "total": round(total, 4),
                "weights_used": dict(weights),
            }
            matrix_rows.append(matrix_row)

        # Sort solutions by total_score descending
        solutions.sort(key=lambda s: s.total_score, reverse=True)

        # Sort matrix rows to match
        matrix_rows.sort(key=lambda r: r["total"], reverse=True)

        logger.info(
            "uot_evaluation_complete",
            company_id=self.config.company_id,
            solution_count=len(solutions),
            top_solution=solutions[0].name if solutions else "none",
            top_score=solutions[0].total_score if solutions else 0.0,
        )

        return solutions, matrix_rows

    # ── Step 3: Optimal Selection ──────────────────────────────────

    async def select_optimal(
        self,
        solutions: List[SolutionCandidate],
    ) -> Optional[SolutionCandidate]:
        """
        Select the highest-scoring solution.

        After evaluation and ranking (descending by total_score),
        the first solution is the optimal choice. Additional checks
        ensure the selected solution has a minimum viable score.

        Args:
            solutions: Ranked list of SolutionCandidate objects.

        Returns:
            The best SolutionCandidate, or None if no solutions exist.
        """
        if not solutions:
            return None

        best = solutions[0]

        # Minimum viable score threshold (below 3.0 indicates
        # no solution is genuinely good — still return it but log)
        if best.total_score < 3.0:
            logger.warning(
                "uot_low_confidence_selection",
                company_id=self.config.company_id,
                selected_solution=best.name,
                score=best.total_score,
            )

        logger.info(
            "uot_optimal_selected",
            company_id=self.config.company_id,
            solution=best.name,
            score=best.total_score,
            rationale=best.rationale[:80],
        )

        return best

    # ── Step 4: Presentation ───────────────────────────────────────

    async def generate_presentation(
        self,
        solution: SolutionCandidate,
        all_solutions: Optional[List[SolutionCandidate]] = None,
    ) -> str:
        """
        Present the selected solution with rationale.

        Formats a structured presentation string suitable for
        inclusion in the response. Includes the solution name,
        description, key rationale, and how it compares to
        alternatives.

        Args:
            solution: The selected SolutionCandidate.
            all_solutions: Optional full list for comparison context.

        Returns:
            Formatted presentation string.
        """
        if not solution:
            return "Unable to determine an optimal solution at this time."

        parts: List[str] = []

        # Solution name and description
        parts.append(
            f"Recommended Solution: {solution.name}"
        )
        parts.append(solution.description)

        # Rationale
        if solution.rationale:
            parts.append(f"\nRationale: {solution.rationale}")

        # Score summary
        raw = solution.scores
        cost_display = raw.get("financial_cost", 0)
        cost_label = (
            f"${abs(cost_display)}"
            if cost_display >= 0
            else f"-${abs(cost_display)}"
        )
        speed_display = raw.get("resolution_speed", "moderate")

        score_summary = (
            f"\nScore Summary — "
            f"CSAT: {raw.get('customer_satisfaction', 'N/A')}/10, "
            f"Cost Impact: {cost_label}, "
            f"Policy: {raw.get('policy_compliance', 'N/A')}, "
            f"Speed: {speed_display}, "
            f"Long-Term: {raw.get('long_term_impact', 'N/A')} | "
            f"Weighted Total: {solution.total_score:.1f}"
        )
        parts.append(score_summary)

        # Comparison context
        if all_solutions and len(all_solutions) > 1:
            runner_up = all_solutions[1] if len(all_solutions) > 1 else None
            if runner_up and runner_up.name != solution.name:
                parts.append(
                    f"\nAlternative Considered: {runner_up.name} "
                    f"(Score: {runner_up.total_score:.1f})"
                )

        return "\n".join(parts)

    # ── Full Pipeline ──────────────────────────────────────────────

    async def process(
        self,
        query: str,
    ) -> UoTResult:
        """
        Run the full 5-step Universe of Thoughts pipeline.

        Args:
            query: The customer query to reason about.

        Returns:
            UoTResult with all pipeline outputs.
        """
        steps_applied: List[str] = []
        confidence_boost = 0.0
        solutions: List[SolutionCandidate] = []
        evaluation_matrix: List[Dict[str, Any]] = []
        selected: Optional[SolutionCandidate] = None

        if not query or not query.strip():
            return UoTResult(
                steps_applied=["empty_input"],
                confidence_boost=0.0,
            )

        try:
            # Step 1: Solution Space Generation
            solutions = await self.generate_solution_space(query)
            if solutions:
                steps_applied.append("solution_space_generation")
                confidence_boost += 0.05
                logger.info(
                    "uot_step1_complete",
                    company_id=self.config.company_id,
                    solutions_generated=len(solutions),
                )

            # Step 2: Evaluation Matrix
            solutions, evaluation_matrix = await self.evaluate_solutions(
                solutions,
            )
            if evaluation_matrix:
                steps_applied.append("evaluation_matrix")
                confidence_boost += 0.10
                logger.info(
                    "uot_step2_complete",
                    company_id=self.config.company_id,
                    matrix_rows=len(evaluation_matrix),
                )

            # Step 3: Optimal Selection
            selected = await self.select_optimal(solutions)
            if selected:
                steps_applied.append("optimal_selection")
                confidence_boost += 0.10

            # Step 4: Presentation
            if selected:
                presentation = await self.generate_presentation(
                    selected, solutions,
                )
                if presentation:
                    steps_applied.append("presentation")
                    confidence_boost += 0.05

            # Final confidence boost — cap at 0.35 for UoT (Tier 3)
            confidence_boost = min(confidence_boost, 0.35)

        except Exception as exc:
            # BC-008: Never crash — return graceful fallback
            logger.warning(
                "uot_processing_error",
                error=str(exc),
                company_id=self.config.company_id,
            )
            return UoTResult(
                solutions=solutions,
                selected_solution=selected,
                evaluation_matrix=evaluation_matrix,
                steps_applied=steps_applied + ["error_fallback"]
                if steps_applied
                else ["error_fallback"],
                confidence_boost=0.0,
            )

        return UoTResult(
            solutions=solutions,
            selected_solution=selected,
            evaluation_matrix=evaluation_matrix,
            steps_applied=steps_applied,
            confidence_boost=confidence_boost,
        )

    # ── Normalization Utility Methods ──────────────────────────────

    @staticmethod
    def _normalize_1_to_10(
        value: Any,
        min_val: float = 1.0,
        max_val: float = 10.0,
    ) -> float:
        """
        Clamp a numeric value to the 1-10 range.

        Handles non-numeric inputs gracefully by returning a
        neutral midpoint.

        Args:
            value: The value to normalize (ideally numeric).
            min_val: Lower bound of the valid range.
            max_val: Upper bound of the valid range.

        Returns:
            Clamped float between min_val and max_val.
        """
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return 5.0

        return max(min_val, min(max_val, numeric))

    @staticmethod
    def _normalize_cost(raw_cost: Any) -> float:
        """
        Normalize financial cost to a 1-10 scale.

        Mapping:
          - -200 or lower → 1.0  (highest cost to company)
          -   0            → 5.5  (neutral)
          - +200 or higher → 10.0 (revenue positive)

        The formula linearly interpolates between these anchor points.

        Args:
            raw_cost: The raw financial cost (negative = expense).

        Returns:
            Normalized score between 1.0 and 10.0.
        """
        try:
            cost = float(raw_cost)
        except (TypeError, ValueError):
            return 5.5

        # Linear mapping: cost in [-200, +200] → score in [1.0, 10.0]
        # slope = (10.0 - 1.0) / (200 - (-200)) = 9.0 / 400 = 0.0225
        # intercept: when cost = -200, score = 1.0
        # score = 0.0225 * (cost + 200) + 1.0
        normalized = 0.0225 * (cost + 200.0) + 1.0
        return max(1.0, min(10.0, round(normalized, 2)))

    @staticmethod
    def _normalize_by_lookup(
        value: Any,
        lookup: Dict[str, int],
    ) -> float:
        """
        Normalize a text label by lookup table.

        Falls back to a neutral midpoint of 5.0 if the label
        is not found in the lookup table.

        Args:
            value: The text label to look up.
            lookup: Dict mapping label strings to integer scores.

        Returns:
            Normalized score (1-10 range), or 5.0 if not found.
        """
        if not value or not isinstance(value, str):
            return 5.0

        score = lookup.get(value.strip().lower())
        if score is not None:
            return float(score)

        # Case-insensitive fallback
        value_lower = value.strip().lower()
        for key, val in lookup.items():
            if key in value_lower or value_lower in key:
                return float(val)

        return 5.0

    # ── Query Categorization ──────────────────────────────────────

    @staticmethod
    def _categorize_query(query: str) -> SolutionCategory:
        """
        Categorize a query into a solution category using pattern matching.

        Evaluates query patterns in order; the first match wins. Falls
        back to GENERAL if no patterns match.

        Args:
            query: The customer query text.

        Returns:
            Matched SolutionCategory, or GENERAL if no match.
        """
        for pattern, category in _CATEGORY_PATTERNS:
            if pattern.search(query):
                return category
        return _DEFAULT_CATEGORY


# ── Universe of Thoughts Node (LangGraph compatible) ──────────────────


class UniverseOfThoughtsNode(BaseTechniqueNode):
    """
    F-144: Universe of Thoughts (UoT) — Tier 3 Premium.

    Extends BaseTechniqueNode for integration into the LangGraph
    pipeline (F-060).

    Activation triggers:
      - Customer is VIP tier, OR
      - Sentiment score < 0.3 (angry/frustrated), OR
      - Query involves > $100 monetary value, OR
      - Query flagged by Urgent Attention Panel (F-080)
    """

    def __init__(
        self,
        config: Optional[UoTConfig] = None,
    ):
        self._config = config or UoTConfig()
        self._processor = UoTProcessor(config=self._config)
        # Call parent init after config is set (reads TECHNIQUE_REGISTRY)
        super().__init__()

    @property
    def technique_id(self) -> TechniqueID:
        """Return the TechniqueID for this node."""
        return TechniqueID.UNIVERSE_OF_THOUGHTS

    async def should_activate(self, state: ConversationState) -> bool:
        """
        Check if Universe of Thoughts should activate.

        Triggers when any of the following conditions are met:
          - Customer tier is VIP
          - Sentiment score is below 0.3 (angry/frustrated)
          - Monetary value of the query exceeds $100
          - Query has been flagged by the Urgent Attention Panel (F-080)

        The urgent_flag is checked via the technique_results key
        'urgent_attention_panel' if present.
        """
        is_vip = state.signals.customer_tier == "vip"
        is_angry = state.signals.sentiment_score < 0.3
        is_high_value = state.signals.monetary_value > 100

        # Check for F-080 Urgent Attention Panel flag
        is_flagged = False
        urgent_result = state.technique_results.get("urgent_attention_panel")
        if urgent_result and isinstance(urgent_result, dict):
            is_flagged = urgent_result.get("flagged", False)
        elif urgent_result is True:
            is_flagged = True

        return (
            is_vip
            or is_angry
            or is_high_value
            or is_flagged
        )

    async def execute(self, state: ConversationState) -> ConversationState:
        """
        Execute the Universe of Thoughts pipeline.

        Implements the 5-step multi-solution reasoning process:
          1. Solution Space Generation
          2. Evaluation Matrix
          3. Optimal Selection
          4. Presentation
          5. Confidence update

        On error (BC-008), returns the original state unchanged.
        """
        original_state = state

        try:
            result = await self._processor.process(state.query)

            # Build confidence-adjusted signals
            new_confidence = min(
                state.signals.confidence_score + result.confidence_boost,
                1.0,
            )

            # Record result in state
            self.record_result(state, result.to_dict())

            # Update confidence score in signals
            state.signals.confidence_score = new_confidence

            # If we have a selected solution with presentation,
            # append the presentation to response parts
            if result.selected_solution and result.steps_applied:
                presentation = await self._processor.generate_presentation(
                    result.selected_solution, result.solutions,
                )
                if presentation:
                    state.response_parts.append(presentation)

            logger.info(
                "uot_execution_complete",
                company_id=self._config.company_id,
                solutions_evaluated=len(result.solutions),
                selected=(
                    result.selected_solution.name
                    if result.selected_solution
                    else "none"
                ),
                confidence_boost=result.confidence_boost,
                steps_applied=", ".join(result.steps_applied),
            )

            return state

        except Exception as exc:
            # BC-008: Never crash — return original state
            logger.warning(
                "uot_execute_error",
                error=str(exc),
                company_id=self._config.company_id,
            )
            return original_state
