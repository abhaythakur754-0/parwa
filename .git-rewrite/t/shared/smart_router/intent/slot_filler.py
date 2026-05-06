"""
Slot Filler for Smart Router
Required slot identification, value extraction, and validation
"""

from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class SlotStatus(Enum):
    """Slot filling status"""
    EMPTY = "empty"
    FILLED = "filled"
    INVALID = "invalid"
    CONFIRMED = "confirmed"
    PROMPTED = "prompted"


@dataclass
class Slot:
    """Slot definition and state"""
    name: str
    value: Any
    status: SlotStatus
    required: bool = True
    prompt: str = ""
    validation_regex: Optional[str] = None
    source: str = "extracted"  # extracted, provided, inherited, default
    confidence: float = 1.0


@dataclass
class SlotFillingResult:
    """Result of slot filling operation"""
    slots: Dict[str, Slot]
    missing_required: List[str]
    ready_for_action: bool
    confirmation_needed: List[str]


class SlotFiller:
    """
    Slot filler for intent parameter extraction.
    Handles required slot identification and validation.
    """
    
    # Intent slot requirements
    INTENT_SLOTS = {
        'check_order_status': {
            'required': ['order_id'],
            'optional': ['email', 'phone'],
        },
        'request_refund': {
            'required': ['order_id', 'reason'],
            'optional': ['amount'],
        },
        'cancel_order': {
            'required': ['order_id'],
            'optional': ['reason', 'cancellation_fee_acknowledged'],
        },
        'billing_inquiry': {
            'required': ['account_id'],
            'optional': ['invoice_number', 'transaction_id'],
        },
        'report_issue': {
            'required': ['issue_description'],
            'optional': ['order_id', 'product_id', 'screenshot_url'],
        },
        'get_product_info': {
            'required': ['product_id'],
            'optional': ['category'],
        },
        'contact_support': {
            'required': [],
            'optional': ['issue_type', 'urgency', 'preferred_contact_method'],
        },
    }
    
    # Slot prompts
    SLOT_PROMPTS = {
        'order_id': "Could you please provide your order ID? It usually looks like ABC-12345.",
        'email': "What's the email address associated with your account?",
        'phone': "What's your phone number?",
        'reason': "Could you tell me the reason for this request?",
        'amount': "What amount are you referring to?",
        'account_id': "Could you provide your account ID?",
        'invoice_number': "What's the invoice number?",
        'product_id': "What's the product ID or SKU?",
        'issue_description': "Could you describe the issue you're experiencing?",
    }
    
    # Slot validation patterns
    SLOT_VALIDATIONS = {
        'order_id': r'^[A-Z]{2,3}-?\d{4,8}$',
        'email': r'^[\w\.-]+@[\w\.-]+\.\w+$',
        'phone': r'^\+?1?[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}$',
        'amount': r'^[\d,]+\.?\d*$',
    }
    
    def __init__(self):
        self._slot_states: Dict[str, Dict[str, Slot]] = {}
        self._initialized = True
    
    def fill_slots(
        self, 
        intent: str,
        extracted_entities: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> SlotFillingResult:
        """
        Fill slots for an intent from extracted entities.
        
        Args:
            intent: Intent name
            extracted_entities: Dict of entity_type -> value
            context: Optional context for slot inheritance
            
        Returns:
            SlotFillingResult with filled slots and status
        """
        # Get slot requirements for intent
        slot_requirements = self.INTENT_SLOTS.get(intent, {
            'required': [],
            'optional': []
        })
        
        required_slots = slot_requirements['required']
        optional_slots = slot_requirements['optional']
        
        # Initialize slots
        slots: Dict[str, Slot] = {}
        
        # Fill required slots
        for slot_name in required_slots:
            slot = self._fill_slot(
                slot_name, 
                extracted_entities, 
                context,
                required=True
            )
            slots[slot_name] = slot
        
        # Fill optional slots
        for slot_name in optional_slots:
            slot = self._fill_slot(
                slot_name, 
                extracted_entities, 
                context,
                required=False
            )
            slots[slot_name] = slot
        
        # Determine missing required slots
        missing = [
            name for name, slot in slots.items() 
            if slot.required and slot.status in [SlotStatus.EMPTY, SlotStatus.INVALID]
        ]
        
        # Check if ready for action
        ready = len(missing) == 0
        
        # Check for confirmation needs
        confirmation_needed = [
            name for name, slot in slots.items()
            if slot.status == SlotStatus.FILLED and slot.confidence < 0.8
        ]
        
        return SlotFillingResult(
            slots=slots,
            missing_required=missing,
            ready_for_action=ready,
            confirmation_needed=confirmation_needed
        )
    
    def _fill_slot(
        self, 
        slot_name: str,
        extracted_entities: Dict[str, Any],
        context: Optional[Dict[str, Any]],
        required: bool
    ) -> Slot:
        """Fill a single slot from entities or context."""
        
        # Try to get from extracted entities
        entity_mapping = {
            'order_id': 'order_id',
            'email': 'email',
            'phone': 'phone',
            'reason': 'reason',
            'amount': 'amount',
            'product_id': 'product_id',
            'account_id': 'customer_id',
        }
        
        entity_key = entity_mapping.get(slot_name, slot_name)
        value = extracted_entities.get(entity_key)
        source = "extracted"
        
        # Try context if not found
        if value is None and context:
            value = context.get(slot_name) or context.get('slots', {}).get(slot_name)
            if value:
                source = "inherited"
        
        # Get prompt
        prompt = self.SLOT_PROMPTS.get(slot_name, f"Please provide {slot_name}")
        
        # Validate if value exists
        if value is not None:
            is_valid, _ = self.validate_slot(slot_name, value)
            status = SlotStatus.FILLED if is_valid else SlotStatus.INVALID
            confidence = 1.0 if is_valid else 0.5
        else:
            status = SlotStatus.EMPTY
            confidence = 0.0
        
        return Slot(
            name=slot_name,
            value=value,
            status=status,
            required=required,
            prompt=prompt,
            validation_regex=self.SLOT_VALIDATIONS.get(slot_name),
            source=source,
            confidence=confidence
        )
    
    def validate_slot(
        self, 
        slot_name: str, 
        value: Any
    ) -> tuple[bool, Optional[str]]:
        """
        Validate a slot value.
        
        Args:
            slot_name: Name of slot to validate
            value: Value to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        import re
        
        # Check for None or empty
        if value is None or (isinstance(value, str) and not value.strip()):
            return False, "Value is empty"
        
        # Get validation pattern
        pattern = self.SLOT_VALIDATIONS.get(slot_name)
        
        if pattern:
            try:
                if re.match(pattern, str(value), re.IGNORECASE):
                    return True, None
                return False, f"Invalid format for {slot_name}"
            except re.error:
                # Pattern error, accept value
                return True, None
        
        # No validation pattern, accept value
        return True, None
    
    def get_missing_slots_prompt(
        self, 
        missing_slots: List[str]
    ) -> str:
        """
        Generate prompt for missing slots.
        
        Args:
            missing_slots: List of missing slot names
            
        Returns:
            Prompt string for user
        """
        if not missing_slots:
            return ""
        
        if len(missing_slots) == 1:
            return self.SLOT_PROMPTS.get(
                missing_slots[0], 
                f"Please provide {missing_slots[0]}."
            )
        
        # Multiple missing slots
        prompts = [
            self.SLOT_PROMPTS.get(s, f"Please provide {s}")
            for s in missing_slots
        ]
        
        return "I need a bit more information: " + " Also, ".join(prompts)
    
    def confirm_slot(
        self, 
        intent: str, 
        slot_name: str, 
        value: Any
    ) -> Slot:
        """
        Confirm a slot value after user verification.
        
        Args:
            intent: Intent name
            slot_name: Slot name
            value: Confirmed value
            
        Returns:
            Confirmed Slot
        """
        return Slot(
            name=slot_name,
            value=value,
            status=SlotStatus.CONFIRMED,
            required=True,
            confidence=1.0
        )
    
    def update_slot(
        self, 
        session_id: str,
        slot_name: str, 
        value: Any,
        status: SlotStatus = SlotStatus.FILLED
    ) -> None:
        """
        Update slot state in session.
        
        Args:
            session_id: Session identifier
            slot_name: Slot name
            value: New value
            status: New status
        """
        if session_id not in self._slot_states:
            self._slot_states[session_id] = {}
        
        self._slot_states[session_id][slot_name] = Slot(
            name=slot_name,
            value=value,
            status=status,
            required=True
        )
    
    def get_session_slots(
        self, 
        session_id: str
    ) -> Dict[str, Slot]:
        """
        Get all slots for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Dict of slot name to Slot
        """
        return self._slot_states.get(session_id, {})
    
    def clear_session_slots(self, session_id: str) -> None:
        """Clear all slots for a session."""
        self._slot_states.pop(session_id, None)
    
    def get_required_slots(self, intent: str) -> List[str]:
        """Get required slots for an intent."""
        return self.INTENT_SLOTS.get(intent, {}).get('required', [])
    
    def get_optional_slots(self, intent: str) -> List[str]:
        """Get optional slots for an intent."""
        return self.INTENT_SLOTS.get(intent, {}).get('optional', [])
    
    def is_initialized(self) -> bool:
        """Check if filler is initialized."""
        return self._initialized
    
    def get_stats(self) -> Dict[str, Any]:
        """Get filler statistics."""
        return {
            'active_sessions': len(self._slot_states),
            'intent_count': len(self.INTENT_SLOTS),
            'total_slot_definitions': sum(
                len(s.get('required', [])) + len(s.get('optional', []))
                for s in self.INTENT_SLOTS.values()
            ),
        }
