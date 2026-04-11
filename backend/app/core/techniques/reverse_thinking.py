"""
F-141: Reverse Thinking — Tier 2 Conditional AI Reasoning Technique

Activates when confidence < 0.7 OR previous_response_status is
"rejected" or "corrected". Uses deterministic heuristic-based
inversion reasoning (no LLM calls) to derive correct answers by:

  1. Problem Statement   — formulate core question from query
  2. Inversion Generation — generate WRONG answer hypotheses
  3. Error Analysis       — analyze WHY wrong answers are wrong
  4. Inversion            — invert wrong logic to derive correct answer
  5. Validation           — validate against known facts and policies

Performance target: ~300 tokens, sub-100ms processing.

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

logger = get_logger("reverse_thinking")


# ── Error Types ─────────────────────────────────────────────────────


class ErrorType(str, Enum):
    """Predefined error categories for wrong hypothesis analysis."""
    FACTUAL_INCORRECT = "factual_incorrect"
    POLICY_VIOLATION = "policy_violation"
    LOGICAL_FALLACY = "logical_fallacy"
    INCOMPLETE_INFO = "incomplete_info"
    MISINTERPRETATION = "misinterpretation"
    WRONG_SCOPE = "wrong_scope"


# ── Problem Categories ──────────────────────────────────────────────


class ProblemCategory(str, Enum):
    """Categories of customer support queries for pattern matching."""
    BILLING = "billing"
    REFUND = "refund"
    SUBSCRIPTION = "subscription"
    TECHNICAL = "technical"
    ACCOUNT = "account"
    GENERAL = "general"


# ── Category Pattern Matching ───────────────────────────────────────


# Query patterns mapped to problem categories
_CATEGORY_PATTERNS: List[Tuple[re.Pattern, ProblemCategory]] = [
    # Billing patterns
    (re.compile(r"\b(bill|billing|invoice|charge|payment|fee|cost|price)\b", re.I),
     ProblemCategory.BILLING),
    # Refund patterns
    (re.compile(r"\b(refund|money.?back|reimburse|credit.?back|return.?payment)\b", re.I),
     ProblemCategory.REFUND),
    # Subscription patterns
    (re.compile(r"\b(subscri|plan|upgrade|downgrade|cancel.?subscription|renew|trial|tier)\b", re.I),
     ProblemCategory.SUBSCRIPTION),
    # Technical patterns
    (re.compile(r"\b(bug|error|crash|broken|not.?work|fix|issue|slow|fail|login|password|install|setup|config|connect|sync|integration)\b", re.I),
     ProblemCategory.TECHNICAL),
    # Account patterns
    (re.compile(r"\b(account|profile|email|username|settings|notification|pref)\b", re.I),
     ProblemCategory.ACCOUNT),
]

# Default category fallback
_DEFAULT_CATEGORY = ProblemCategory.GENERAL


# ── Wrong Answer Templates (per category) ───────────────────────────


_WRONG_ANSWER_TEMPLATES: Dict[ProblemCategory, List[Dict[str, str]]] = {
    ProblemCategory.BILLING: [
        {
            "hypothesis": "Your billing issue cannot be resolved; you must pay the full amount immediately regardless of discrepancies.",
            "error_type": ErrorType.POLICY_VIOLATION,
            "error_reason": "This ignores the dispute and review process available for billing discrepancies.",
            "inversion": "Billing discrepancies can be reviewed and disputed. Please provide the charge details so we can investigate and apply any applicable corrections.",
        },
        {
            "hypothesis": "The charge is correct and no further action is needed on your part.",
            "error_type": ErrorType.FACTUAL_INCORRECT,
            "error_reason": "Assumes the charge is correct without verification against the customer's account records.",
            "inversion": "Let's verify the charge against your account records. Could you provide the transaction date and amount so I can check for any discrepancies?",
        },
        {
            "hypothesis": "All billing issues are automatically resolved within 24 hours without any action required.",
            "error_type": ErrorType.INCOMPLETE_INFO,
            "error_reason": "Billing resolution timelines vary by issue type and may require customer action or documentation.",
            "inversion": "Billing resolution timelines depend on the issue type. Some charges can be reviewed quickly, while disputes may take 3-5 business days. Let me check the specifics of your case.",
        },
    ],
    ProblemCategory.REFUND: [
        {
            "hypothesis": "Refunds are never issued under any circumstances once a payment is made.",
            "error_type": ErrorType.POLICY_VIOLATION,
            "error_reason": "This contradicts the standard refund policy which allows refunds within the eligible period.",
            "inversion": "Refunds may be available depending on the timing and circumstances. Let me review your order to check eligibility based on our refund policy.",
        },
        {
            "hypothesis": "Your refund has already been processed and there is nothing more to discuss.",
            "error_type": ErrorType.FACTUAL_INCORRECT,
            "error_reason": "States the refund is processed without verifying the actual refund status in the system.",
            "inversion": "Let me verify the current status of your refund request. I'll check the processing timeline and confirm when you can expect to receive it.",
        },
        {
            "hypothesis": "Refunds take only 1 hour to appear in your account after being approved.",
            "error_type": ErrorType.FACTUAL_INCORRECT,
            "error_reason": "Refund processing times are typically 3-10 business days depending on the payment method.",
            "inversion": "Once approved, refund processing typically takes 3-10 business days depending on your payment method. I can provide more specific timing based on your case.",
        },
    ],
    ProblemCategory.SUBSCRIPTION: [
        {
            "hypothesis": "You cannot change your subscription plan at any time; you are locked in permanently.",
            "error_type": ErrorType.POLICY_VIOLATION,
            "error_reason": "Most subscription plans allow changes, upgrades, or downgrades with proper notice.",
            "inversion": "You can modify your subscription plan. Let me walk you through the available options and any prorated charges or credits that may apply.",
        },
        {
            "hypothesis": "Canceling your subscription will immediately delete all your data and account history.",
            "error_type": ErrorType.MISINTERPRETATION,
            "error_reason": "Cancellation does not typically result in immediate data deletion; there is usually a grace period.",
            "inversion": "Canceling your subscription does not immediately delete your data. You'll typically retain access until the end of your current billing period, with a grace period for data export.",
        },
        {
            "hypothesis": "The free trial automatically charges you the highest tier price with no notification.",
            "error_type": ErrorType.FACTUAL_INCORRECT,
            "error_reason": "Trial conversions require customer consent and typically convert to the selected plan, not the highest tier.",
            "inversion": "Trial periods provide full access, and you'll be notified before any charges. You can choose which plan fits your needs before the trial ends.",
        },
    ],
    ProblemCategory.TECHNICAL: [
        {
            "hypothesis": "The technical issue is entirely your fault and you need to fix it yourself with no support available.",
            "error_type": ErrorType.POLICY_VIOLATION,
            "error_reason": "Technical support is a standard service; issues should be investigated before assigning blame.",
            "inversion": "Let's troubleshoot this issue together. I'll need some details about what you're experiencing so we can identify the root cause and find a solution.",
        },
        {
            "hypothesis": "The only solution is to completely reinstall the application and delete all your current data.",
            "error_type": ErrorType.WRONG_SCOPE,
            "error_reason": "Suggests the most extreme solution first without exploring less disruptive alternatives.",
            "inversion": "Before considering a reinstall, let's try some less disruptive troubleshooting steps. Can you describe the exact error message or behavior you're seeing?",
        },
        {
            "hypothesis": "This technical issue affects all users equally and there is no workaround.",
            "error_type": ErrorType.FACTUAL_INCORRECT,
            "error_reason": "Makes an unverified claim about scope and impact without investigation.",
            "inversion": "Let me check if this is a known issue with an existing workaround. In the meantime, could you share your browser version and operating system so I can narrow down the cause?",
        },
    ],
    ProblemCategory.ACCOUNT: [
        {
            "hypothesis": "Your account settings cannot be changed once the account is created.",
            "error_type": ErrorType.POLICY_VIOLATION,
            "error_reason": "Account settings are designed to be modifiable for user flexibility.",
            "inversion": "Most account settings can be updated at any time. Let me know which specific settings you'd like to change and I'll guide you through the process.",
        },
        {
            "hypothesis": "To change your email, you must create an entirely new account and lose all your data.",
            "error_type": ErrorType.WRONG_SCOPE,
            "error_reason": "Email changes should be possible within the existing account without data loss.",
            "inversion": "You can update your email address within your current account. I'll send a verification link to your new email to confirm the change, and your data will remain intact.",
        },
        {
            "hypothesis": "Account-related requests are processed instantly with no verification required.",
            "error_type": ErrorType.FACTUAL_INCORRECT,
            "error_reason": "Security verification is required for account changes to protect user data.",
            "inversion": "For account security, some changes require identity verification. I'll guide you through the verification steps needed to complete your request safely.",
        },
    ],
    ProblemCategory.GENERAL: [
        {
            "hypothesis": "There is no solution to your problem and nothing can be done.",
            "error_type": ErrorType.LOGICAL_FALLACY,
            "error_reason": "Prematurely concludes that no solution exists without proper investigation.",
            "inversion": "Let me look into this for you. Could you provide more details about your situation so I can find the best available solution?",
        },
        {
            "hypothesis": "The standard answer applies to all cases without exception.",
            "error_type": ErrorType.WRONG_SCOPE,
            "error_reason": "Assumes a one-size-fits-all answer without considering the specifics of the customer's situation.",
            "inversion": "While there are standard processes, your specific situation may have unique aspects. Let me review the details to provide you with the most relevant guidance.",
        },
        {
            "hypothesis": "You need to wait indefinitely without any update or follow-up.",
            "error_type": ErrorType.INCOMPLETE_INFO,
            "error_reason": "Provides no timeline or follow-up mechanism, leaving the customer without actionable information.",
            "inversion": "I understand the wait can be frustrating. Let me set a clear expectation for the timeline and ensure you receive updates as your request progresses.",
        },
    ],
}


# ── Reserved Phrases (policy anchors) ───────────────────────────────


_RESERVED_PHRASES: FrozenSet[str] = frozenset({
    "refund", "cancellation", "payment", "charge", "invoice",
    "subscription", "billing", "prorated", "policy", "deadline",
    "contract", "termination", "credit", "debit", "amount",
    "dispute", "verification", "security", "timeline", "eligibility",
})

_VALIDATION_ANCHORS: FrozenSet[str] = frozenset({
    "verify", "review", "check", "investigate", "confirm",
    "available", "eligible", "within", "depending on", "based on",
    "let me", "i can", "we can", "option", "solution",
})


# ── Data Structures ──────────────────────────────────────────────────


@dataclass(frozen=True)
class ReverseThinkingConfig:
    """
    Immutable configuration for Reverse Thinking (BC-001).

    Attributes:
        company_id: Tenant identifier for company isolation.
        enable_validation: Whether to run the validation step.
        max_inversions: Maximum number of wrong hypotheses to generate.
    """

    company_id: str = ""
    enable_validation: bool = True
    max_inversions: int = 3


@dataclass
class InversionHypothesis:
    """
    A single wrong answer hypothesis with its analysis.

    Attributes:
        hypothesis_text: The generated wrong answer.
        error_type: Category of error identified.
        inversion_result: The corrected answer derived by inversion.
    """

    hypothesis_text: str = ""
    error_type: str = ""
    inversion_result: str = ""


@dataclass
class ReverseThinkingResult:
    """
    Output of the Reverse Thinking pipeline.

    Attributes:
        problem_statement: Formulated core question from the query.
        wrong_hypotheses: List of wrong answer hypotheses generated.
        error_analysis: Consolidated analysis of why wrong answers are wrong.
        inverted_answer: Best corrected answer derived through inversion.
        validation_status: Result of validation against policies.
        steps_applied: Names of pipeline steps that were executed.
        confidence_boost: Estimated confidence increase from this process.
    """

    problem_statement: str = ""
    wrong_hypotheses: List[InversionHypothesis] = field(
        default_factory=list,
    )
    error_analysis: str = ""
    inverted_answer: str = ""
    validation_status: str = ""
    steps_applied: List[str] = field(default_factory=list)
    confidence_boost: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Serialize result to dictionary for recording in state."""
        return {
            "problem_statement": self.problem_statement,
            "wrong_hypotheses": [
                {
                    "hypothesis_text": h.hypothesis_text,
                    "error_type": h.error_type,
                    "inversion_result": h.inversion_result,
                }
                for h in self.wrong_hypotheses
            ],
            "error_analysis": self.error_analysis,
            "inverted_answer": self.inverted_answer,
            "validation_status": self.validation_status,
            "steps_applied": self.steps_applied,
            "confidence_boost": round(self.confidence_boost, 4),
        }


# ── Reverse Thinking Processor ──────────────────────────────────────


class ReverseThinkingProcessor:
    """
    Deterministic reverse thinking processor (F-141).

    Uses pattern matching and heuristic rules to simulate the
    inversion reasoning process without any LLM calls.

    Pipeline:
      1. Problem Statement   — categorize and formulate core question
      2. Inversion Generation — template-based wrong answer hypotheses
      3. Error Analysis       — identify error types in wrong answers
      4. Inversion            — derive correct answer by logical inversion
      5. Validation           — validate against reserved phrases and policies
    """

    def __init__(
        self, config: Optional[ReverseThinkingConfig] = None,
    ):
        self.config = config or ReverseThinkingConfig()

    # ── Step 1: Problem Statement ──────────────────────────────────

    async def formulate_problem_statement(
        self, query: str,
    ) -> str:
        """
        Extract and formulate the core problem statement from the query.

        Uses pattern matching to identify the query category and
        generates a structured problem statement.

        Args:
            query: The customer query text.

        Returns:
            A formatted problem statement string.
        """
        if not query or not query.strip():
            return ""

        category = self._categorize_query(query)
        category_label = category.value.replace("_", " ")

        # Extract key terms from the query
        key_terms = self._extract_key_terms(query)

        problem = (
            f"Determine the correct response for a {category_label} "
            f"query. Key terms: {', '.join(key_terms)}. "
            f"Provide accurate, policy-compliant guidance."
        )
        return problem

    # ── Step 2: Inversion Generation ───────────────────────────────

    async def generate_wrong_hypotheses(
        self, query: str, category: Optional[ProblemCategory] = None,
    ) -> List[InversionHypothesis]:
        """
        Generate wrong answer hypotheses for the given query.

        Uses template-based generation per problem category. Each
        hypothesis represents a plausible but incorrect answer.

        Args:
            query: The customer query text.
            category: Optional pre-computed category. If None, will
                be computed from the query.

        Returns:
            List of InversionHypothesis objects.
        """
        if not query or not query.strip():
            return []

        if category is None:
            category = self._categorize_query(query)

        templates = _WRONG_ANSWER_TEMPLATES.get(
            category, _WRONG_ANSWER_TEMPLATES[_DEFAULT_CATEGORY],
        )

        # Limit by max_inversions config
        selected = templates[: self.config.max_inversions]

        hypotheses: List[InversionHypothesis] = []
        for template in selected:
            hypothesis = InversionHypothesis(
                hypothesis_text=template["hypothesis"],
                error_type=template["error_type"].value,
                inversion_result=template["inversion"],
            )
            hypotheses.append(hypothesis)

        return hypotheses

    # ── Step 3: Error Analysis ─────────────────────────────────────

    async def analyze_errors(
        self,
        hypotheses: List[InversionHypothesis],
    ) -> str:
        """
        Analyze why each wrong hypothesis is incorrect.

        Consolidates error analysis across all hypotheses into a
        structured summary.

        Args:
            hypotheses: List of wrong answer hypotheses to analyze.

        Returns:
            Consolidated error analysis string.
        """
        if not hypotheses:
            return "No hypotheses to analyze."

        error_types: Dict[str, int] = {}
        reasons: List[str] = []

        for hypothesis in hypotheses:
            et = hypothesis.error_type
            error_types[et] = error_types.get(et, 0) + 1

            # Look up the error reason from templates
            reason = self._get_error_reason(hypothesis)
            if reason:
                reasons.append(reason)

        # Build analysis summary
        type_summary = ", ".join(
            f"{et}({count})" for et, count in error_types.items()
        )

        analysis = (
            f"Identified {len(hypotheses)} error pattern(s) "
            f"[{type_summary}]. "
        )

        if reasons:
            analysis += "Key findings: " + " ".join(reasons)

        return analysis

    # ── Step 4: Inversion ──────────────────────────────────────────

    async def invert_to_correct_answer(
        self,
        hypotheses: List[InversionHypothesis],
    ) -> str:
        """
        Derive the correct answer by inverting wrong answer logic.

        Selects the best inversion result from the hypotheses
        based on quality scoring (longer, more specific answers
        are preferred as they typically contain more useful guidance).

        Args:
            hypotheses: List of wrong answer hypotheses with
                their inversion results.

        Returns:
            The best inverted (correct) answer string.
        """
        if not hypotheses:
            return ""

        # Score each inversion result
        best_score = -1
        best_answer = ""

        for hypothesis in hypotheses:
            result = hypothesis.inversion_result
            if not result:
                continue
            score = self._score_inversion(result)
            if score > best_score:
                best_score = score
                best_answer = result

        return best_answer

    # ── Step 5: Validation ─────────────────────────────────────────

    async def validate_answer(
        self,
        answer: str,
        problem_statement: str = "",
    ) -> str:
        """
        Validate the inverted answer against known facts and policies.

        Checks that the answer contains validation anchors (action
        words like 'verify', 'review', etc.) and does not contain
        language that contradicts standard policies.

        Args:
            answer: The inverted answer to validate.
            problem_statement: The original problem statement for context.

        Returns:
            Validation status string: 'passed', 'warning', or 'failed'.
        """
        if not answer:
            return "failed"

        answer_lower = answer.lower()

        # Check for validation anchor phrases
        anchor_count = sum(
            1 for anchor in _VALIDATION_ANCHORS
            if anchor in answer_lower
        )

        # Check that reserved/policy terms are used correctly
        reserved_hits = sum(
            1 for phrase in _RESERVED_PHRASES
            if phrase in answer_lower
        )

        # Check for negative absolutes (sign of wrong answers)
        negative_absolutes = re.findall(
            r"\b(never|always|impossible|cannot ever|no way|nothing can)\b",
            answer_lower,
        )

        # Scoring
        if anchor_count >= 2 and not negative_absolutes:
            return "passed"
        elif anchor_count >= 1 and len(negative_absolutes) <= 1:
            return "warning"
        else:
            return "failed"

    # ── Full Pipeline ──────────────────────────────────────────────

    async def process(
        self, query: str,
    ) -> ReverseThinkingResult:
        """
        Run the full 5-step Reverse Thinking pipeline.

        Args:
            query: The customer query to reason about.

        Returns:
            ReverseThinkingResult with all pipeline outputs.
        """
        steps_applied: List[str] = []
        confidence_boost = 0.0

        if not query or not query.strip():
            return ReverseThinkingResult(
                steps_applied=["empty_input"],
                confidence_boost=0.0,
            )

        try:
            # Step 1: Problem Statement
            problem_statement = await self.formulate_problem_statement(
                query,
            )
            if problem_statement:
                steps_applied.append("problem_statement")
            confidence_boost += 0.05

            # Step 2: Inversion Generation
            category = self._categorize_query(query)
            hypotheses = await self.generate_wrong_hypotheses(
                query, category,
            )
            if hypotheses:
                steps_applied.append("inversion_generation")
            confidence_boost += 0.05

            # Step 3: Error Analysis
            error_analysis = await self.analyze_errors(hypotheses)
            if error_analysis and error_analysis != "No hypotheses to analyze.":
                steps_applied.append("error_analysis")
            confidence_boost += 0.05

            # Step 4: Inversion
            inverted_answer = await self.invert_to_correct_answer(
                hypotheses,
            )
            if inverted_answer:
                steps_applied.append("inversion")
            confidence_boost += 0.1

            # Step 5: Validation (optional based on config)
            validation_status = "skipped"
            if self.config.enable_validation:
                validation_status = await self.validate_answer(
                    inverted_answer, problem_statement,
                )
                steps_applied.append("validation")
                if validation_status == "passed":
                    confidence_boost += 0.1
                elif validation_status == "warning":
                    confidence_boost += 0.05

        except Exception as exc:
            # BC-008: Never crash — return graceful fallback
            logger.warning(
                "reverse_thinking_processing_error",
                error=str(exc),
                company_id=self.config.company_id,
            )
            return ReverseThinkingResult(
                problem_statement=problem_statement if 'problem_statement' in dir() else "",
                wrong_hypotheses=hypotheses if 'hypotheses' in dir() else [],
                steps_applied=steps_applied + ["error_fallback"]
                if 'steps_applied' in dir() else ["error_fallback"],
                confidence_boost=0.0,
            )

        return ReverseThinkingResult(
            problem_statement=problem_statement,
            wrong_hypotheses=hypotheses,
            error_analysis=error_analysis,
            inverted_answer=inverted_answer,
            validation_status=validation_status,
            steps_applied=steps_applied,
            confidence_boost=confidence_boost,
        )

    # ── Utility Methods ───────────────────────────────────────────

    @staticmethod
    def _categorize_query(query: str) -> ProblemCategory:
        """
        Categorize a query into a problem category using pattern matching.

        Args:
            query: The customer query text.

        Returns:
            Matched ProblemCategory, or GENERAL if no match.
        """
        for pattern, category in _CATEGORY_PATTERNS:
            if pattern.search(query):
                return category
        return _DEFAULT_CATEGORY

    @staticmethod
    def _extract_key_terms(query: str) -> List[str]:
        """
        Extract key terms from a query for the problem statement.

        Uses word frequency to identify significant terms, filtering
        out common stop words.

        Args:
            query: The customer query text.

        Returns:
            List of key terms (lowercase, up to 5).
        """
        _STOP_WORDS: FrozenSet[str] = frozenset({
            "i", "me", "my", "we", "you", "your", "it", "its",
            "is", "am", "are", "was", "were", "be", "been",
            "have", "has", "had", "do", "does", "did",
            "will", "would", "could", "should", "may", "might",
            "shall", "can", "to", "of", "in", "for", "on",
            "with", "at", "by", "from", "as", "into",
            "the", "a", "an", "and", "or", "but", "if",
            "not", "no", "this", "that", "these", "those",
            "what", "how", "when", "where", "why", "who",
            "which", "about", "up", "out", "just", "so",
            "than", "too", "very", "also", "then",
        })

        words = re.findall(r"\b\w{3,}\b", query.lower())
        filtered = [w for w in words if w not in _STOP_WORDS]

        # Deduplicate while preserving order
        seen: Set[str] = set()
        unique: List[str] = []
        for word in filtered:
            if word not in seen:
                seen.add(word)
                unique.append(word)

        return unique[:5]

    @staticmethod
    def _get_error_reason(hypothesis: InversionHypothesis) -> str:
        """
        Look up the predefined error reason for a hypothesis.

        Searches all category templates to find the matching
        hypothesis text and returns its error_reason.

        Args:
            hypothesis: The hypothesis to look up.

        Returns:
            The error reason string, or empty string if not found.
        """
        for templates in _WRONG_ANSWER_TEMPLATES.values():
            for template in templates:
                if template["hypothesis"] == hypothesis.hypothesis_text:
                    return template.get("error_reason", "")
        return ""

    @staticmethod
    def _score_inversion(answer: str) -> float:
        """
        Score an inversion result for quality.

        Higher scores indicate more specific, actionable answers.

        Scoring criteria:
          - Length (longer answers typically more informative)
          - Presence of action verbs
          - Presence of specific guidance markers
          - Absence of negative absolutes

        Args:
            answer: The inversion result text.

        Returns:
            Quality score (0.0+).
        """
        if not answer:
            return 0.0

        score = 0.0

        # Length component (capped at 2.0)
        score += min(len(answer) / 100.0, 2.0)

        # Action verbs
        action_words = [
            "verify", "review", "check", "investigate", "confirm",
            "provide", "guide", "walk", "ensure", "update",
        ]
        action_hits = sum(
            1 for w in action_words if w in answer.lower()
        )
        score += action_hits * 0.5

        # Specificity markers
        specific_markers = [
            "your", "the", "based on", "depending on",
            "typically", "specific", "details",
        ]
        specific_hits = sum(
            1 for m in specific_markers if m in answer.lower()
        )
        score += specific_hits * 0.3

        # Penalty for negative absolutes
        negative_absolutes = re.findall(
            r"\b(never|always|impossible|cannot ever)\b",
            answer.lower(),
        )
        score -= len(negative_absolutes) * 1.0

        return max(score, 0.0)


# ── Reverse Thinking Node (LangGraph compatible) ──────────────────


class ReverseThinkingNode(BaseTechniqueNode):
    """
    F-141: Reverse Thinking Engine — Tier 2 Conditional.

    Extends BaseTechniqueNode for integration into the LangGraph
    pipeline (F-060).

    Activation trigger:
      - confidence_score < 0.7, OR
      - previous_response_status in ("rejected", "corrected")
    """

    def __init__(
        self, config: Optional[ReverseThinkingConfig] = None,
    ):
        self._config = config or ReverseThinkingConfig()
        self._processor = ReverseThinkingProcessor(config=self._config)
        # Call parent init after config is set (reads TECHNIQUE_REGISTRY)
        super().__init__()

    @property
    def technique_id(self) -> TechniqueID:
        """Return the TechniqueID for this node."""
        return TechniqueID.REVERSE_THINKING

    async def should_activate(self, state: ConversationState) -> bool:
        """
        Check if Reverse Thinking should activate.

        Triggers when confidence is low (< 0.7) or when a previous
        response was rejected or corrected.
        """
        return (
            state.signals.confidence_score < 0.7
            or state.signals.previous_response_status in ("rejected", "corrected")
        )

    async def execute(self, state: ConversationState) -> ConversationState:
        """
        Execute the Reverse Thinking pipeline.

        Implements the 5-step inversion reasoning process:
          1. Problem Statement
          2. Inversion Generation
          3. Error Analysis
          4. Inversion
          5. Validation

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

            # If we have a validated inverted answer, append to response parts
            if (
                result.inverted_answer
                and result.validation_status in ("passed", "warning")
            ):
                state.response_parts.append(result.inverted_answer)

            return state

        except Exception as exc:
            # BC-008: Never crash — return original state
            logger.warning(
                "reverse_thinking_execute_error",
                error=str(exc),
                company_id=self._config.company_id,
            )
            return original_state
