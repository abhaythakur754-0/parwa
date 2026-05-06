"""
Intent Classifier for Smart Router
Predefined intent taxonomy, custom intents, and confidence calibration
"""

from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import logging
import math

logger = logging.getLogger(__name__)


class IntentCategory(Enum):
    """Intent category classification"""
    TRANSACTIONAL = "transactional"
    INFORMATIONAL = "informational"
    SUPPORT = "support"
    FEEDBACK = "feedback"
    SOCIAL = "social"


@dataclass
class IntentDefinition:
    """Intent definition with metadata"""
    name: str
    category: IntentCategory
    description: str
    examples: List[str]
    parent: Optional[str] = None
    confidence_threshold: float = 0.7
    requires_slots: List[str] = field(default_factory=list)


@dataclass
class ClassificationResult:
    """Intent classification result"""
    intent: str
    confidence: float
    category: IntentCategory
    alternative_intents: List[Tuple[str, float]] = field(default_factory=list)
    calibration_score: float = 1.0


class IntentClassifier:
    """
    Intent classifier with predefined taxonomy.
    Supports custom intents and confidence calibration.
    """
    
    # Target accuracy
    TARGET_ACCURACY = 0.93
    
    # Predefined intent taxonomy
    INTENT_TAXONOMY: Dict[str, IntentDefinition] = {
        # Transactional intents
        'place_order': IntentDefinition(
            name='place_order',
            category=IntentCategory.TRANSACTIONAL,
            description='User wants to place a new order',
            examples=[
                'I want to buy this product',
                'Place an order for item ABC',
                'How can I order this?',
            ],
            requires_slots=['product_id', 'quantity']
        ),
        'cancel_order': IntentDefinition(
            name='cancel_order',
            category=IntentCategory.TRANSACTIONAL,
            description='User wants to cancel an order',
            examples=[
                'Cancel my order',
                'I want to stop my order',
                'Don\'t ship my order',
            ],
            requires_slots=['order_id']
        ),
        'request_refund': IntentDefinition(
            name='request_refund',
            category=IntentCategory.TRANSACTIONAL,
            description='User wants a refund',
            examples=[
                'I want my money back',
                'Refund this order',
                'Return this item',
            ],
            requires_slots=['order_id']
        ),
        
        # Informational intents
        'check_order_status': IntentDefinition(
            name='check_order_status',
            category=IntentCategory.INFORMATIONAL,
            description='User wants to check order status',
            examples=[
                'Where is my order?',
                'Track my package',
                'Order status for ABC-123',
            ],
            requires_slots=['order_id']
        ),
        'get_product_info': IntentDefinition(
            name='get_product_info',
            category=IntentCategory.INFORMATIONAL,
            description='User wants product information',
            examples=[
                'Tell me about this product',
                'What are the specs?',
                'Product details please',
            ],
            requires_slots=['product_id']
        ),
        'check_billing': IntentDefinition(
            name='check_billing',
            category=IntentCategory.INFORMATIONAL,
            description='User has billing questions',
            examples=[
                'Check my bill',
                'What did I get charged?',
                'Invoice question',
            ],
            requires_slots=[]
        ),
        
        # Support intents
        'report_issue': IntentDefinition(
            name='report_issue',
            category=IntentCategory.SUPPORT,
            description='User reporting a problem',
            examples=[
                'Something is broken',
                'There\'s an error',
                'Not working properly',
            ],
            requires_slots=['issue_description']
        ),
        'contact_support': IntentDefinition(
            name='contact_support',
            category=IntentCategory.SUPPORT,
            description='User wants to contact support',
            examples=[
                'Let me speak to someone',
                'I need a human',
                'Connect me to agent',
            ],
            requires_slots=[]
        ),
        'escalate': IntentDefinition(
            name='escalate',
            category=IntentCategory.SUPPORT,
            description='User wants to escalate',
            examples=[
                'I want to speak to manager',
                'Escalate this issue',
                'This needs higher attention',
            ],
            requires_slots=[]
        ),
        
        # Feedback intents
        'provide_feedback': IntentDefinition(
            name='provide_feedback',
            category=IntentCategory.FEEDBACK,
            description='User providing feedback',
            examples=[
                'I want to give feedback',
                'Here\'s my suggestion',
                'I have a complaint',
            ],
            requires_slots=[]
        ),
        'rate_service': IntentDefinition(
            name='rate_service',
            category=IntentCategory.FEEDBACK,
            description='User rating the service',
            examples=[
                'Rate my experience',
                'I give this 5 stars',
                'Poor service experience',
            ],
            requires_slots=[]
        ),
        
        # Social intents
        'greeting': IntentDefinition(
            name='greeting',
            category=IntentCategory.SOCIAL,
            description='User greeting',
            examples=[
                'Hello',
                'Hi there',
                'Good morning',
            ],
            requires_slots=[]
        ),
        'thanks': IntentDefinition(
            name='thanks',
            category=IntentCategory.SOCIAL,
            description='User expressing gratitude',
            examples=[
                'Thank you',
                'Thanks for help',
                'Appreciate it',
            ],
            requires_slots=[]
        ),
        'goodbye': IntentDefinition(
            name='goodbye',
            category=IntentCategory.SOCIAL,
            description='User saying goodbye',
            examples=[
                'Goodbye',
                'Bye',
                'See you later',
            ],
            requires_slots=[]
        ),
    }
    
    # Intent embedding patterns (simplified - production would use actual embeddings)
    INTENT_KEYWORDS = {
        'place_order': ['buy', 'purchase', 'order', 'get this'],
        'cancel_order': ['cancel', 'stop', 'don\'t want', 'remove'],
        'request_refund': ['refund', 'money back', 'return', 'reimburse'],
        'check_order_status': ['where', 'track', 'status', 'location', 'when'],
        'get_product_info': ['product', 'details', 'specs', 'information', 'about'],
        'check_billing': ['bill', 'charge', 'invoice', 'payment', 'charged'],
        'report_issue': ['issue', 'problem', 'error', 'broken', 'bug', 'not working'],
        'contact_support': ['agent', 'human', 'person', 'representative', 'support'],
        'escalate': ['manager', 'supervisor', 'escalate', 'higher'],
        'provide_feedback': ['feedback', 'suggestion', 'complaint', 'opinion'],
        'rate_service': ['rate', 'stars', 'rating', 'experience'],
        'greeting': ['hello', 'hi', 'hey', 'good morning', 'good afternoon'],
        'thanks': ['thank', 'thanks', 'appreciate', 'helpful'],
        'goodbye': ['bye', 'goodbye', 'see you', 'later'],
    }
    
    def __init__(self):
        self._custom_intents: Dict[str, IntentDefinition] = {}
        self._classification_history: List[Tuple[str, str, bool]] = []
        self._confidence_calibration: Dict[str, float] = {}
        self._initialized = True
    
    def classify(
        self, 
        query: str,
        candidates: Optional[List[str]] = None
    ) -> ClassificationResult:
        """
        Classify query into an intent.
        
        Args:
            query: User query text
            candidates: Optional list of candidate intents to consider
            
        Returns:
            ClassificationResult with intent and confidence
        """
        query_lower = query.lower()
        
        # Get intents to consider
        if candidates:
            intents_to_check = {
                k: v for k, v in self._get_all_intents().items()
                if k in candidates
            }
        else:
            intents_to_check = self._get_all_intents()
        
        # Score each intent
        scores: List[Tuple[str, float]] = []
        
        for intent_name, definition in intents_to_check.items():
            score = self._calculate_intent_score(query_lower, intent_name)
            if score > 0:
                # Apply calibration
                calibration = self._confidence_calibration.get(intent_name, 1.0)
                adjusted_score = score * calibration
                scores.append((intent_name, adjusted_score))
        
        # Sort by score
        scores.sort(key=lambda x: x[1], reverse=True)
        
        if not scores:
            # Default to unknown
            return ClassificationResult(
                intent='unknown',
                confidence=0.3,
                category=IntentCategory.SUPPORT,
                calibration_score=1.0
            )
        
        # Get top intent
        top_intent, top_score = scores[0]
        definition = intents_to_check.get(top_intent)
        
        # Normalize confidence to 0-1
        confidence = min(1.0, top_score / 3.0)  # Max score is ~3
        
        return ClassificationResult(
            intent=top_intent,
            confidence=confidence,
            category=definition.category if definition else IntentCategory.SUPPORT,
            alternative_intents=scores[1:4],
            calibration_score=self._confidence_calibration.get(top_intent, 1.0)
        )
    
    def _calculate_intent_score(self, query_lower: str, intent_name: str) -> float:
        """Calculate score for an intent given query."""
        keywords = self.INTENT_KEYWORDS.get(intent_name, [])
        definition = self._get_all_intents().get(intent_name)
        
        score = 0.0
        
        # Keyword matching
        for keyword in keywords:
            if keyword in query_lower:
                score += 1.0
        
        # Example matching
        if definition:
            for example in definition.examples:
                example_lower = example.lower()
                # Check word overlap
                query_words = set(query_lower.split())
                example_words = set(example_lower.split())
                overlap = len(query_words & example_words)
                score += overlap * 0.3
        
        return score
    
    def _get_all_intents(self) -> Dict[str, IntentDefinition]:
        """Get all intents including custom ones."""
        all_intents = dict(self.INTENT_TAXONOMY)
        all_intents.update(self._custom_intents)
        return all_intents
    
    def add_custom_intent(
        self, 
        name: str, 
        category: IntentCategory,
        description: str,
        examples: List[str],
        keywords: Optional[List[str]] = None
    ) -> IntentDefinition:
        """
        Add a custom intent.
        
        Args:
            name: Intent name
            category: Intent category
            description: Intent description
            examples: Example queries
            keywords: Keywords for matching
            
        Returns:
            Created IntentDefinition
        """
        definition = IntentDefinition(
            name=name,
            category=category,
            description=description,
            examples=examples
        )
        
        self._custom_intents[name] = definition
        
        # Add keywords for matching
        if keywords:
            self.INTENT_KEYWORDS[name] = keywords
        else:
            # Extract keywords from examples
            self.INTENT_KEYWORDS[name] = list(set(
                word.lower() 
                for ex in examples 
                for word in ex.split()
                if len(word) > 3
            ))
        
        logger.info(f"Added custom intent: {name}")
        return definition
    
    def learn_from_feedback(
        self, 
        query: str, 
        correct_intent: str
    ) -> None:
        """
        Learn from classification feedback (few-shot learning).
        
        Args:
            query: Query that was classified
            correct_intent: Correct intent label
        """
        definition = self._get_all_intents().get(correct_intent)
        if definition:
            # Add to examples
            if query not in definition.examples:
                definition.examples.append(query)
            
            # Update keywords
            keywords = self.INTENT_KEYWORDS.get(correct_intent, [])
            for word in query.lower().split():
                if len(word) > 3 and word not in keywords:
                    keywords.append(word)
            self.INTENT_KEYWORDS[correct_intent] = keywords
        
        logger.info(f"Learned from feedback: {correct_intent}")
    
    def calibrate_confidence(
        self, 
        intent: str, 
        predicted_confidence: float,
        was_correct: bool
    ) -> None:
        """
        Calibrate confidence scoring based on outcomes.
        
        Args:
            intent: Intent that was predicted
            predicted_confidence: Confidence that was predicted
            was_correct: Whether classification was correct
        """
        current_calibration = self._confidence_calibration.get(intent, 1.0)
        
        if was_correct:
            # Increase confidence for this intent
            adjustment = (predicted_confidence - current_calibration) * 0.1
            new_calibration = current_calibration + adjustment
        else:
            # Decrease confidence
            adjustment = 0.1
            new_calibration = current_calibration - adjustment
        
        # Keep in reasonable bounds
        self._confidence_calibration[intent] = max(0.5, min(1.5, new_calibration))
    
    def get_intent_clusters(self) -> Dict[str, List[str]]:
        """
        Get clusters of similar intents.
        
        Returns:
            Dict mapping cluster name to list of intents
        """
        clusters = {
            'transactional': [],
            'informational': [],
            'support': [],
            'feedback': [],
            'social': [],
        }
        
        for intent_name, definition in self._get_all_intents().items():
            cluster_name = definition.category.value
            if cluster_name in clusters:
                clusters[cluster_name].append(intent_name)
        
        return clusters
    
    def get_taxonomy(self) -> Dict[str, Any]:
        """Get full intent taxonomy."""
        return {
            name: {
                'category': defn.category.value,
                'description': defn.description,
                'example_count': len(defn.examples),
                'requires_slots': defn.requires_slots,
            }
            for name, defn in self._get_all_intents().items()
        }
    
    def is_initialized(self) -> bool:
        """Check if classifier is initialized."""
        return self._initialized
    
    def get_stats(self) -> Dict[str, Any]:
        """Get classifier statistics."""
        return {
            'predefined_intents': len(self.INTENT_TAXONOMY),
            'custom_intents': len(self._custom_intents),
            'calibrated_intents': len(self._confidence_calibration),
            'total_classification_history': len(self._classification_history),
        }
