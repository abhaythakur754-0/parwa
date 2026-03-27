"""
Entity Extractor for Smart Router
Named entity recognition, custom patterns, and entity linking
"""

from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import re
import logging

logger = logging.getLogger(__name__)


class EntityType(Enum):
    """Entity types"""
    ORDER_ID = "order_id"
    PRODUCT_ID = "product_id"
    AMOUNT = "amount"
    EMAIL = "email"
    PHONE = "phone"
    DATE = "date"
    TRACKING_NUMBER = "tracking_number"
    SKU = "sku"
    CUSTOMER_ID = "customer_id"
    PROMO_CODE = "promo_code"
    URL = "url"
    ADDRESS = "address"


@dataclass
class Entity:
    """Extracted entity"""
    type: EntityType
    value: str
    normalized_value: Any
    confidence: float
    start_pos: int
    end_pos: int
    metadata: Dict[str, Any] = field(default_factory=dict)


class EntityExtractor:
    """
    Entity extractor with pattern matching and normalization.
    Supports custom patterns and knowledge base linking.
    """
    
    # Entity patterns
    PATTERNS = {
        EntityType.ORDER_ID: [
            r'\b[A-Za-z]{2,3}[-]?\d{3,8}\b',  # ABC-123 or ABC12345 (3-8 digits)
            r'\b\d{6,12}\b',  # 6-12 digit order ID
            r'\border\s+(?:#|:)?\s*([A-Za-z0-9-]+)\b',  # order followed by ID (requires space)
        ],
        EntityType.TRACKING_NUMBER: [
            r'\b[A-Z]{2}\d{9}[A-Z]{2}\b',  # International format
            r'\b\d{15,22}\b',  # USPS, UPS, FedEx
            r'1Z[A-Z0-9]{16}',  # UPS format
        ],
        EntityType.AMOUNT: [
            r'\$[\d,]+\.?\d*',  # $1,234.56
            r'\d+(?:\.\d{2})?\s*(?:dollars?|USD|EUR|€|£)',  # 100 dollars
            r'(?:USD|EUR|GBP)\s*[\d,]+\.?\d*',  # USD 100.00
        ],
        EntityType.EMAIL: [
            r'[\w\.-]+@[\w\.-]+\.\w+',
        ],
        EntityType.PHONE: [
            r'\+?1?[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}',  # US format
            r'\+?\d{10,15}',  # International
        ],
        EntityType.PRODUCT_ID: [
            r'product[\s#:-]*([A-Z0-9-]+)',
            r'item[\s#:-]*([A-Z0-9-]+)',
            r'SKU[\s#:-]*([A-Z0-9-]+)',
        ],
        EntityType.SKU: [
            r'\b[A-Z]{2,4}\d{4,8}[A-Z]?\b',  # SKU format
        ],
        EntityType.DATE: [
            r'\d{1,2}[-/]\d{1,2}[-/]\d{2,4}',  # MM/DD/YYYY
            r'\d{4}[-/]\d{1,2}[-/]\d{1,2}',  # YYYY-MM-DD
            r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4}',
        ],
        EntityType.PROMO_CODE: [
            r'promo[\s]*(code)?[\s:#-]*([A-Z0-9]{4,10})',
            r'discount[\s]*(code)?[\s:#-]*([A-Z0-9]{4,10})',
            r'\b[A-Z]{2,4}\d{2,6}\b',  # Generic promo format
        ],
        EntityType.CUSTOMER_ID: [
            r'customer[\s#:-]*([A-Z0-9-]+)',
            r'account[\s#:-]*([A-Z0-9-]+)',
        ],
        EntityType.URL: [
            r'https?://[^\s]+',
            r'www\.[^\s]+\.[a-z]{2,3}',
        ],
    }
    
    # Confidence thresholds
    HIGH_CONFIDENCE = 0.9
    MEDIUM_CONFIDENCE = 0.7
    LOW_CONFIDENCE = 0.5
    
    def __init__(self, knowledge_base: Optional[Any] = None):
        self.knowledge_base = knowledge_base
        self._entity_cache: Dict[str, List[Entity]] = {}
        self._initialized = True
    
    def extract(self, text: str) -> List[Entity]:
        """
        Extract all entities from text.
        
        Args:
            text: Input text to extract entities from
            
        Returns:
            List of extracted entities
        """
        # Check cache
        if text in self._entity_cache:
            return self._entity_cache[text]
        
        entities = []
        
        for entity_type, patterns in self.PATTERNS.items():
            type_entities = self._extract_entities_by_type(text, entity_type, patterns)
            entities.extend(type_entities)
        
        # Sort by position
        entities.sort(key=lambda e: e.start_pos)
        
        # Cache result
        self._entity_cache[text] = entities
        
        return entities
    
    def _extract_entities_by_type(
        self, 
        text: str, 
        entity_type: EntityType, 
        patterns: List[str]
    ) -> List[Entity]:
        """Extract entities of a specific type."""
        entities = []
        
        for pattern in patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                # Use capturing group if present, otherwise use full match
                if match.lastindex:
                    value = match.group(1)
                else:
                    value = match.group(0)
                
                if not value:
                    continue
                
                # Normalize value
                normalized = self._normalize_entity(entity_type, value)
                
                # Calculate confidence
                confidence = self._calculate_confidence(entity_type, value, match)
                
                # Cross-reference with knowledge base if available
                kb_match = self._link_to_knowledge_base(entity_type, normalized)
                
                entity = Entity(
                    type=entity_type,
                    value=value,
                    normalized_value=normalized,
                    confidence=confidence,
                    start_pos=match.start(),
                    end_pos=match.end(),
                    metadata={'kb_match': kb_match} if kb_match else {}
                )
                
                # Avoid duplicates
                if not self._is_duplicate(entity, entities):
                    entities.append(entity)
        
        return entities
    
    def _normalize_entity(self, entity_type: EntityType, value: str) -> Any:
        """Normalize entity value."""
        if entity_type == EntityType.AMOUNT:
            # Extract numeric value
            match = re.search(r'[\d,]+\.?\d*', value)
            if match:
                return float(match.group().replace(',', ''))
            return 0.0
        
        elif entity_type == EntityType.ORDER_ID:
            # Standardize format
            return value.upper().replace(' ', '-')
        
        elif entity_type == EntityType.PHONE:
            # Keep only digits
            digits = re.sub(r'[^\d]', '', value)
            return digits[-10:] if len(digits) > 10 else digits
        
        elif entity_type == EntityType.EMAIL:
            return value.lower()
        
        elif entity_type == EntityType.DATE:
            # Parse date (simplified)
            return value  # Could parse to datetime
        
        return value
    
    def _calculate_confidence(
        self, 
        entity_type: EntityType, 
        value: str, 
        match: re.Match
    ) -> float:
        """Calculate confidence for extracted entity."""
        confidence = self.MEDIUM_CONFIDENCE
        
        # Higher confidence for exact pattern matches
        if match.group(0) == value:
            confidence += 0.1
        
        # Check value validity
        if entity_type == EntityType.EMAIL:
            if '@' in value and '.' in value.split('@')[-1]:
                confidence = self.HIGH_CONFIDENCE
        
        elif entity_type == EntityType.ORDER_ID:
            if re.match(r'^[A-Z]{2,3}-\d{4,8}$', value.upper()):
                confidence = self.HIGH_CONFIDENCE
        
        elif entity_type == EntityType.AMOUNT:
            normalized = self._normalize_entity(entity_type, value)
            if normalized > 0:
                confidence = self.HIGH_CONFIDENCE
        
        elif entity_type == EntityType.TRACKING_NUMBER:
            if len(value) >= 15:
                confidence = self.HIGH_CONFIDENCE
        
        return min(1.0, confidence)
    
    def _link_to_knowledge_base(
        self, 
        entity_type: EntityType, 
        normalized: Any
    ) -> Optional[Dict[str, Any]]:
        """Link entity to knowledge base."""
        if not self.knowledge_base:
            return None
        
        # Placeholder for knowledge base linking
        # In production, this would query the KB
        return None
    
    def _is_duplicate(self, new_entity: Entity, existing: List[Entity]) -> bool:
        """Check if entity is duplicate."""
        for entity in existing:
            if (entity.type == new_entity.type and 
                entity.start_pos == new_entity.start_pos):
                return True
        return False
    
    def extract_by_type(
        self, 
        text: str, 
        entity_type: EntityType
    ) -> List[Entity]:
        """
        Extract entities of a specific type.
        
        Args:
            text: Input text
            entity_type: Type of entity to extract
            
        Returns:
            List of entities of specified type
        """
        all_entities = self.extract(text)
        return [e for e in all_entities if e.type == entity_type]
    
    def get_order_ids(self, text: str) -> List[str]:
        """Extract all order IDs from text."""
        entities = self.extract_by_type(text, EntityType.ORDER_ID)
        return [e.normalized_value for e in entities]
    
    def get_amounts(self, text: str) -> List[float]:
        """Extract all monetary amounts from text."""
        entities = self.extract_by_type(text, EntityType.AMOUNT)
        return [e.normalized_value for e in entities]
    
    def get_emails(self, text: str) -> List[str]:
        """Extract all email addresses from text."""
        entities = self.extract_by_type(text, EntityType.EMAIL)
        return [e.normalized_value for e in entities]
    
    def get_phones(self, text: str) -> List[str]:
        """Extract all phone numbers from text."""
        entities = self.extract_by_type(text, EntityType.PHONE)
        return [e.normalized_value for e in entities]
    
    def validate_entity(
        self, 
        entity_type: EntityType, 
        value: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate an entity value.
        
        Args:
            entity_type: Type of entity
            value: Value to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        patterns = self.PATTERNS.get(entity_type, [])
        
        for pattern in patterns:
            if re.match(pattern, value, re.IGNORECASE):
                return True, None
        
        return False, f"Invalid {entity_type.value} format"
    
    def add_custom_pattern(
        self, 
        entity_type: EntityType, 
        pattern: str
    ) -> None:
        """Add a custom pattern for entity extraction."""
        if entity_type not in self.PATTERNS:
            self.PATTERNS[entity_type] = []
        self.PATTERNS[entity_type].append(pattern)
    
    def is_initialized(self) -> bool:
        """Check if extractor is initialized."""
        return self._initialized
    
    def get_stats(self) -> Dict[str, Any]:
        """Get extractor statistics."""
        return {
            'cache_size': len(self._entity_cache),
            'entity_types': len(self.PATTERNS),
            'total_patterns': sum(len(p) for p in self.PATTERNS.values()),
        }
