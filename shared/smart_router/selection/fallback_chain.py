"""
Fallback Chain for Smart Router
Multi-level fallback with graceful degradation
"""

from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class FallbackLevel(Enum):
    """Fallback levels"""
    PRIMARY = 0
    SECONDARY = 1
    TERTIARY = 2
    RULE_BASED = 3
    STATIC_RESPONSE = 4


class FallbackReason(Enum):
    """Reasons for fallback"""
    MODEL_ERROR = "model_error"
    TIMEOUT = "timeout"
    RATE_LIMIT = "rate_limit"
    HIGH_LATENCY = "high_latency"
    LOW_CONFIDENCE = "low_confidence"
    COST_LIMIT = "cost_limit"
    MANUAL = "manual"


@dataclass
class FallbackEvent:
    """Fallback event record"""
    timestamp: datetime
    from_level: FallbackLevel
    to_level: FallbackLevel
    reason: FallbackReason
    model_from: str
    model_to: str
    session_id: str
    success: bool


@dataclass
class FallbackResult:
    """Result of fallback handling"""
    model: str
    level: FallbackLevel
    reason: FallbackReason
    response: Any
    confidence: float
    latency_ms: float
    recovery_recommended: bool


class FallbackChain:
    """
    Manages fallback chain for model failures.
    Implements circuit breaker and graceful degradation.
    """
    
    # Default chain
    DEFAULT_CHAIN = [
        ('high', FallbackLevel.PRIMARY),
        ('junior', FallbackLevel.SECONDARY),
        ('mini', FallbackLevel.TERTIARY),
        ('rules', FallbackLevel.RULE_BASED),
    ]
    
    # Circuit breaker settings
    FAILURE_THRESHOLD = 5
    RECOVERY_TIMEOUT = 300  # 5 minutes
    
    # Tier-specific chains
    TIER_CHAINS = {
        'heavy': ['high', 'junior', 'mini', 'rules'],
        'medium': ['junior', 'mini', 'rules'],
        'light': ['mini', 'rules'],
    }
    
    def __init__(self):
        self._chains: Dict[str, List[tuple[str, FallbackLevel]]] = {}
        self._circuit_state: Dict[str, Dict[str, Any]] = {}
        self._fallback_history: List[FallbackEvent] = []
        self._failure_counts: Dict[str, int] = {}
        self._last_failure: Dict[str, datetime] = {}
        self._initialized = True
    
    def get_fallback_model(
        self,
        current_model: str,
        reason: FallbackReason,
        tier: str = "medium",
        session_id: str = ""
    ) -> FallbackResult:
        """
        Get next fallback model in chain.
        
        Args:
            current_model: Current model that failed
            reason: Reason for fallback
            tier: Query tier
            session_id: Session identifier
            
        Returns:
            FallbackResult
        """
        # Get chain for tier
        chain = self.TIER_CHAINS.get(tier, self.TIER_CHAINS['medium'])
        
        # Find current position
        current_idx = -1
        for i, model in enumerate(chain):
            if model == current_model:
                current_idx = i
                break
        
        # Get next model
        next_idx = current_idx + 1
        if next_idx >= len(chain):
            # End of chain, use rules
            next_model = 'rules'
            level = FallbackLevel.RULE_BASED
        else:
            next_model = chain[next_idx]
            level = FallbackLevel(next_idx)
        
        # Record fallback event
        event = FallbackEvent(
            timestamp=datetime.now(),
            from_level=FallbackLevel(max(0, current_idx)),
            to_level=level,
            reason=reason,
            model_from=current_model,
            model_to=next_model,
            session_id=session_id,
            success=True
        )
        
        self._fallback_history.append(event)
        
        # Update failure count
        self._update_failure_count(current_model)
        
        logger.warning(f"Fallback: {current_model} -> {next_model} ({reason.value})")
        
        return FallbackResult(
            model=next_model,
            level=level,
            reason=reason,
            response=None,  # Will be filled by caller
            confidence=0.5 + (0.1 * (4 - next_idx)),  # Lower confidence for deeper fallback
            latency_ms=0,
            recovery_recommended=self._should_recommend_recovery(next_model)
        )
    
    def _update_failure_count(self, model: str) -> None:
        """Update failure count for model."""
        if model not in self._failure_counts:
            self._failure_counts[model] = 0
        
        self._failure_counts[model] += 1
        self._last_failure[model] = datetime.now()
        
        # Check circuit breaker
        if self._failure_counts[model] >= self.FAILURE_THRESHOLD:
            self._trip_circuit(model)
    
    def _trip_circuit(self, model: str) -> None:
        """Trip circuit breaker for model."""
        self._circuit_state[model] = {
            'tripped': True,
            'tripped_at': datetime.now(),
            'failure_count': self._failure_counts[model],
        }
        
        logger.error(f"Circuit breaker tripped for {model}")
    
    def is_circuit_open(self, model: str) -> bool:
        """Check if circuit breaker is open for model."""
        state = self._circuit_state.get(model)
        
        if not state or not state.get('tripped'):
            return False
        
        # Check recovery timeout
        tripped_at = state['tripped_at']
        if (datetime.now() - tripped_at).total_seconds() > self.RECOVERY_TIMEOUT:
            # Attempt recovery
            self._reset_circuit(model)
            return False
        
        return True
    
    def _reset_circuit(self, model: str) -> None:
        """Reset circuit breaker for model."""
        self._circuit_state[model] = {
            'tripped': False,
            'recovered_at': datetime.now(),
        }
        self._failure_counts[model] = 0
        
        logger.info(f"Circuit breaker reset for {model}")
    
    def _should_recommend_recovery(self, model: str) -> bool:
        """Check if recovery to primary is recommended."""
        # Recommend recovery if we're deep in fallback
        return model in ['mini', 'rules']
    
    def get_chain_for_tier(self, tier: str) -> List[str]:
        """Get fallback chain for a tier."""
        return self.TIER_CHAINS.get(tier, self.TIER_CHAINS['medium'])
    
    def add_custom_chain(
        self,
        tier: str,
        models: List[str]
    ) -> None:
        """Add custom fallback chain for a tier."""
        self.TIER_CHAINS[tier] = models
        logger.info(f"Added custom chain for {tier}: {models}")
    
    def record_successful_recovery(
        self,
        model: str,
        session_id: str
    ) -> None:
        """Record successful recovery to primary model."""
        # Reset failure count on success
        if model in self._failure_counts:
            self._failure_counts[model] = max(0, self._failure_counts[model] - 1)
        
        logger.info(f"Recorded successful recovery for {model}")
    
    def get_fallback_analytics(
        self,
        hours: int = 24
    ) -> Dict[str, Any]:
        """
        Get fallback analytics.
        
        Args:
            hours: Hours to include
            
        Returns:
            Analytics dict
        """
        from datetime import timedelta
        
        cutoff = datetime.now() - timedelta(hours=hours)
        
        events = [e for e in self._fallback_history if e.timestamp >= cutoff]
        
        if not events:
            return {
                'total_fallbacks': 0,
                'by_reason': {},
                'by_model': {},
            }
        
        # Count by reason
        by_reason: Dict[str, int] = {}
        for e in events:
            by_reason[e.reason.value] = by_reason.get(e.reason.value, 0) + 1
        
        # Count by model
        by_model: Dict[str, int] = {}
        for e in events:
            by_model[e.model_from] = by_model.get(e.model_from, 0) + 1
        
        return {
            'total_fallbacks': len(events),
            'by_reason': by_reason,
            'by_model': by_model,
            'success_rate': sum(1 for e in events if e.success) / len(events),
        }
    
    def get_model_health(self, model: str) -> Dict[str, Any]:
        """Get health status for a model."""
        is_circuit_open = self.is_circuit_open(model)
        failure_count = self._failure_counts.get(model, 0)
        last_failure = self._last_failure.get(model)
        
        return {
            'model': model,
            'circuit_open': is_circuit_open,
            'failure_count': failure_count,
            'last_failure': last_failure.isoformat() if last_failure else None,
            'healthy': not is_circuit_open and failure_count < self.FAILURE_THRESHOLD,
        }
    
    def graceful_degradation(
        self,
        tier: str,
        constraints: Dict[str, Any]
    ) -> str:
        """
        Select model with graceful degradation under constraints.
        
        Args:
            tier: Target tier
            constraints: Constraints (budget, latency, etc.)
            
        Returns:
            Selected model
        """
        chain = self.get_chain_for_tier(tier)
        
        for model in chain:
            # Skip if circuit is open
            if self.is_circuit_open(model):
                continue
            
            # Check constraints
            if constraints.get('max_latency'):
                # Would check model latency here
                pass
            
            if constraints.get('max_cost'):
                # Would check model cost here
                pass
            
            return model
        
        # Return rules as last resort
        return 'rules'
    
    def is_initialized(self) -> bool:
        """Check if chain is initialized."""
        return self._initialized
    
    def get_stats(self) -> Dict[str, Any]:
        """Get chain statistics."""
        return {
            'total_fallbacks': len(self._fallback_history),
            'circuits_tripped': sum(
                1 for s in self._circuit_state.values()
                if s.get('tripped')
            ),
            'model_health': {
                model: self.get_model_health(model)['healthy']
                for model in self._failure_counts
            },
        }
