"""
PARWA Complexity Scorer.

Scores query complexity to determine appropriate AI tier.
"""
from typing import Dict, Any, List
import re

from shared.core_functions.logger import get_logger
from shared.smart_router.tier_config import AITier

logger = get_logger(__name__)


class ComplexityScorer:
    """
    Query Complexity Scorer.

    Scores queries from 0-10 based on:
    - Keywords and patterns
    - Query length
    - Sentiment indicators
    - Domain-specific complexity
    """

    # Simple query patterns (score 0-2)
    SIMPLE_PATTERNS = [
        r"\bwhat is\b", r"\bhow do i\b", r"\bwhere can i\b",
        r"\bhours\b", r"\bcontact\b", r"\bprice\b", r"\bcost\b",
        r"\bfaq\b", r"\bhelp\b", r"\bsimple\b", r"\bbasic\b",
        r"\bwhen\b", r"\bwho\b", r"\bwhich\b",
    ]

    # Medium complexity patterns (score 3-6)
    MEDIUM_PATTERNS = [
        r"\bwhy\b", r"\bexplain\b", r"\bhow does\b",
        r"\bcompare\b", r"\bdifference\b", r"\bvs\b",
        r"\bproblem\b", r"\bissue\b", r"\bnot working\b",
        r"\berror\b", r"\bfailed\b", r"\bstuck\b",
    ]

    # High complexity patterns (score 7-10)
    COMPLEX_PATTERNS = [
        r"\brefund\b", r"\bdispute\b", r"\bescalat\b", r"\bmanager\b",
        r"\bcomplaint\b", r"\blegal\b", r"\battorney\b", r"\bsue\b",
        r"\bcompensation\b", r"\bdamages\b", r"\bfraud\b",
        r"\bunacceptable\b", r"\bterrible\b", r"\bworst\b",
    ]

    # Escalation indicators (auto-heavy)
    ESCALATION_PATTERNS = [
        r"\bspeak to.*human\b", r"\breal person\b", r"\bagent\b",
        r"\bsupervisor\b", r"\bmanager\b", r"\bcomplaint\b",
        r"\bnever.*again\b", r"\bcancel.*subscription\b", r"\bdelete.*account\b",
    ]

    def score(self, query: str) -> int:
        """
        Score query complexity from 0-10.

        Args:
            query: Customer query text

        Returns:
            Complexity score (0=simple FAQ, 10=complex escalation)
        """
        if not query:
            return 0

        query_lower = query.lower()
        score = 0

        # Check escalation patterns first (auto-high)
        for pattern in self.ESCALATION_PATTERNS:
            if re.search(pattern, query_lower):
                return 10

        # Count pattern matches
        simple_count = sum(1 for p in self.SIMPLE_PATTERNS if re.search(p, query_lower))
        medium_count = sum(1 for p in self.MEDIUM_PATTERNS if re.search(p, query_lower))
        complex_count = sum(1 for p in self.COMPLEX_PATTERNS if re.search(p, query_lower))

        # Base score from patterns
        if complex_count >= 2:
            score = 9
        elif complex_count == 1:
            score = 7
        elif medium_count >= 2:
            score = 5
        elif medium_count == 1:
            score = 3
        elif simple_count >= 1:
            score = 1
        else:
            score = 2

        # Adjust for query length
        word_count = len(query.split())
        if word_count > 50:
            score = min(10, score + 2)
        elif word_count > 30:
            score = min(10, score + 1)

        # Adjust for question marks (multiple = more complex)
        question_count = query.count("?")
        if question_count > 2:
            score = min(10, score + 1)

        logger.debug({
            "event": "complexity_scored",
            "query_length": len(query),
            "simple_matches": simple_count,
            "medium_matches": medium_count,
            "complex_matches": complex_count,
            "final_score": score,
        })

        return score

    def get_tier_for_score(self, score: int) -> AITier:
        """
        Get recommended AI tier for complexity score.

        Args:
            score: Complexity score (0-10)

        Returns:
            AITier recommendation
        """
        if score <= 2:
            return AITier.LIGHT
        elif score <= 6:
            return AITier.MEDIUM
        else:
            return AITier.HEAVY

    def analyze(self, query: str) -> Dict[str, Any]:
        """
        Full analysis of query complexity.

        Args:
            query: Customer query text

        Returns:
            Dict with score, tier, and breakdown
        """
        score = self.score(query)
        tier = self.get_tier_for_score(score)

        return {
            "query": query[:100] + "..." if len(query) > 100 else query,
            "complexity_score": score,
            "recommended_tier": tier.value,
            "word_count": len(query.split()),
            "has_escalation_indicators": any(
                re.search(p, query.lower()) for p in self.ESCALATION_PATTERNS
            ),
        }
