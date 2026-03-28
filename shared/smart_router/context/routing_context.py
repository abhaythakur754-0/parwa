"""
Routing Context for Smart Router
Context-aware routing decisions and historical patterns
"""

from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, time
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class TimeSegment(Enum):
    """Time segments for routing"""
    EARLY_MORNING = "early_morning"  # 6-9
    MORNING = "morning"              # 9-12
    AFTERNOON = "afternoon"          # 12-17
    EVENING = "evening"              # 17-21
    NIGHT = "night"                  # 21-6


class RoutingPriority(Enum):
    """Routing priority levels"""
    STANDARD = "standard"
    ELEVATED = "elevated"
    PRIORITY = "priority"
    CRITICAL = "critical"


@dataclass
class RoutingDecision:
    """Routing decision with context"""
    selected_tier: str
    selected_model: str
    confidence: float
    context_factors: Dict[str, Any]
    alternative_routes: List[Tuple[str, float]]
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class ClientContext:
    """Client-specific routing context"""
    client_id: str
    tier: str  # basic, pro, enterprise
    sla_level: str  # standard, premium, platinum
    preferred_models: List[str]
    budget_remaining: Optional[float]
    custom_routing_rules: Dict[str, Any]


class RoutingContext:
    """
    Context-aware routing decision engine.
    Uses conversation context and historical patterns.
    """
    
    # Time-based routing rules
    TIME_ROUTING = {
        TimeSegment.EARLY_MORNING: {
            'preferred_tier': 'medium',
            'availability_factor': 0.8,
        },
        TimeSegment.MORNING: {
            'preferred_tier': 'heavy',
            'availability_factor': 1.0,
        },
        TimeSegment.AFTERNOON: {
            'preferred_tier': 'heavy',
            'availability_factor': 1.0,
        },
        TimeSegment.EVENING: {
            'preferred_tier': 'medium',
            'availability_factor': 0.9,
        },
        TimeSegment.NIGHT: {
            'preferred_tier': 'light',
            'availability_factor': 0.6,
        },
    }
    
    # Priority routing rules
    PRIORITY_ROUTING = {
        RoutingPriority.STANDARD: {'tier': 'light', 'model': 'mini'},
        RoutingPriority.ELEVATED: {'tier': 'medium', 'model': 'junior'},
        RoutingPriority.PRIORITY: {'tier': 'heavy', 'model': 'junior'},
        RoutingPriority.CRITICAL: {'tier': 'heavy', 'model': 'high'},
    }
    
    # Client tier benefits
    CLIENT_TIER_ROUTING = {
        'enterprise': {
            'priority_boost': 1,
            'max_tier': 'heavy',
            'fallback_enabled': True,
        },
        'pro': {
            'priority_boost': 0,
            'max_tier': 'medium',
            'fallback_enabled': True,
        },
        'basic': {
            'priority_boost': -1,
            'max_tier': 'light',
            'fallback_enabled': False,
        },
    }
    
    def __init__(self):
        self._routing_history: Dict[str, List[RoutingDecision]] = {}
        self._client_contexts: Dict[str, ClientContext] = {}
        self._pattern_cache: Dict[str, Dict[str, Any]] = {}
        self._initialized = True
    
    def register_client(
        self,
        client_id: str,
        tier: str = 'basic',
        sla_level: str = 'standard',
        preferred_models: Optional[List[str]] = None,
        budget_remaining: Optional[float] = None,
        custom_rules: Optional[Dict[str, Any]] = None
    ) -> ClientContext:
        """
        Register client context.
        
        Args:
            client_id: Client identifier
            tier: Client tier (basic, pro, enterprise)
            sla_level: SLA level
            preferred_models: Preferred model list
            budget_remaining: Remaining budget
            custom_rules: Custom routing rules
            
        Returns:
            ClientContext
        """
        context = ClientContext(
            client_id=client_id,
            tier=tier,
            sla_level=sla_level,
            preferred_models=preferred_models or [],
            budget_remaining=budget_remaining,
            custom_routing_rules=custom_rules or {}
        )
        
        self._client_contexts[client_id] = context
        logger.info(f"Registered client {client_id} with tier {tier}")
        
        return context
    
    def get_routing_decision(
        self,
        session_id: str,
        client_id: str,
        user_id: Optional[str],
        conversation_context: Dict[str, Any],
        user_profile: Optional[Dict[str, Any]] = None
    ) -> RoutingDecision:
        """
        Make context-aware routing decision.
        
        Args:
            session_id: Session identifier
            client_id: Client identifier
            user_id: Optional user identifier
            conversation_context: Current conversation context
            user_profile: Optional user profile data
            
        Returns:
            RoutingDecision
        """
        # Get client context
        client_ctx = self._client_contexts.get(client_id)
        
        # Determine time segment
        time_segment = self._get_time_segment()
        
        # Calculate priority
        priority = self._calculate_priority(
            conversation_context,
            client_ctx,
            user_profile
        )
        
        # Get historical pattern
        historical = self._get_historical_pattern(user_id)
        
        # Make decision
        decision = self._make_decision(
            session_id,
            client_ctx,
            time_segment,
            priority,
            historical,
            conversation_context
        )
        
        # Store in history
        if session_id not in self._routing_history:
            self._routing_history[session_id] = []
        self._routing_history[session_id].append(decision)
        
        return decision
    
    def _get_time_segment(self) -> TimeSegment:
        """Get current time segment."""
        hour = datetime.now().hour
        
        if 6 <= hour < 9:
            return TimeSegment.EARLY_MORNING
        elif 9 <= hour < 12:
            return TimeSegment.MORNING
        elif 12 <= hour < 17:
            return TimeSegment.AFTERNOON
        elif 17 <= hour < 21:
            return TimeSegment.EVENING
        else:
            return TimeSegment.NIGHT
    
    def _calculate_priority(
        self,
        context: Dict[str, Any],
        client_ctx: Optional[ClientContext],
        user_profile: Optional[Dict[str, Any]]
    ) -> RoutingPriority:
        """Calculate routing priority."""
        base_priority = RoutingPriority.STANDARD
        
        # Check for escalation flag
        if context.get('escalation_flag'):
            return RoutingPriority.CRITICAL
        
        # Check sentiment (negative = higher priority)
        sentiment = context.get('sentiment', 0)
        if sentiment < -0.5:
            base_priority = RoutingPriority.PRIORITY
        elif sentiment < -0.2:
            base_priority = RoutingPriority.ELEVATED
        
        # Check urgency in intent
        intent = context.get('user_intent', '')
        if intent in ['report_issue', 'contact_support', 'escalate']:
            if base_priority.value < RoutingPriority.PRIORITY.value:
                base_priority = RoutingPriority.PRIORITY
        
        # Apply client tier boost
        if client_ctx:
            tier_config = self.CLIENT_TIER_ROUTING.get(client_ctx.tier, {})
            boost = tier_config.get('priority_boost', 0)
            
            if boost > 0 and base_priority.value < RoutingPriority.PRIORITY.value:
                # Upgrade priority
                priorities = list(RoutingPriority)
                current_idx = priorities.index(base_priority)
                new_idx = min(current_idx + boost, len(priorities) - 1)
                base_priority = priorities[new_idx]
        
        return base_priority
    
    def _get_historical_pattern(
        self,
        user_id: Optional[str]
    ) -> Dict[str, Any]:
        """Get historical routing patterns for user."""
        if not user_id:
            return {}
        
        return self._pattern_cache.get(user_id, {})
    
    def _make_decision(
        self,
        session_id: str,
        client_ctx: Optional[ClientContext],
        time_segment: TimeSegment,
        priority: RoutingPriority,
        historical: Dict[str, Any],
        context: Dict[str, Any]
    ) -> RoutingDecision:
        """Make the routing decision."""
        
        # Start with priority-based routing
        priority_config = self.PRIORITY_ROUTING[priority]
        tier = priority_config['tier']
        model = priority_config['model']
        
        # Adjust for time
        time_config = self.TIME_ROUTING[time_segment]
        availability = time_config['availability_factor']
        
        # If availability is low, may need to adjust
        if availability < 0.7 and tier == 'heavy':
            # Check if we can downgrade
            if priority != RoutingPriority.CRITICAL:
                tier = 'medium'
                model = 'junior'
        
        # Apply client constraints
        if client_ctx:
            tier_config = self.CLIENT_TIER_ROUTING.get(client_ctx.tier, {})
            max_tier = tier_config.get('max_tier', 'heavy')
            
            # Enforce max tier
            tier_order = ['light', 'medium', 'heavy']
            if tier_order.index(tier) > tier_order.index(max_tier):
                tier = max_tier
                model = 'mini' if max_tier == 'light' else 'junior'
            
            # Check preferred models
            if client_ctx.preferred_models and model not in client_ctx.preferred_models:
                if client_ctx.preferred_models:
                    model = client_ctx.preferred_models[0]
            
            # Apply custom rules
            custom = client_ctx.custom_routing_rules
            if custom.get('always_use_heavy'):
                tier = 'heavy'
                model = 'high'
        
        # Check historical preferences
        if historical.get('preferred_tier'):
            # Use historical preference if not critical
            if priority != RoutingPriority.CRITICAL:
                tier = historical['preferred_tier']
        
        # Calculate confidence
        confidence = self._calculate_confidence(
            tier, model, priority, context
        )
        
        # Get alternatives
        alternatives = self._get_alternatives(tier, priority)
        
        return RoutingDecision(
            selected_tier=tier,
            selected_model=model,
            confidence=confidence,
            context_factors={
                'time_segment': time_segment.value,
                'priority': priority.value,
                'client_tier': client_ctx.tier if client_ctx else None,
                'availability_factor': availability,
            },
            alternative_routes=alternatives
        )
    
    def _calculate_confidence(
        self,
        tier: str,
        model: str,
        priority: RoutingPriority,
        context: Dict[str, Any]
    ) -> float:
        """Calculate confidence in routing decision."""
        base_confidence = 0.8
        
        # Adjust based on context richness
        context_factors = len(context)
        base_confidence += min(0.1, context_factors * 0.01)
        
        # Adjust based on priority match
        priority_config = self.PRIORITY_ROUTING[priority]
        if priority_config['tier'] == tier:
            base_confidence += 0.1
        
        return min(1.0, base_confidence)
    
    def _get_alternatives(
        self,
        selected_tier: str,
        priority: RoutingPriority
    ) -> List[Tuple[str, float]]:
        """Get alternative routing options."""
        alternatives = []
        
        tier_order = ['light', 'medium', 'heavy']
        selected_idx = tier_order.index(selected_tier)
        
        # Add adjacent tiers
        if selected_idx > 0:
            alternatives.append((tier_order[selected_idx - 1], 0.7))
        if selected_idx < len(tier_order) - 1:
            alternatives.append((tier_order[selected_idx + 1], 0.6))
        
        return alternatives
    
    def record_outcome(
        self,
        session_id: str,
        decision_id: str,
        successful: bool,
        user_satisfied: Optional[bool] = None
    ) -> None:
        """Record routing outcome for learning."""
        # Would store outcome for ML training
        logger.debug(f"Recorded outcome for {session_id}: {successful}")
    
    def get_client_context(self, client_id: str) -> Optional[ClientContext]:
        """Get client context."""
        return self._client_contexts.get(client_id)
    
    def update_pattern_cache(
        self,
        user_id: str,
        pattern: Dict[str, Any]
    ) -> None:
        """Update pattern cache for user."""
        self._pattern_cache[user_id] = pattern
    
    def is_initialized(self) -> bool:
        """Check if routing context is initialized."""
        return self._initialized
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics."""
        return {
            'total_clients': len(self._client_contexts),
            'total_sessions': len(self._routing_history),
            'pattern_cache_size': len(self._pattern_cache),
        }
