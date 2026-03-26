"""
PARWA Multi-Query Generator.

Implements multi-query retrieval technique by generating
multiple variations of the user's query to improve
recall in vector search.
"""
from typing import Optional, Dict, Any, List, Callable
from uuid import UUID
from datetime import datetime, timezone
import json
import re

from pydantic import BaseModel, Field, ConfigDict

from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class QueryVariation(BaseModel):
    """
    A single query variation.
    """
    original_query: str
    variation: str
    variation_type: str  # synonym, rephrase, expand, narrow
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)

    model_config = ConfigDict(
        use_enum_values=True)


class MultiQueryResult(BaseModel):
    """
    Result from multi-query generation.
    """
    original_query: str
    variations: List[QueryVariation]
    total_queries: int = Field(default=1)
    generation_method: str = "rule_based"

    model_config = ConfigDict(
        use_enum_values=True)


class MultiQueryConfig(BaseModel):
    """
    Configuration for Multi-Query Generator.
    """
    num_variations: int = Field(default=3, ge=1, le=10)
    variation_types: List[str] = Field(
        default=["rephrase", "synonym", "expand"]
    )
    include_original: bool = Field(default=True)
    min_variation_similarity: float = Field(default=0.3, ge=0.0, le=1.0)
    max_query_length: int = Field(default=500)

    model_config = ConfigDict(
        use_enum_values=True)


class MultiQueryGenerator:
    """
    Multi-Query Generator for improved retrieval.

    Features:
    - Generate multiple query variations
    - Multiple variation strategies (rephrase, synonym, expand)
    - LLM-powered or rule-based generation
    - Configurable number of variations
    - Query deduplication
    """

    # Synonym patterns for common query terms
    SYNONYM_PATTERNS = {
        "how do i": ["how can i", "what is the way to", "steps to"],
        "what is": ["explain", "describe", "tell me about"],
        "why": ["what is the reason", "what causes", "how come"],
        "when": ["at what time", "on what date", "how soon"],
        "where": ["in what location", "what place", "which area"],
        "help": ["assist", "support", "guidance"],
        "problem": ["issue", "difficulty", "trouble"],
        "fix": ["resolve", "solve", "repair"],
        "change": ["modify", "update", "alter"],
        "create": ["make", "build", "generate"],
        "remove": ["delete", "eliminate", "clear"],
        "find": ["search", "locate", "look for"],
        "show": ["display", "view", "see"],
        "get": ["obtain", "receive", "acquire"],
        "set up": ["configure", "install", "setup"],
    }

    # Expansion patterns for adding context
    EXPANSION_PATTERNS = {
        "pricing": ["cost", "price", "subscription", "billing"],
        "account": ["profile", "settings", "user account"],
        "order": ["purchase", "transaction", "checkout"],
        "refund": ["money back", "return", "cancellation"],
        "shipping": ["delivery", "shipment", "tracking"],
        "payment": ["billing", "checkout", "transaction"],
        "product": ["item", "goods", "merchandise"],
        "service": ["support", "assistance", "help"],
    }

    def __init__(
        self,
        llm_client: Optional[Any] = None,
        config: Optional[MultiQueryConfig] = None
    ) -> None:
        """
        Initialize Multi-Query Generator.

        Args:
            llm_client: Optional LLM client for advanced generation
            config: Multi-query configuration
        """
        self.llm_client = llm_client
        self.config = config or MultiQueryConfig()

        self._generation_count = 0

        logger.info({
            "event": "multi_query_initialized",
            "num_variations": self.config.num_variations,
            "variation_types": self.config.variation_types,
            "has_llm_client": llm_client is not None,
        })

    def generate(
        self,
        query: str,
        num_variations: Optional[int] = None
    ) -> MultiQueryResult:
        """
        Generate query variations.

        Args:
            query: Original query
            num_variations: Number of variations (overrides config)

        Returns:
            MultiQueryResult with all variations

        Raises:
            ValueError: If query is empty
        """
        if not query or not query.strip():
            raise ValueError("Query cannot be empty")

        num_variations = num_variations or self.config.num_variations
        query = query.strip()

        variations: List[QueryVariation] = []

        # Generate variations using different strategies
        for variation_type in self.config.variation_types:
            if len(variations) >= num_variations:
                break

            generated = self._generate_by_type(query, variation_type)
            for var in generated:
                if len(variations) >= num_variations:
                    break
                if self._is_unique_variation(var, variations):
                    variations.append(var)

        # If LLM client available, enhance with LLM-generated variations
        if self.llm_client and len(variations) < num_variations:
            llm_variations = self._generate_with_llm(
                query, num_variations - len(variations)
            )
            for var in llm_variations:
                if self._is_unique_variation(var, variations):
                    variations.append(var)

        # Add original query if configured
        if self.config.include_original:
            original_variation = QueryVariation(
                original_query=query,
                variation=query,
                variation_type="original",
                confidence=1.0
            )
            variations.insert(0, original_variation)

        self._generation_count += 1

        logger.info({
            "event": "multi_query_generated",
            "original_query_length": len(query),
            "variations_count": len(variations),
            "variation_types_used": list(set(v.variation_type for v in variations)),
        })

        return MultiQueryResult(
            original_query=query,
            variations=variations,
            total_queries=len(variations),
            generation_method="llm" if self.llm_client else "rule_based"
        )

    def get_all_queries(self, result: MultiQueryResult) -> List[str]:
        """
        Extract all query strings from result.

        Args:
            result: MultiQueryResult

        Returns:
            List of query strings
        """
        return [v.variation for v in result.variations]

    def get_embeddings_for_queries(
        self,
        result: MultiQueryResult,
        embedding_fn: Callable[[str], List[float]]
    ) -> Dict[str, List[float]]:
        """
        Generate embeddings for all query variations.

        Args:
            result: MultiQueryResult
            embedding_fn: Function to generate embeddings

        Returns:
            Dict mapping query text to embedding
        """
        embeddings: Dict[str, List[float]] = {}

        for variation in result.variations:
            try:
                embeddings[variation.variation] = embedding_fn(variation.variation)
            except Exception as e:
                logger.error({
                    "event": "query_embedding_failed",
                    "query": variation.variation[:50],
                    "error": str(e),
                })

        return embeddings

    def get_stats(self) -> Dict[str, Any]:
        """
        Get generator statistics.

        Returns:
            Dict with generator stats
        """
        return {
            "generation_count": self._generation_count,
            "config": self.config.model_dump(),
            "has_llm_client": self.llm_client is not None,
        }

    def _generate_by_type(
        self,
        query: str,
        variation_type: str
    ) -> List[QueryVariation]:
        """
        Generate variations by type.

        Args:
            query: Original query
            variation_type: Type of variation to generate

        Returns:
            List of QueryVariation
        """
        if variation_type == "rephrase":
            return self._rephrase(query)
        elif variation_type == "synonym":
            return self._synonym_replace(query)
        elif variation_type == "expand":
            return self._expand(query)
        elif variation_type == "narrow":
            return self._narrow(query)
        else:
            return []

    def _rephrase(self, query: str) -> List[QueryVariation]:
        """
        Rephrase the query.

        Args:
            query: Original query

        Returns:
            List of rephrased variations
        """
        variations: List[QueryVariation] = []
        query_lower = query.lower()

        # Check for patterns and rephrase
        for pattern, replacements in self.SYNONYM_PATTERNS.items():
            if pattern in query_lower:
                for replacement in replacements:
                    new_query = query_lower.replace(pattern, replacement, 1)
                    # Capitalize first letter
                    new_query = new_query[0].upper() + new_query[1:] if new_query else new_query
                    variations.append(QueryVariation(
                        original_query=query,
                        variation=new_query,
                        variation_type="rephrase",
                        confidence=0.8
                    ))
                    break  # One rephrasing per pattern match

        return variations[:2]  # Limit rephrase variations

    def _synonym_replace(self, query: str) -> List[QueryVariation]:
        """
        Replace words with synonyms.

        Args:
            query: Original query

        Returns:
            List of synonym-replaced variations
        """
        variations: List[QueryVariation] = []
        query_lower = query.lower()

        for pattern, synonyms in self.SYNONYM_PATTERNS.items():
            if pattern in query_lower:
                for synonym in synonyms[:1]:  # Use first synonym
                    new_query = re.sub(
                        re.escape(pattern),
                        synonym,
                        query_lower,
                        count=1,
                        flags=re.IGNORECASE
                    )
                    new_query = new_query[0].upper() + new_query[1:] if new_query else new_query
                    variations.append(QueryVariation(
                        original_query=query,
                        variation=new_query,
                        variation_type="synonym",
                        confidence=0.7
                    ))
                    break

        return variations

    def _expand(self, query: str) -> List[QueryVariation]:
        """
        Expand query with related terms.

        Args:
            query: Original query

        Returns:
            List of expanded variations
        """
        variations: List[QueryVariation] = []
        query_lower = query.lower()

        for pattern, expansions in self.EXPANSION_PATTERNS.items():
            if pattern in query_lower:
                # Add related terms
                expansion = expansions[0]
                new_query = f"{query} ({expansion})"
                variations.append(QueryVariation(
                    original_query=query,
                    variation=new_query,
                    variation_type="expand",
                    confidence=0.6
                ))
                break

        return variations

    def _narrow(self, query: str) -> List[QueryVariation]:
        """
        Narrow the query scope.

        Args:
            query: Original query

        Returns:
            List of narrowed variations
        """
        variations: List[QueryVariation] = []

        # Add specificity qualifiers
        qualifiers = ["specifically", "exactly", "precisely"]
        for qualifier in qualifiers[:1]:
            new_query = f"{query} {qualifier}"
            variations.append(QueryVariation(
                original_query=query,
                variation=new_query,
                variation_type="narrow",
                confidence=0.5
            ))

        return variations

    def _generate_with_llm(
        self,
        query: str,
        count: int
    ) -> List[QueryVariation]:
        """
        Generate variations using LLM.

        Args:
            query: Original query
            count: Number of variations to generate

        Returns:
            List of LLM-generated variations
        """
        variations: List[QueryVariation] = []

        if not self.llm_client:
            return variations

        try:
            prompt = f"""Generate {count} different ways to ask the following question.
Each variation should maintain the same intent but use different wording.
Return only the variations, one per line, numbered.

Question: {query}

Variations:"""

            response = self._call_llm(prompt)

            # Parse LLM response
            lines = response.strip().split("\n")
            for line in lines:
                # Remove numbering
                cleaned = re.sub(r"^\d+[\.\)]\s*", "", line).strip()
                if cleaned and cleaned.lower() != query.lower():
                    variations.append(QueryVariation(
                        original_query=query,
                        variation=cleaned,
                        variation_type="llm_generated",
                        confidence=0.9
                    ))

        except Exception as e:
            logger.error({
                "event": "llm_variation_failed",
                "error": str(e),
            })

        return variations

    def _call_llm(self, prompt: str) -> str:
        """
        Call the LLM.

        Args:
            prompt: Generation prompt

        Returns:
            Generated text
        """
        if hasattr(self.llm_client, "invoke"):
            response = self.llm_client.invoke(prompt)
            return response.content if hasattr(response, "content") else str(response)

        if hasattr(self.llm_client, "chat") and hasattr(self.llm_client.chat, "completions"):
            response = self.llm_client.chat.completions.create(
                model=getattr(self.llm_client, "model_name", "gpt-3.5-turbo"),
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200,
                temperature=0.7
            )
            return response.choices[0].message.content

        if callable(self.llm_client):
            return str(self.llm_client(prompt))

        raise ValueError("Unsupported LLM client interface")

    def _is_unique_variation(
        self,
        new_variation: QueryVariation,
        existing: List[QueryVariation]
    ) -> bool:
        """
        Check if variation is unique.

        Args:
            new_variation: New variation to check
            existing: Existing variations

        Returns:
            True if unique, False if duplicate
        """
        new_lower = new_variation.variation.lower().strip()
        for var in existing:
            if var.variation.lower().strip() == new_lower:
                return False
        return True
