"""
Query Enhancement Module for Agent Lightning.

Provides query enhancement with:
- Spelling correction
- Query expansion
- Intent clarification
- Entity normalization
- Query rewriting

Target: 94% accuracy improvement through better query understanding.
"""

from typing import Dict, Any, List, Optional, Tuple, Set
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import asyncio
import re
from collections import defaultdict

from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class EnhancementType(Enum):
    """Types of query enhancements."""
    SPELLING_CORRECTION = "spelling_correction"
    QUERY_EXPANSION = "query_expansion"
    INTENT_CLARIFICATION = "intent_clarification"
    ENTITY_NORMALIZATION = "entity_normalization"
    QUERY_REWRITING = "query_rewriting"


@dataclass
class SpellingCorrection:
    """Result of spelling correction."""
    original: str
    corrected: str
    confidence: float
    corrections: List[Tuple[str, str]] = field(default_factory=list)  # (wrong, right)

    @property
    def was_corrected(self) -> bool:
        return self.original.lower() != self.corrected.lower()


@dataclass
class QueryExpansion:
    """Result of query expansion."""
    original_query: str
    expanded_terms: List[str]
    synonyms: Dict[str, List[str]] = field(default_factory=dict)
    related_queries: List[str] = field(default_factory=list)


@dataclass
class IntentClarification:
    """Result of intent clarification."""
    original_intent: str
    clarified_intent: str
    confidence: float
    alternative_intents: List[Tuple[str, float]] = field(default_factory=list)
    clarification_questions: List[str] = field(default_factory=list)


@dataclass
class EntityNormalization:
    """Result of entity normalization."""
    original_entities: Dict[str, Any]
    normalized_entities: Dict[str, Any]
    entity_types: Dict[str, str]
    confidence: float


@dataclass
class QueryRewrite:
    """Result of query rewriting."""
    original_query: str
    rewritten_query: str
    rewrite_type: str
    improvements: List[str] = field(default_factory=list)


@dataclass
class EnhancedQuery:
    """Complete enhanced query result."""
    original_query: str
    enhanced_query: str
    spelling_correction: Optional[SpellingCorrection] = None
    expansion: Optional[QueryExpansion] = None
    intent_clarification: Optional[IntentClarification] = None
    entity_normalization: Optional[EntityNormalization] = None
    rewrite: Optional[QueryRewrite] = None
    enhancements_applied: List[EnhancementType] = field(default_factory=list)
    confidence_boost: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class SpellingCorrector:
    """
    Spelling correction for customer queries.

    Uses common misspellings dictionary and context-aware correction.
    """

    # Common misspellings in customer support context
    COMMON_MISSPELLINGS = {
        "recieved": "received",
        "recive": "receive",
        "recieving": "receiving",
        "cancelation": "cancellation",
        "cancled": "cancelled",
        "delivered": "delivered",
        "delievery": "delivery",
        "delivar": "deliver",
        "refun": "refund",
        "refound": "refund",
        "shiping": "shipping",
        "shipmnt": "shipment",
        "trakcing": "tracking",
        "trasnfer": "transfer",
        "transfr": "transfer",
        "acount": "account",
        "accunt": "account",
        "paymnet": "payment",
        "paymant": "payment",
        "subscripion": "subscription",
        "subscribtion": "subscription",
        "ordr": "order",
        "ordder": "order",
        "retrun": "return",
        "retun": "return",
        "exchnge": "exchange",
        "exhange": "exchange",
        "recepit": "receipt",
        "reciept": "receipt",
        "adress": "address",
        "addres": "address",
        "confirmaton": "confirmation",
        "confimration": "confirmation",
        "proble": "problem",
        "issu": "issue",
        "isue": "issue",
        "hlep": "help",
        "hlpe": "help",
        "suppot": "support",
        "supprt": "support",
        "custmer": "customer",
        "customr": "customer",
        "managre": "manager",
        "superviser": "supervisor",
        "complaint": "complaint",
        "complaint": "complaint",
        "complint": "complaint",
        "dispute": "dispute",
        "dispue": "dispute",
    }

    # Industry-specific terms
    INDUSTRY_TERMS = {
        "ecommerce": {
            "checkout": ["checkot", "chekout", "checkout"],
            "cart": ["kart", "crt"],
            "coupon": ["coupn", "coupen"],
            "discount": ["discnt", "discoun"],
        },
        "saas": {
            "subscription": ["subscripton", "subscribtion"],
            "billing": ["biling", "bilng"],
            "invoice": ["invoce", "invoise"],
        },
        "healthcare": {
            "appointment": ["apointment", "appointmnt"],
            "prescription": ["presciption", "perscription"],
            "insurance": ["insurence", "insurace"],
        },
        "financial": {
            "transaction": ["transacton", "transction"],
            "mortgage": ["morgage", "mortage"],
            "investment": ["investmnt", "investmet"],
        },
    }

    def __init__(self) -> None:
        """Initialize spelling corrector."""
        self._build_correction_map()

    def _build_correction_map(self) -> None:
        """Build the correction map from all sources."""
        self._correction_map = {}

        # Add common misspellings
        for wrong, right in self.COMMON_MISSPELLINGS.items():
            self._correction_map[wrong.lower()] = right

        # Add industry-specific terms
        for industry, terms in self.INDUSTRY_TERMS.items():
            for correct, misspellings in terms.items():
                for wrong in misspellings:
                    if wrong.lower() != correct.lower():
                        self._correction_map[wrong.lower()] = correct

    def correct(self, query: str) -> SpellingCorrection:
        """
        Correct spelling in a query.

        Args:
            query: Original query

        Returns:
            SpellingCorrection result
        """
        corrections = []
        words = query.split()
        corrected_words = []

        for word in words:
            # Preserve punctuation
            prefix = ""
            suffix = ""
            clean_word = word.lower()

            # Extract punctuation
            match = re.match(r'^([^\w]*)(.+?)([^\w]*)$', word)
            if match:
                prefix, clean_word, suffix = match.groups()
                clean_word = clean_word.lower()

            # Check for correction
            if clean_word in self._correction_map:
                corrected = self._correction_map[clean_word]
                # Preserve case
                if word.isupper():
                    corrected = corrected.upper()
                elif word[0].isupper():
                    corrected = corrected.capitalize()

                corrections.append((clean_word, corrected))
                corrected_words.append(f"{prefix}{corrected}{suffix}")
            else:
                corrected_words.append(word)

        corrected_query = " ".join(corrected_words)

        # Calculate confidence based on number of corrections
        confidence = 1.0 - (len(corrections) * 0.05) if corrections else 1.0

        return SpellingCorrection(
            original=query,
            corrected=corrected_query,
            confidence=max(0.8, confidence),
            corrections=corrections,
        )


class QueryExpander:
    """
    Query expansion for better retrieval and understanding.

    Adds synonyms, related terms, and generates alternative queries.
    """

    # Synonym dictionary
    SYNONYMS = {
        "order": ["purchase", "transaction", "buy", "bought"],
        "refund": ["money back", "reimbursement", "return money", "credit"],
        "return": ["send back", "exchange", "give back"],
        "cancel": ["stop", "end", "terminate", "abort"],
        "shipping": ["delivery", "shipment", "mail", "courier"],
        "payment": ["charge", "transaction", "billing"],
        "account": ["profile", "membership", "subscription"],
        "help": ["support", "assist", "aid", "help me"],
        "issue": ["problem", "trouble", "difficulty", "concern"],
        "status": ["state", "condition", "progress", "update"],
        "tracking": ["trace", "follow", "locate", "track"],
        "discount": ["coupon", "promo", "code", "offer", "deal"],
        "manager": ["supervisor", "lead", "boss", "escalate"],
    }

    # Intent-related expansions
    INTENT_EXPANSIONS = {
        "refund_request": ["money back", "return policy", "refund policy", "cancel order refund"],
        "order_status": ["where is my order", "order tracking", "delivery status", "order update"],
        "shipping_inquiry": ["delivery time", "shipping cost", "shipping options", "carrier"],
        "technical_support": ["help with", "not working", "error", "bug", "issue"],
        "billing_inquiry": ["charge", "invoice", "payment", "billing", "subscription"],
    }

    def __init__(self) -> None:
        """Initialize query expander."""
        pass

    def expand(self, query: str, intent: Optional[str] = None) -> QueryExpansion:
        """
        Expand query with synonyms and related terms.

        Args:
            query: Original query
            intent: Optional detected intent

        Returns:
            QueryExpansion result
        """
        query_lower = query.lower()
        expanded_terms = []
        synonyms_found = {}

        # Find synonyms
        for word, syns in self.SYNONYMS.items():
            if word in query_lower:
                expanded_terms.extend(syns)
                synonyms_found[word] = syns

        # Add intent-related expansions
        related_queries = []
        if intent and intent in self.INTENT_EXPANSIONS:
            for expansion in self.INTENT_EXPANSIONS[intent]:
                if expansion not in query_lower:
                    related_queries.append(f"{query} {expansion}")

        return QueryExpansion(
            original_query=query,
            expanded_terms=list(set(expanded_terms)),
            synonyms=synonyms_found,
            related_queries=related_queries[:3],  # Limit to top 3
        )


class IntentClarifier:
    """
    Intent clarification for ambiguous queries.

    Identifies ambiguous intents and generates clarification questions.
    """

    # Ambiguous patterns and their possible intents
    AMBIGUOUS_PATTERNS = {
        r"i want to (cancel|stop)": {
            "intents": ["cancel_order", "cancel_subscription", "cancel_payment"],
            "questions": [
                "Are you looking to cancel an order, subscription, or payment?",
                "What would you like to cancel?",
            ],
        },
        r"(issue|problem|trouble) with": {
            "intents": ["technical_support", "billing_issue", "order_issue"],
            "questions": [
                "Is this about a technical issue, billing, or your order?",
                "Can you tell me more about the problem?",
            ],
        },
        r"(change|update|modify)": {
            "intents": ["change_address", "update_payment", "modify_order"],
            "questions": [
                "What would you like to change?",
                "Are you updating an address, payment method, or order?",
            ],
        },
        r"need (help|support)": {
            "intents": ["general_inquiry", "technical_support", "account_help"],
            "questions": [
                "What can I help you with today?",
                "Is this about your order, account, or something else?",
            ],
        },
    }

    # Intent hierarchy for fallback
    INTENT_HIERARCHY = {
        "cancel_order": "cancellation",
        "cancel_subscription": "cancellation",
        "cancel_payment": "cancellation",
        "refund_request": "refund",
        "partial_refund": "refund",
        "order_status": "order_inquiry",
        "tracking_inquiry": "order_inquiry",
    }

    def __init__(self) -> None:
        """Initialize intent clarifier."""
        pass

    def clarify(
        self,
        query: str,
        detected_intent: str,
        confidence: float,
    ) -> IntentClarification:
        """
        Clarify ambiguous intent.

        Args:
            query: Original query
            detected_intent: Detected intent
            confidence: Confidence score

        Returns:
            IntentClarification result
        """
        clarification_questions = []
        alternative_intents = []

        # Check for ambiguous patterns
        for pattern, info in self.AMBIGUOUS_PATTERNS.items():
            if re.search(pattern, query, re.IGNORECASE):
                alternative_intents = [
                    (intent, confidence * 0.8)
                    for intent in info["intents"]
                    if intent != detected_intent
                ]
                clarification_questions = info["questions"]
                break

        # Determine clarified intent
        clarified_intent = detected_intent
        if confidence < 0.7 and alternative_intents:
            # Use hierarchy for fallback
            for alt_intent, alt_conf in alternative_intents:
                if alt_conf > confidence:
                    clarified_intent = alt_intent
                    break

        return IntentClarification(
            original_intent=detected_intent,
            clarified_intent=clarified_intent,
            confidence=confidence,
            alternative_intents=alternative_intents,
            clarification_questions=clarification_questions,
        )


class EntityNormalizer:
    """
    Entity normalization for consistent entity handling.

    Normalizes entity formats and types across different industries.
    """

    # Entity patterns and normalization rules
    ENTITY_PATTERNS = {
        "order_id": {
            "patterns": [r"#?(\d{5,})", r"ORD[-_]?(\d+)", r"order\s*#?\s*(\d+)"],
            "format": "ORD-{id}",
            "extract_group": 1,
        },
        "tracking_number": {
            "patterns": [r"([A-Z]{2}\d{9}[A-Z]{2})", r"TRK[-_]?(\d+)", r"tracking\s*#?\s*([A-Z0-9]+)"],
            "format": "{id}",
            "extract_group": 1,
        },
        "phone": {
            "patterns": [r"\(?(\d{3})\)?[-.\s]?(\d{3})[-.\s]?(\d{4})"],
            "format": "{area}-{prefix}-{line}",
            "extract_group": None,  # Special handling
        },
        "email": {
            "patterns": [r"([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})"],
            "format": "{email}",
            "extract_group": 1,
        },
        "amount": {
            "patterns": [r"\$?(\d+(?:\.\d{2})?)", r"(\d+(?:,\d{3})*(?:\.\d{2})?)\s*(?:dollars?|USD)"],
            "format": "{amount}",
            "extract_group": 1,
        },
        "date": {
            "patterns": [
                r"(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})",
                r"(\d{4}[/\-]\d{1,2}[/\-]\d{1,2})",
            ],
            "format": "{date}",
            "extract_group": 1,
        },
    }

    # Entity type mappings
    ENTITY_TYPES = {
        "order_id": "identifier",
        "tracking_number": "identifier",
        "phone": "contact",
        "email": "contact",
        "amount": "monetary",
        "date": "temporal",
    }

    def __init__(self) -> None:
        """Initialize entity normalizer."""
        pass

    def normalize(
        self,
        query: str,
        extracted_entities: Optional[Dict[str, Any]] = None,
    ) -> EntityNormalization:
        """
        Normalize entities in query.

        Args:
            query: Original query
            extracted_entities: Pre-extracted entities

        Returns:
            EntityNormalization result
        """
        original_entities = extracted_entities or {}
        normalized_entities = {}
        entity_types = {}

        # Extract and normalize entities from query
        for entity_type, config in self.ENTITY_PATTERNS.items():
            for pattern in config["patterns"]:
                matches = re.findall(pattern, query, re.IGNORECASE)
                if matches:
                    match = matches[0]  # Take first match

                    # Handle special formatting
                    if entity_type == "phone" and isinstance(match, tuple):
                        normalized = f"{match[0]}-{match[1]}-{match[2]}"
                    elif config["extract_group"] and isinstance(match, tuple):
                        normalized = match[config["extract_group"] - 1] if len(match) >= config["extract_group"] else match[0]
                    else:
                        normalized = str(match) if not isinstance(match, tuple) else match[0]

                    # Apply format
                    if config["format"]:
                        normalized = config["format"].format(
                            id=normalized,
                            area=normalized[:3] if len(normalized) >= 3 else normalized,
                            prefix=normalized[3:6] if len(normalized) >= 6 else "",
                            line=normalized[6:] if len(normalized) > 6 else "",
                            email=normalized,
                            amount=normalized,
                            date=normalized,
                        )

                    normalized_entities[entity_type] = normalized
                    entity_types[entity_type] = self.ENTITY_TYPES.get(entity_type, "unknown")
                    break  # Move to next entity type

        # Include any pre-extracted entities
        for key, value in original_entities.items():
            if key not in normalized_entities:
                normalized_entities[key] = value

        confidence = 0.95 if normalized_entities else 0.5

        return EntityNormalization(
            original_entities=original_entities,
            normalized_entities=normalized_entities,
            entity_types=entity_types,
            confidence=confidence,
        )


class QueryRewriter:
    """
    Query rewriting for improved understanding.

    Rewrites queries to be clearer and more actionable.
    """

    # Rewrite rules
    REWRITE_RULES = [
        # Vague to specific
        {
            "pattern": r"^it'?s?\s+(not working|broken|wrong)$",
            "rewrite": "I am experiencing an issue: {issue}. Please help.",
            "type": "clarification",
        },
        {
            "pattern": r"^i want (a |my )?refund$",
            "rewrite": "I would like to request a refund for my order. Please help me process this.",
            "type": "expansion",
        },
        {
            "pattern": r"^(hi|hello|hey).*$",
            "rewrite": "Hello! I need help with: {original}.",
            "type": "context_addition",
        },
        # Add context
        {
            "pattern": r"^cancel$",
            "rewrite": "I would like to cancel my order or subscription.",
            "type": "expansion",
        },
        {
            "pattern": r"^status$",
            "rewrite": "I would like to check the status of my order.",
            "type": "expansion",
        },
    ]

    def __init__(self) -> None:
        """Initialize query rewriter."""
        pass

    def rewrite(self, query: str) -> QueryRewrite:
        """
        Rewrite query for clarity.

        Args:
            query: Original query

        Returns:
            QueryRewrite result
        """
        rewritten = query
        improvements = []
        rewrite_type = "none"

        for rule in self.REWRITE_RULES:
            match = re.search(rule["pattern"], query, re.IGNORECASE)
            if match:
                # Apply rewrite
                new_query = rule["rewrite"].format(
                    issue=match.group(1) if match.groups() else "an issue",
                    original=query,
                )
                rewritten = new_query
                improvements.append(f"Applied {rule['type']}")
                rewrite_type = rule["type"]
                break

        return QueryRewrite(
            original_query=query,
            rewritten_query=rewritten,
            rewrite_type=rewrite_type,
            improvements=improvements,
        )


class QueryEnhancer:
    """
    Query Enhancement for Agent Lightning.

    Provides comprehensive query enhancement with:
    - Spelling correction
    - Query expansion
    - Intent clarification
    - Entity normalization
    - Query rewriting

    Target: 94% accuracy improvement through better query understanding.

    Example:
        enhancer = QueryEnhancer()
        enhanced = await enhancer.enhance("I want a refun for ordr 12345")
        print(enhanced.enhanced_query)  # "I want a refund for order ORD-12345"
    """

    def __init__(self) -> None:
        """Initialize query enhancer with all components."""
        self._spelling_corrector = SpellingCorrector()
        self._query_expander = QueryExpander()
        self._intent_clarifier = IntentClarifier()
        self._entity_normalizer = EntityNormalizer()
        self._query_rewriter = QueryRewriter()

        self._enhancement_stats = defaultdict(int)

        logger.info({
            "event": "query_enhancer_initialized",
            "components": ["spelling", "expansion", "clarification", "normalization", "rewriting"],
        })

    async def enhance(
        self,
        query: str,
        detected_intent: Optional[str] = None,
        intent_confidence: float = 0.0,
        entities: Optional[Dict[str, Any]] = None,
        enable_all: bool = True,
    ) -> EnhancedQuery:
        """
        Enhance a query with all available enhancements.

        Args:
            query: Original query
            detected_intent: Optional pre-detected intent
            intent_confidence: Confidence of detected intent
            entities: Pre-extracted entities
            enable_all: Enable all enhancement types

        Returns:
            EnhancedQuery with all enhancements applied
        """
        enhancements_applied = []
        confidence_boost = 0.0

        # 1. Spelling correction
        spelling_result = self._spelling_corrector.correct(query)
        current_query = spelling_result.corrected

        if spelling_result.was_corrected:
            enhancements_applied.append(EnhancementType.SPELLING_CORRECTION)
            confidence_boost += 0.05
            self._enhancement_stats["spelling_corrections"] += 1

        # 2. Entity normalization
        entity_result = self._entity_normalizer.normalize(current_query, entities)
        if entity_result.normalized_entities:
            enhancements_applied.append(EnhancementType.ENTITY_NORMALIZATION)
            confidence_boost += 0.08

            # Replace entities in query with normalized versions
            for entity_type, normalized in entity_result.normalized_entities.items():
                if entity_type == "order_id" and normalized not in current_query:
                    # Add normalized order ID
                    current_query = re.sub(
                        r'order\s*#?\s*\d+',
                        f'order {normalized}',
                        current_query,
                        flags=re.IGNORECASE,
                    )

        # 3. Query expansion (if intent is known)
        expansion_result = None
        if detected_intent:
            expansion_result = self._query_expander.expand(current_query, detected_intent)
            if expansion_result.expanded_terms:
                enhancements_applied.append(EnhancementType.QUERY_EXPANSION)
                confidence_boost += 0.03

        # 4. Intent clarification
        clarification_result = None
        if detected_intent and intent_confidence < 0.85:
            clarification_result = self._intent_clarifier.clarify(
                current_query,
                detected_intent,
                intent_confidence,
            )
            if clarification_result.clarification_questions:
                enhancements_applied.append(EnhancementType.INTENT_CLARIFICATION)
                confidence_boost += 0.04

        # 5. Query rewriting
        rewrite_result = self._query_rewriter.rewrite(current_query)
        if rewrite_result.improvements:
            enhancements_applied.append(EnhancementType.QUERY_REWRITING)
            confidence_boost += 0.02
            current_query = rewrite_result.rewritten_query

        # Log enhancement
        logger.info({
            "event": "query_enhanced",
            "original_length": len(query),
            "enhanced_length": len(current_query),
            "enhancements": [e.value for e in enhancements_applied],
            "confidence_boost": confidence_boost,
        })

        return EnhancedQuery(
            original_query=query,
            enhanced_query=current_query,
            spelling_correction=spelling_result,
            expansion=expansion_result,
            intent_clarification=clarification_result,
            entity_normalization=entity_result,
            rewrite=rewrite_result,
            enhancements_applied=enhancements_applied,
            confidence_boost=min(confidence_boost, 0.15),  # Cap boost
            metadata={
                "processing_time": datetime.now(timezone.utc).isoformat(),
            },
        )

    async def correct_spelling(self, query: str) -> SpellingCorrection:
        """
        Apply only spelling correction.

        Args:
            query: Query to correct

        Returns:
            SpellingCorrection result
        """
        return self._spelling_corrector.correct(query)

    async def expand_query(
        self,
        query: str,
        intent: Optional[str] = None,
    ) -> QueryExpansion:
        """
        Apply only query expansion.

        Args:
            query: Query to expand
            intent: Optional intent for better expansion

        Returns:
            QueryExpansion result
        """
        return self._query_expander.expand(query, intent)

    async def clarify_intent(
        self,
        query: str,
        intent: str,
        confidence: float,
    ) -> IntentClarification:
        """
        Apply only intent clarification.

        Args:
            query: Original query
            intent: Detected intent
            confidence: Intent confidence

        Returns:
            IntentClarification result
        """
        return self._intent_clarifier.clarify(query, intent, confidence)

    async def normalize_entities(
        self,
        query: str,
        entities: Optional[Dict[str, Any]] = None,
    ) -> EntityNormalization:
        """
        Apply only entity normalization.

        Args:
            query: Query with entities
            entities: Pre-extracted entities

        Returns:
            EntityNormalization result
        """
        return self._entity_normalizer.normalize(query, entities)

    async def rewrite_query(self, query: str) -> QueryRewrite:
        """
        Apply only query rewriting.

        Args:
            query: Query to rewrite

        Returns:
            QueryRewrite result
        """
        return self._query_rewriter.rewrite(query)

    def get_stats(self) -> Dict[str, int]:
        """Get enhancement statistics."""
        return dict(self._enhancement_stats)


# Singleton instance
_enhancer_instance: Optional[QueryEnhancer] = None


def get_query_enhancer() -> QueryEnhancer:
    """Get singleton QueryEnhancer instance."""
    global _enhancer_instance
    if _enhancer_instance is None:
        _enhancer_instance = QueryEnhancer()
    return _enhancer_instance


async def enhance_query(
    query: str,
    intent: Optional[str] = None,
    confidence: float = 0.0,
) -> EnhancedQuery:
    """
    Convenience function to enhance a query.

    Args:
        query: Query to enhance
        intent: Optional detected intent
        confidence: Intent confidence

    Returns:
        EnhancedQuery result
    """
    enhancer = get_query_enhancer()
    return await enhancer.enhance(query, intent, confidence)
