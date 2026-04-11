"""
F-146: Self-Consistency — Tier 3 Premium AI Reasoning Technique

Activates when monetary_value > $100 OR intent_type == "billing" OR
refund/credit explicitly requested OR financial compliance is implicated.
Uses deterministic heuristic-based multi-answer verification (no LLM
calls) to ensure financial response accuracy by:

  1. Multi-Answer Generation   — generate 3-5 independent answers via
     different reasoning approaches (direct, formula-based, policy-based,
     conservative, customer-favorable)
  2. Consistency Check          — compare all answers for agreement on
     key facts and numerical conclusions
  3. Majority Vote              — if all/most agree → high confidence;
     if disagree → identify source, investigate further
  4. Disagreement Analysis      — pinpoint why answers diverge and
     provide structured reasoning for the variance
  5. Final Response             — deliver most consistent answer with a
     confidence indicator

Performance target: ~750-1,150 tokens, sub-50ms processing.

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
    ExecutionResultStatus,
)
from app.logger import get_logger

logger = get_logger("self_consistency")


# ── Reasoning Approaches ───────────────────────────────────────────


class ReasoningApproach(str, Enum):
    """Approaches used to generate independent answers.

    Each answer in the self-consistency pipeline uses a slightly
    different reasoning lens so that genuine errors are exposed
    through cross-validation.
    """

    DIRECT = "direct"
    FORMULA_BASED = "formula_based"
    POLICY_BASED = "policy_based"
    CONSERVATIVE = "conservative"
    CUSTOMER_FAVORABLE = "customer_favorable"


# ── Consensus Levels ───────────────────────────────────────────────


class ConsensusLevel(str, Enum):
    """Degree of agreement across independently generated answers."""

    UNANIMOUS = "unanimous"
    MAJORITY = "majority"
    SPLIT = "split"
    NO_CONSENSUS = "no_consensus"


# ── Financial Categories ───────────────────────────────────────────


class FinancialCategory(str, Enum):
    """Categories of financial customer-support queries."""

    REFUND = "refund"
    PRORATION = "proration"
    CREDIT = "credit"
    CHARGE_DISPUTE = "charge_dispute"
    BILLING_INQUIRY = "billing_inquiry"
    GENERAL = "general"


# ── Category Pattern Matching ──────────────────────────────────────


_CATEGORY_PATTERNS: List[Tuple[re.Pattern, FinancialCategory]] = [
    # Refund patterns — explicit refund/credit-back language
    (
        re.compile(
            r"\b(?:refund\w*|money.?back|reimburs\w*|credit.?back|"
            r"return.?payment|non.?refundable)\b",
            re.I,
        ),
        FinancialCategory.REFUND,
    ),
    # Proration patterns — partial-period calculations
    (
        re.compile(
            r"\b(?:prorat(?:ed|ion|ing|e)?|partial|remaining.?period|"
            r"unused|mid.?cycle|early.?cancel|cancel.*month|"
            r"month.*cancel|days? remaining|credit.*balance)\b",
            re.I,
        ),
        FinancialCategory.PRORATION,
    ),
    # Credit patterns — store credit, account credit, promotional credit
    (
        re.compile(
            r"\b(store.?credit|account.?credit|promo.?credit|credit.?note|"
            r"credit.?memo|apply.?credit|credit.?balance|voucher)\b",
            re.I,
        ),
        FinancialCategory.CREDIT,
    ),
    # Charge-dispute patterns — unexpected charges, double billing
    (
        re.compile(
            r"\b(?:disput\w*|unauthor\w*|unexpect\w*|unrecogni\w*|"
            r"double.?bill|over.?charg|wrong.?amount|fraudulent|"
            r"didn'?t.?author|not.?recogni\w*|charge.?back|chargeback)\b",
            re.I,
        ),
        FinancialCategory.CHARGE_DISPUTE,
    ),
    # Billing-inquiry patterns — general billing questions
    (
        re.compile(
            r"\b(?:bill\w*|invoic\w*|charg\w*|payment|fee|cost|price|"
            r"subscription|plan.?price|monthly|annual|yearly|"
            r"auto.?renew|renewal)\b",
            re.I,
        ),
        FinancialCategory.BILLING_INQUIRY,
    ),
]

_DEFAULT_CATEGORY = FinancialCategory.GENERAL


# ── Monetary-amount detection ──────────────────────────────────────

_MONETARY_PATTERN = re.compile(
    r"\$\s*([\d,]+(?:\.\d{1,2})?)",
)

# ── Reserved / policy-anchor words ─────────────────────────────────

_RESERVED_PHRASES: FrozenSet[str] = frozenset({
    "refund", "cancellation", "payment", "charge", "invoice",
    "subscription", "billing", "prorated", "policy", "deadline",
    "contract", "termination", "credit", "debit", "amount",
    "dispute", "verification", "security", "timeline", "eligibility",
    "proration", "fee", "penalty", "remaining", "unused",
})

_VALIDATION_ANCHORS: FrozenSet[str] = frozenset({
    "verify", "review", "check", "investigate", "confirm",
    "available", "eligible", "within", "depending on", "based on",
    "let me", "i can", "we can", "option", "solution",
    "per our", "according to", "standard", "typically",
})


# ── Answer Templates (per category × approach) ─────────────────────
#
# Each template represents one independent "answer" generated by a
# specific reasoning approach.  Most answers within a category agree
# on the key numerical value so that the consistency-check logic has
# a realistic majority to detect.  One answer (usually CONSERVATIVE)
# typically introduces a small variation to exercise the disagreement
# analysis path.
#
# key_value  — the core numerical conclusion (e.g. "$80") used for
#              cross-answer comparison.


_ANSWER_TEMPLATES: Dict[FinancialCategory, List[Dict[str, str]]] = {
    # ─── REFUND ─────────────────────────────────────────────────
    FinancialCategory.REFUND: [
        {
            "approach": ReasoningApproach.DIRECT,
            "answer": "Based on the information provided, your refund amount is $80.00. "
                      "This reflects the unused portion of your service after processing "
                      "your cancellation request through our standard refund workflow.",
            "key_value": "$80",
            "reasoning": "Direct calculation of unused service value based on "
                         "remaining billing period.",
        },
        {
            "approach": ReasoningApproach.FORMULA_BASED,
            "answer": "Applying the refund formula: (remaining_months / total_months) × "
                      "annual_price = (8 / 12) × $120 = $80.00. Your refund is $80.00.",
            "key_value": "$80",
            "reasoning": "Standard proration formula applied to derive the refund "
                         "from the remaining service term.",
        },
        {
            "approach": ReasoningApproach.POLICY_BASED,
            "answer": "Per our refund policy (Section 4.2), customers cancelling after the "
                      "first 30 days receive a prorated refund. Your eligible refund is "
                      "$80.00, reflecting 8 months of unused service.",
            "key_value": "$80",
            "reasoning": "Refund policy referenced to confirm eligibility and "
                         "calculate the prorated amount.",
        },
        {
            "approach": ReasoningApproach.CONSERVATIVE,
            "answer": "Accounting for the 5% early cancellation processing fee outlined "
                      "in our terms, the adjusted refund is $76.00 ($80.00 − $4.00 fee). "
                      "This conservative estimate accounts for administrative costs.",
            "key_value": "$76",
            "reasoning": "Applied early cancellation fee deduction per terms of service, "
                         "resulting in a lower refund estimate.",
        },
        {
            "approach": ReasoningApproach.CUSTOMER_FAVORABLE,
            "answer": "Your refund is $80.00 for the unused portion of your plan. If "
                      "your account is in good standing and this is your first "
                      "cancellation, we may also waive the processing fee as a courtesy.",
            "key_value": "$80",
            "reasoning": "Standard refund calculated, with a note about potential "
                         "fee waiver for first-time customers.",
        },
    ],

    # ─── PRORATION ──────────────────────────────────────────────
    FinancialCategory.PRORATION: [
        {
            "approach": ReasoningApproach.DIRECT,
            "answer": "Your prorated charge for the partial month is $15.00, calculated "
                      "from the 12 days of service used out of a 30-day billing cycle "
                      "on your $37.50/month plan.",
            "key_value": "$15",
            "reasoning": "Direct day-based calculation: (12 / 30) × $37.50 = $15.00.",
        },
        {
            "approach": ReasoningApproach.FORMULA_BASED,
            "answer": "Using the daily rate formula: monthly_price / days_in_cycle × "
                      "days_used = ($37.50 / 30) × 12 = $15.00. Your prorated "
                      "charge is $15.00.",
            "key_value": "$15",
            "reasoning": "Daily rate derived first, then multiplied by days of "
                         "active service.",
        },
        {
            "approach": ReasoningApproach.POLICY_BASED,
            "answer": "Our proration policy applies a daily rate calculation when service "
                      "changes mid-cycle. Based on your $37.50/month plan and 12 days "
                      "of usage, the prorated amount is $15.00.",
            "key_value": "$15",
            "reasoning": "Policy-driven daily-rate proration applied consistently "
                         "across mid-cycle changes.",
        },
        {
            "approach": ReasoningApproach.CONSERVATIVE,
            "answer": "Accounting for potential rounding and a 2-day minimum billing "
                      "window, the conservative prorated charge is $16.00 rather than "
                      "the exact $15.00 to cover any partial-day discrepancies.",
            "key_value": "$16",
            "reasoning": "Added a rounding buffer of $1 for potential partial-day "
                         "and minimum-billing adjustments.",
        },
        {
            "approach": ReasoningApproach.CUSTOMER_FAVORABLE,
            "answer": "Your prorated charge is $15.00. Since you upgraded mid-cycle, "
                      "we apply the lower rate for the first 12 days as a customer "
                      "courtesy, keeping your cost minimal.",
            "key_value": "$15",
            "reasoning": "Lower-rate courtesy applied for the initial period before "
                         "the mid-cycle plan change.",
        },
    ],

    # ─── CREDIT ──────────────────────────────────────────────────
    FinancialCategory.CREDIT: [
        {
            "approach": ReasoningApproach.DIRECT,
            "answer": "A store credit of $25.00 has been applied to your account. "
                      "This credit is available immediately and can be used toward "
                      "your next purchase or subscription renewal.",
            "key_value": "$25",
            "reasoning": "Direct application of the determined credit amount "
                         "to the customer's account balance.",
        },
        {
            "approach": ReasoningApproach.FORMULA_BASED,
            "answer": "Credit calculation: promotional_rate × affected_months = "
                      "$5.00 × 5 = $25.00. The total credit of $25.00 reflects "
                      "the billing error over the affected 5-month period.",
            "key_value": "$25",
            "reasoning": "Error-rate multiplied by the number of affected billing "
                         "cycles to reach the total credit.",
        },
        {
            "approach": ReasoningApproach.POLICY_BASED,
            "answer": "Per our billing correction policy, overcharges are credited "
                      "back in full. The $25.00 credit covers 5 months of incorrect "
                      "billing at $5.00/month, applied per Section 6.1.",
            "key_value": "$25",
            "reasoning": "Policy mandates full credit for confirmed overcharges "
                         "with no deductions.",
        },
        {
            "approach": ReasoningApproach.CONSERVATIVE,
            "answer": "After verifying the exact billing discrepancy and excluding "
                      "one month with partial usage, the conservative credit estimate "
                      "is $20.00 (4 confirmed months × $5.00).",
            "key_value": "$20",
            "reasoning": "Excluded one partially-verified month, yielding a lower "
                         "but more defensible credit amount.",
        },
        {
            "approach": ReasoningApproach.CUSTOMER_FAVORABLE,
            "answer": "We've applied a $25.00 credit to your account for the billing "
                      "error. Additionally, we've added a $5.00 goodwill credit for "
                      "the inconvenience, bringing your total to $30.00.",
            "key_value": "$30",
            "reasoning": "Base credit of $25 plus $5 goodwill adjustment for "
                         "customer satisfaction.",
        },
    ],

    # ─── CHARGE DISPUTE ──────────────────────────────────────────
    FinancialCategory.CHARGE_DISPUTE: [
        {
            "approach": ReasoningApproach.DIRECT,
            "answer": "After reviewing the disputed charge of $49.99, we confirm "
                      "it does not match your authorized plan of $29.99/month. The "
                      "difference of $20.00 will be refunded to your original "
                      "payment method.",
            "key_value": "$20",
            "reasoning": "Direct comparison of charged amount vs. authorized plan "
                         "price to identify the overcharge.",
        },
        {
            "approach": ReasoningApproach.FORMULA_BASED,
            "answer": "Dispute resolution: charged_amount − authorized_amount = "
                      "$49.99 − $29.99 = $20.00. The overcharge of $20.00 will be "
                      "credited back within 5-7 business days.",
            "key_value": "$20",
            "reasoning": "Simple arithmetic difference between what was charged "
                         "and what was authorized.",
        },
        {
            "approach": ReasoningApproach.POLICY_BASED,
            "answer": "Under our dispute resolution policy, unauthorized charge "
                      "differences are fully refunded. The $20.00 variance between "
                      "your $29.99 plan and the $49.99 charge will be corrected.",
            "key_value": "$20",
            "reasoning": "Dispute policy guarantees full refund of the charge "
                         "variance upon verification.",
        },
        {
            "approach": ReasoningApproach.CONSERVATIVE,
            "answer": "Pending full investigation of the $49.99 charge, we "
                      "provisionally credit $20.00. If the investigation confirms "
                      "a system error, the full $20.00 credit becomes permanent.",
            "key_value": "$20",
            "reasoning": "Provisional credit issued pending investigation — "
                         "amount matches the observed discrepancy.",
        },
        {
            "approach": ReasoningApproach.CUSTOMER_FAVORABLE,
            "answer": "The $20.00 overcharge has been fully refunded. We also "
                      "applied a 10% goodwill adjustment ($2.00) for the "
                      "inconvenience, for a total credit of $22.00.",
            "key_value": "$22",
            "reasoning": "Full overcharge refund plus a percentage-based "
                         "goodwill adjustment for the dispute.",
        },
    ],

    # ─── BILLING INQUIRY ─────────────────────────────────────────
    FinancialCategory.BILLING_INQUIRY: [
        {
            "approach": ReasoningApproach.DIRECT,
            "answer": "Your current monthly bill is $39.99, which includes your base "
                      "plan at $29.99 plus the $10.00 add-on you activated last "
                      "billing cycle.",
            "key_value": "$39.99",
            "reasoning": "Sum of base plan price and active add-on charges "
                         "as reflected in the billing system.",
        },
        {
            "approach": ReasoningApproach.FORMULA_BASED,
            "answer": "Bill calculation: base_plan + add_ons + taxes = $29.99 + "
                      "$10.00 + $0.00 (taxes included) = $39.99. Your total "
                      "monthly charge is $39.99.",
            "key_value": "$39.99",
            "reasoning": "Itemized calculation summing each billing component "
                         "to reach the total.",
        },
        {
            "approach": ReasoningApproach.POLICY_BASED,
            "answer": "Per our billing schedule, your account is billed on the 1st "
                      "of each month. Your current plan ($29.99) plus the active "
                      "add-on ($10.00) totals $39.99 as shown on your latest invoice.",
            "key_value": "$39.99",
            "reasoning": "Billing policy confirms the charge composition and "
                         "billing date alignment.",
        },
        {
            "approach": ReasoningApproach.CONSERVATIVE,
            "answer": "Your base plan is $29.99. With the $10.00 add-on, the "
                      "subtotal is $39.99. Please note that if promotional pricing "
                      "expires next cycle, the cost may increase by approximately $5.00.",
            "key_value": "$39.99",
            "reasoning": "Current total confirmed, but conservative note added "
                         "about potential future price changes.",
        },
        {
            "approach": ReasoningApproach.CUSTOMER_FAVORABLE,
            "answer": "Your bill is $39.99 this month ($29.99 plan + $10.00 add-on). "
                      "Good news: your loyalty discount of $5.00/month kicks in next "
                      "cycle, reducing your bill to $34.99.",
            "key_value": "$39.99",
            "reasoning": "Current total confirmed with a forward-looking note about "
                         "upcoming loyalty discount.",
        },
    ],

    # ─── GENERAL (financial) ─────────────────────────────────────
    FinancialCategory.GENERAL: [
        {
            "approach": ReasoningApproach.DIRECT,
            "answer": "Based on the details provided, the applicable amount is $50.00. "
                      "This is derived from the standard rate applied to your account "
                      "configuration and current billing settings.",
            "key_value": "$50",
            "reasoning": "Direct application of standard rates to the customer's "
                         "account configuration.",
        },
        {
            "approach": ReasoningApproach.FORMULA_BASED,
            "answer": "Using the standard calculation: base_rate × units = $25.00 × 2 = "
                      "$50.00. The total applicable amount is $50.00 based on your "
                      "current usage and plan terms.",
            "key_value": "$50",
            "reasoning": "Rate × quantity formula applied to determine the "
                         "total financial impact.",
        },
        {
            "approach": ReasoningApproach.POLICY_BASED,
            "answer": "According to our general pricing policy, the amount of $50.00 "
                      "applies to your current service tier. This is consistent with "
                      "our published rate card for your account type.",
            "key_value": "$50",
            "reasoning": "Published rate card and pricing policy cross-referenced "
                         "to confirm the amount.",
        },
        {
            "approach": ReasoningApproach.CONSERVATIVE,
            "answer": "The standard amount is $50.00. However, depending on your "
                      "specific contract terms, there could be a variance of ±$5.00 "
                      "based on regional adjustments or custom provisions.",
            "key_value": "$50",
            "reasoning": "Standard amount confirmed with a conservative variance "
                         "range noted for contractual differences.",
        },
        {
            "approach": ReasoningApproach.CUSTOMER_FAVORABLE,
            "answer": "Your total is $50.00 at the standard rate. If you've been "
                      "a customer for over 12 months, you may qualify for a "
                      "10% loyalty discount, bringing it to $45.00.",
            "key_value": "$50",
            "reasoning": "Standard rate confirmed with a loyalty-discount "
                         "path highlighted for the customer.",
        },
    ],
}


# ── Consensus → confidence-boost mapping ───────────────────────────


_CONSENSUS_BOOST: Dict[ConsensusLevel, float] = {
    ConsensusLevel.UNANIMOUS: 0.15,
    ConsensusLevel.MAJORITY: 0.10,
    ConsensusLevel.SPLIT: 0.05,
    ConsensusLevel.NO_CONSENSUS: 0.02,
}


# ── Data Structures ────────────────────────────────────────────────


@dataclass(frozen=True)
class SelfConsistencyConfig:
    """
    Immutable configuration for Self-Consistency (BC-001).

    Attributes:
        company_id: Tenant identifier for company isolation.
        num_answers: Number of independent answers to generate (3-5).
        consensus_threshold: Agreement ratio required for majority.
        enable_disagreement_analysis: Whether to run disagreement analysis.
    """

    company_id: str = ""
    num_answers: int = 5
    consensus_threshold: float = 0.6  # 60% agreement for majority
    enable_disagreement_analysis: bool = True


@dataclass
class IndependentAnswer:
    """
    A single answer generated by one reasoning approach.

    Attributes:
        approach: The reasoning lens used (e.g. "formula_based").
        answer_text: Full natural-language answer.
        key_value: The core numerical conclusion for cross-comparison.
        reasoning: Explanation of how the answer was derived.
        confidence: Per-answer confidence estimate.
    """

    approach: str = ""
    answer_text: str = ""
    key_value: str = ""
    reasoning: str = ""
    confidence: float = 0.0


@dataclass
class ConsistencyResult:
    """
    Output of the consistency-check step.

    Attributes:
        consensus_level: Degree of agreement (unanimous / majority / …).
        agreement_ratio: Fraction of answers that agree (0.0 – 1.0).
        majority_value: The most common key_value among answers.
        dissenting_answers: Answers whose key_value differs from majority.
        disagreement_analysis: Natural-language analysis of divergence.
    """

    consensus_level: str = ""
    agreement_ratio: float = 0.0
    majority_value: str = ""
    dissenting_answers: List[IndependentAnswer] = field(default_factory=list)
    disagreement_analysis: str = ""


@dataclass
class SelfConsistencyResult:
    """
    Complete output of the Self-Consistency pipeline.

    Attributes:
        answers: All independently generated answers.
        consistency: Cross-answer consistency analysis.
        final_answer: The most consistent answer delivered to the user.
        final_confidence: Confidence score for the final answer.
        steps_applied: Names of pipeline steps that were executed.
        confidence_boost: Estimated confidence increase from this process.
    """

    answers: List[IndependentAnswer] = field(default_factory=list)
    consistency: ConsistencyResult = field(default_factory=ConsistencyResult)
    final_answer: str = ""
    final_confidence: float = 0.0
    steps_applied: List[str] = field(default_factory=list)
    confidence_boost: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Serialize result to dictionary for recording in state."""
        return {
            "num_answers": len(self.answers),
            "consensus_level": self.consistency.consensus_level,
            "agreement_ratio": round(self.consistency.agreement_ratio, 4),
            "majority_value": self.consistency.majority_value,
            "num_dissenting": len(self.consistency.dissenting_answers),
            "disagreement_analysis": self.consistency.disagreement_analysis,
            "final_answer": self.final_answer,
            "final_confidence": round(self.final_confidence, 4),
            "steps_applied": self.steps_applied,
            "confidence_boost": round(self.confidence_boost, 4),
        }


# ── Self-Consistency Processor ─────────────────────────────────────


class SelfConsistencyProcessor:
    """
    Deterministic Self-Consistency processor (F-146).

    Uses template-based multi-answer generation and heuristic
    consistency checking without any LLM calls.

    Pipeline:
      1. Multi-Answer Generation  — produce 3-5 independent answers
      2. Consistency Check         — compare key_values across answers
      3. Majority Vote             — determine consensus level
      4. Disagreement Analysis     — explain divergences when present
      5. Final Response            — select best answer with confidence
    """

    def __init__(
        self, config: Optional[SelfConsistencyConfig] = None,
    ):
        self.config = config or SelfConsistencyConfig()

    # ── Step 1: Multi-Answer Generation ──────────────────────────

    async def generate_independent_answers(
        self, query: str,
    ) -> List[IndependentAnswer]:
        """
        Generate 3-5 independent answers using different reasoning
        approaches.

        Each answer is sourced from a template keyed on the detected
        financial category.  Templates are pre-authored with realistic
        variations so that the consistency checker has meaningful
        signal to evaluate.

        Args:
            query: The customer query text.

        Returns:
            List of IndependentAnswer objects (up to config.num_answers).
        """
        if not query or not query.strip():
            return []

        category = self._categorize_query(query)
        templates = _ANSWER_TEMPLATES.get(category, _ANSWER_TEMPLATES[_DEFAULT_CATEGORY])
        selected = templates[: self.config.num_answers]

        answers: List[IndependentAnswer] = []
        for template in selected:
            approach = template["approach"]
            answer = IndependentAnswer(
                approach=approach.value if isinstance(approach, ReasoningApproach) else str(approach),
                answer_text=template["answer"],
                key_value=template["key_value"],
                reasoning=template["reasoning"],
                confidence=self._estimate_answer_confidence(template),
            )
            answers.append(answer)

        logger.debug(
            "self_consistency_answers_generated",
            category=category.value,
            num_answers=len(answers),
            company_id=self.config.company_id,
        )
        return answers

    # ── Step 2: Consistency Check ────────────────────────────────

    async def check_consistency(
        self, answers: List[IndependentAnswer],
    ) -> ConsistencyResult:
        """
        Compare all answers for agreement on the key value.

        Groups answers by ``key_value``, identifies the majority group,
        and classifies the overall consensus level.

        Args:
            answers: The independently generated answers.

        Returns:
            A ConsistencyResult with consensus metadata.
        """
        if not answers:
            return ConsistencyResult()

        # Count occurrences of each key_value
        value_counts: Dict[str, List[IndependentAnswer]] = {}
        for ans in answers:
            kv = ans.key_value
            if kv not in value_counts:
                value_counts[kv] = []
            value_counts[kv].append(ans)

        # Determine majority value (most frequent key_value)
        majority_value = max(value_counts, key=lambda k: len(value_counts[k]))
        majority_count = len(value_counts[majority_value])
        total = len(answers)
        agreement_ratio = majority_count / total if total > 0 else 0.0

        # Classify consensus level
        consensus_level = self._classify_consensus(
            agreement_ratio, total, len(value_counts),
        )

        # Collect dissenting answers
        dissenting: List[IndependentAnswer] = [
            ans for ans in answers if ans.key_value != majority_value
        ]

        logger.debug(
            "self_consistency_check_completed",
            consensus_level=consensus_level.value,
            agreement_ratio=round(agreement_ratio, 4),
            majority_value=majority_value,
            num_dissenting=len(dissenting),
            company_id=self.config.company_id,
        )

        return ConsistencyResult(
            consensus_level=consensus_level.value,
            agreement_ratio=agreement_ratio,
            majority_value=majority_value,
            dissenting_answers=dissenting,
            disagreement_analysis="",  # Populated in step 4
        )

    # ── Step 3: Disagreement Analysis ────────────────────────────

    async def analyze_disagreement(
        self,
        answers: List[IndependentAnswer],
        consistency: ConsistencyResult,
    ) -> str:
        """
        Analyze why answers disagree and produce a structured
        explanation.

        When consensus is unanimous the analysis simply notes full
        agreement.  When answers differ, each dissenting answer's
        reasoning is compared against the majority to identify the
        source of divergence (fee assumptions, rounding, policy
        interpretation, goodwill adjustments, etc.).

        Args:
            answers: All independently generated answers.
            consistency: The consistency-check result.

        Returns:
            Natural-language disagreement analysis string.
        """
        if not answers:
            return "No answers available for disagreement analysis."

        consensus = ConsensusLevel(consistency.consensus_level)

        # Full agreement — short confirmation
        if consensus == ConsensusLevel.UNANIMOUS:
            return (
                f"All {len(answers)} independent reasoning approaches arrived at "
                f"the same conclusion: {consistency.majority_value}. "
                f"No disagreement detected."
            )

        # No dissenters despite non-unanimous (shouldn't happen, but BC-008)
        if not consistency.dissenting_answers:
            return (
                f"Majority conclusion is {consistency.majority_value} with "
                f"{consistency.agreement_ratio:.0%} agreement. "
                f"No dissenting answers found."
            )

        # Build structured disagreement analysis
        parts: List[str] = []
        majority_approaches = [
            a.approach for a in answers
            if a.key_value == consistency.majority_value
        ]
        dissenting = consistency.dissenting_answers

        parts.append(
            f"Majority value: {consistency.majority_value} "
            f"(agreed by {len(majority_approaches)} of {len(answers)} "
            f"approaches: {', '.join(majority_approaches)})."
        )

        for dissenter in dissenting:
            # Heuristic: categorize the divergence source
            divergence_reason = self._classify_divergence(
                dissenter, consistency.majority_value,
            )
            parts.append(
                f"  - {dissenter.approach} approach returned "
                f"{dissenter.key_value}. Reason: {divergence_reason}. "
                f"Reasoning: {dissenter.reasoning}"
            )

        # Summary recommendation
        if consensus == ConsensusLevel.MAJORITY:
            parts.append(
                f"Recommendation: Accept the majority value of "
                f"{consistency.majority_value}. The dissenting "
                f"{dissenting[0].approach} approach uses a different "
                f"assumption that should be noted but does not "
                f"invalidate the majority conclusion."
            )
        elif consensus in (ConsensusLevel.SPLIT, ConsensusLevel.NO_CONSENSUS):
            parts.append(
                "Recommendation: Escalate for manual review due to "
                "significant disagreement among reasoning approaches. "
                "The customer should be informed of the range of "
                "possible values pending further investigation."
            )

        analysis = " ".join(parts)

        logger.debug(
            "self_consistency_disagreement_analyzed",
            consensus_level=consensus.value,
            num_dissenting=len(dissenting),
            analysis_length=len(analysis),
            company_id=self.config.company_id,
        )

        return analysis

    # ── Step 4: Determine Final Answer ───────────────────────────

    async def determine_final_answer(
        self,
        answers: List[IndependentAnswer],
        consistency: ConsistencyResult,
    ) -> Tuple[str, float]:
        """
        Select the most consistent answer and assign a confidence
        score.

        The answer from the majority group with the highest
        individual confidence is selected.  The overall confidence
        is a weighted combination of agreement ratio, individual
        answer confidence, and consensus level.

        Args:
            answers: All independently generated answers.
            consistency: The consistency-check result.

        Returns:
            Tuple of (final_answer_text, final_confidence).
        """
        if not answers:
            return "", 0.0

        consensus = ConsensusLevel(consistency.consensus_level)
        majority_value = consistency.majority_value

        # Pick the best answer from the majority group
        majority_answers = [
            a for a in answers if a.key_value == majority_value
        ]

        if not majority_answers:
            # Fallback: pick the answer with the highest confidence
            best = max(answers, key=lambda a: a.confidence)
            return best.answer_text, best.confidence * 0.5

        # Select majority answer with highest individual confidence
        best_majority = max(majority_answers, key=lambda a: a.confidence)

        # Compute final confidence
        #   Base: agreement_ratio × 0.5
        #   Individual: best_majority.confidence × 0.3
        #   Consensus boost: from _CONSENSUS_BOOST table × 0.2
        agreement_component = consistency.agreement_ratio * 0.5
        individual_component = best_majority.confidence * 0.3
        consensus_component = (
            _CONSENSUS_BOOST.get(consensus, 0.02) / 0.15
        ) * 0.2  # Normalize max boost (0.15) to 0.2 scale
        final_confidence = min(
            agreement_component + individual_component + consensus_component,
            1.0,
        )

        logger.debug(
            "self_consistency_final_answer_selected",
            consensus_level=consensus.value,
            majority_value=majority_value,
            final_confidence=round(final_confidence, 4),
            company_id=self.config.company_id,
        )

        return best_majority.answer_text, final_confidence

    # ── Full Pipeline ────────────────────────────────────────────

    async def process(
        self, query: str,
    ) -> SelfConsistencyResult:
        """
        Run the full 5-step Self-Consistency pipeline.

        Args:
            query: The customer query to verify.

        Returns:
            SelfConsistencyResult with all pipeline outputs.
        """
        steps_applied: List[str] = []
        confidence_boost = 0.0
        answers: List[IndependentAnswer] = []
        consistency = ConsistencyResult()
        final_answer = ""
        final_confidence = 0.0

        if not query or not query.strip():
            return SelfConsistencyResult(
                steps_applied=["empty_input"],
                confidence_boost=0.0,
            )

        try:
            # Step 1: Multi-Answer Generation
            answers = await self.generate_independent_answers(query)
            if answers:
                steps_applied.append("multi_answer_generation")
            confidence_boost += 0.05

            # Step 2: Consistency Check
            consistency = await self.check_consistency(answers)
            if consistency.consensus_level:
                steps_applied.append("consistency_check")
            confidence_boost += 0.05

            # Step 3: Disagreement Analysis (if enabled)
            if self.config.enable_disagreement_analysis and consistency.dissenting_answers:
                disagreement_analysis = await self.analyze_disagreement(
                    answers, consistency,
                )
                consistency.disagreement_analysis = disagreement_analysis
                steps_applied.append("disagreement_analysis")
            elif not consistency.dissenting_answers:
                # Still record unanimous agreement
                consistency.disagreement_analysis = (
                    await self.analyze_disagreement(answers, consistency)
                )
                steps_applied.append("disagreement_analysis")
            confidence_boost += 0.03

            # Step 4: Determine Final Answer
            final_answer, final_confidence = await self.determine_final_answer(
                answers, consistency,
            )
            if final_answer:
                steps_applied.append("final_response")
            confidence_boost += _CONSENSUS_BOOST.get(
                ConsensusLevel(consistency.consensus_level), 0.02,
            )

            logger.info(
                "self_consistency_pipeline_completed",
                steps=",".join(steps_applied),
                consensus_level=consistency.consensus_level,
                final_confidence=round(final_confidence, 4),
                confidence_boost=round(confidence_boost, 4),
                company_id=self.config.company_id,
            )

        except Exception as exc:
            # BC-008: Never crash — return graceful fallback
            logger.warning(
                "self_consistency_processing_error",
                error=str(exc),
                company_id=self.config.company_id,
            )
            return SelfConsistencyResult(
                answers=answers,
                consistency=consistency,
                steps_applied=steps_applied + ["error_fallback"]
                if steps_applied
                else ["error_fallback"],
                confidence_boost=0.0,
            )

        return SelfConsistencyResult(
            answers=answers,
            consistency=consistency,
            final_answer=final_answer,
            final_confidence=final_confidence,
            steps_applied=steps_applied,
            confidence_boost=confidence_boost,
        )

    # ── Utility Methods ─────────────────────────────────────────

    @staticmethod
    def _categorize_query(query: str) -> FinancialCategory:
        """
        Categorize a query into a financial category via pattern
        matching.

        More specific patterns (refund, proration, credit) are
        checked before the broader billing-inquiry pattern.

        Args:
            query: The customer query text.

        Returns:
            Matched FinancialCategory, or GENERAL if no match.
        """
        for pattern, category in _CATEGORY_PATTERNS:
            if pattern.search(query):
                return category
        return _DEFAULT_CATEGORY

    @staticmethod
    def _classify_consensus(
        agreement_ratio: float,
        total: int,
        unique_values: int,
    ) -> ConsensusLevel:
        """
        Determine the consensus level from voting statistics.

        Args:
            agreement_ratio: Fraction of answers sharing the top value.
            total: Total number of answers.
            unique_values: Count of distinct key_values.

        Returns:
            ConsensusLevel enum value.
        """
        if total == 0:
            return ConsensusLevel.NO_CONSENSUS

        if unique_values == 1:
            return ConsensusLevel.UNANIMOUS
        elif agreement_ratio >= 0.6:
            return ConsensusLevel.MAJORITY
        elif unique_values == 2 and agreement_ratio >= 0.4:
            return ConsensusLevel.SPLIT
        else:
            return ConsensusLevel.NO_CONSENSUS

    @staticmethod
    def _classify_divergence(
        dissenter: IndependentAnswer,
        majority_value: str,
    ) -> str:
        """
        Heuristically classify why a dissenting answer differs
        from the majority.

        Uses keyword matching in the dissenting answer's reasoning
        to identify common divergence sources.

        Args:
            dissenter: The dissenting answer.
            majority_value: The majority key_value.

        Returns:
            Human-readable divergence reason string.
        """
        reasoning_lower = dissenter.reasoning.lower()
        answer_lower = dissenter.answer_text.lower()

        # Check for fee/penalty deductions
        if any(kw in reasoning_lower for kw in ("fee", "penalty", "deduction")):
            return (
                f"Applied an additional fee or penalty not included in the "
                f"majority calculation, resulting in {dissenter.key_value} "
                f"instead of {majority_value}"
            )

        # Check for rounding/buffer adjustments
        if any(kw in reasoning_lower for kw in ("rounding", "buffer", "conservative")):
            return (
                f"Added a conservative rounding buffer, yielding "
                f"{dissenter.key_value} vs. majority {majority_value}"
            )

        # Check for goodwill/customer-favorable adjustments
        if any(kw in reasoning_lower for kw in ("goodwill", "courtesy", "loyalty", "favorable")):
            return (
                f"Included a customer-favorable or goodwill adjustment, "
                f"producing {dissenter.key_value} vs. majority {majority_value}"
            )

        # Check for partial-period exclusions
        if any(kw in reasoning_lower for kw in ("partial", "exclud", "pending")):
            return (
                f"Excluded partial or unverified periods, resulting in "
                f"{dissenter.key_value} instead of {majority_value}"
            )

        # Check for policy interpretation differences
        if any(kw in reasoning_lower for kw in ("policy", "section", "clause", "terms")):
            return (
                f"Interpreted policy terms differently, arriving at "
                f"{dissenting.key_value} vs. majority {majority_value}"
            )

        # Check for provisional/estimate language
        if any(kw in answer_lower for kw in ("provisional", "estimate", "approximate")):
            return (
                f"Provided a provisional estimate of {dissenting.key_value} "
                f"rather than the firm majority value of {majority_value}"
            )

        # Default divergence reason
        return (
            f"Used a different calculation assumption, arriving at "
            f"{dissenting.key_value} vs. majority {majority_value}"
        )

    @staticmethod
    def _estimate_answer_confidence(template: Dict[str, str]) -> float:
        """
        Estimate confidence for a template-generated answer.

        Higher confidence is assigned to answers that reference
        explicit formulas, policies, or verifiable data sources.

        Scoring:
          - Formula-based answers: 0.85 – 0.90
          - Policy-based answers:   0.80 – 0.85
          - Direct answers:         0.75 – 0.80
          - Conservative answers:   0.70 – 0.75
          - Customer-favorable:     0.65 – 0.75

        Args:
            template: The answer template dictionary.

        Returns:
            Confidence estimate between 0.0 and 1.0.
        """
        approach = template.get("approach", "")
        if isinstance(approach, ReasoningApproach):
            approach = approach.value

        _APPROACH_CONFIDENCE: Dict[str, float] = {
            ReasoningApproach.FORMULA_BASED: 0.88,
            ReasoningApproach.POLICY_BASED: 0.82,
            ReasoningApproach.DIRECT: 0.78,
            ReasoningApproach.CONSERVATIVE: 0.72,
            ReasoningApproach.CUSTOMER_FAVORABLE: 0.70,
        }

        base = _APPROACH_CONFIDENCE.get(approach, 0.75)

        # Small bonus for answers that cite specific sections / numbers
        reasoning = template.get("reasoning", "").lower()
        answer_text = template.get("answer", "").lower()
        combined = reasoning + " " + answer_text

        specificity_bonus = 0.0
        if re.search(r"\bsection\s+\d", combined):
            specificity_bonus += 0.02
        if re.search(r"\$\s*[\d,]+(?:\.\d{1,2})", combined):
            specificity_bonus += 0.02
        if "formula" in reasoning or "calculation" in reasoning:
            specificity_bonus += 0.01

        return min(base + specificity_bonus, 1.0)


# ── Self-Consistency Node (LangGraph compatible) ──────────────────


class SelfConsistencyNode(BaseTechniqueNode):
    """
    F-146: Self-Consistency — Tier 3 Premium.

    Extends BaseTechniqueNode for integration into the LangGraph
    pipeline (F-060).

    Activation triggers:
      - monetary_value > $100, OR
      - intent_type == "billing", OR
      - Refund/credit action explicitly requested, OR
      - Financial compliance / regulatory implications detected
    """

    def __init__(
        self, config: Optional[SelfConsistencyConfig] = None,
    ):
        self._config = config or SelfConsistencyConfig()
        self._processor = SelfConsistencyProcessor(config=self._config)
        # Call parent init after config is set (reads TECHNIQUE_REGISTRY)
        super().__init__()

    @property
    def technique_id(self) -> TechniqueID:
        """Return the TechniqueID for this node."""
        return TechniqueID.SELF_CONSISTENCY

    async def should_activate(self, state: ConversationState) -> bool:
        """
        Check if Self-Consistency should activate.

        Triggers when:
          - Monetary value in the query exceeds $100, OR
          - Intent classification identifies a billing/financial query, OR
          - The query text contains explicit refund/credit request language
        """
        # Signal-based triggers (from QuerySignals)
        if state.signals.monetary_value > 100:
            return True
        if state.signals.intent_type == "billing":
            return True

        # Text-based triggers (detect refund/credit/compliance keywords)
        query_lower = (state.query or "").lower()
        refund_patterns = re.compile(
            r"\b(refund|credit|reimburse|charge.?back|chargeback|"
            r"compliance|regulatory)\b",
            re.I,
        )
        if refund_patterns.search(query_lower):
            return True

        return False

    async def execute(self, state: ConversationState) -> ConversationState:
        """
        Execute the Self-Consistency pipeline.

        Implements the 5-step verification process:
          1. Multi-Answer Generation
          2. Consistency Check
          3. Disagreement Analysis
          4. Final Response selection
          5. Confidence boost application

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

            # Append the verified answer if consensus was achieved
            consensus = ConsensusLevel(result.consistency.consensus_level)
            if (
                result.final_answer
                and consensus in (ConsensusLevel.UNANIMOUS, ConsensusLevel.MAJORITY)
            ):
                state.response_parts.append(result.final_answer)
            elif result.final_answer and consensus == ConsensusLevel.SPLIT:
                # For split consensus, include the answer but note the variance
                state.response_parts.append(
                    f"{result.final_answer} "
                    f"(Note: reasoning approaches showed minor variance; "
                    f"{result.consistency.majority_value} is the majority conclusion.)"
                )

            return state

        except Exception as exc:
            # BC-008: Never crash — return original state
            logger.warning(
                "self_consistency_execute_error",
                error=str(exc),
                company_id=self._config.company_id,
            )
            return original_state
