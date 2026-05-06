"""
Model Selector for Smart Router
Dynamic model selection based on complexity and load
"""

from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import random
import logging

logger = logging.getLogger(__name__)


class ModelTier(Enum):
    """Model tier levels"""
    LIGHT = "light"      # Fast, cheap models
    MEDIUM = "medium"    # Balanced models
    HEAVY = "heavy"      # Capable, expensive models


@dataclass
class ModelInfo:
    """Model information"""
    name: str
    tier: ModelTier
    cost_per_1k_tokens: float
    avg_latency_ms: float
    max_tokens: int
    capabilities: List[str]
    health_status: str = "healthy"
    current_load: float = 0.0


@dataclass
class SelectionResult:
    """Model selection result"""
    selected_model: str
    tier: ModelTier
    reason: str
    estimated_cost: float
    estimated_latency_ms: float
    alternatives: List[str]
    confidence: float
    timestamp: datetime = field(default_factory=datetime.now)


class ModelSelector:
    """
    Selects optimal model based on query complexity and constraints.
    Supports load balancing and health monitoring.
    """
    
    # Available models
    MODELS = {
        # Light tier
        'mini': ModelInfo(
            name='mini',
            tier=ModelTier.LIGHT,
            cost_per_1k_tokens=0.0001,
            avg_latency_ms=50,
            max_tokens=4096,
            capabilities=['simple_qa', 'classification']
        ),
        'mini-pro': ModelInfo(
            name='mini-pro',
            tier=ModelTier.LIGHT,
            cost_per_1k_tokens=0.0002,
            avg_latency_ms=60,
            max_tokens=8192,
            capabilities=['simple_qa', 'classification', 'summarization']
        ),
        
        # Medium tier
        'junior': ModelInfo(
            name='junior',
            tier=ModelTier.MEDIUM,
            cost_per_1k_tokens=0.001,
            avg_latency_ms=100,
            max_tokens=16384,
            capabilities=['reasoning', 'complex_qa', 'multi_turn', 'classification']
        ),
        'junior-plus': ModelInfo(
            name='junior-plus',
            tier=ModelTier.MEDIUM,
            cost_per_1k_tokens=0.002,
            avg_latency_ms=150,
            max_tokens=32768,
            capabilities=['reasoning', 'complex_qa', 'multi_turn', 'code', 'analysis']
        ),
        
        # Heavy tier
        'high': ModelInfo(
            name='high',
            tier=ModelTier.HEAVY,
            cost_per_1k_tokens=0.01,
            avg_latency_ms=300,
            max_tokens=128000,
            capabilities=['advanced_reasoning', 'complex_analysis', 'code', 'multi_modal']
        ),
        'high-reasoning': ModelInfo(
            name='high-reasoning',
            tier=ModelTier.HEAVY,
            cost_per_1k_tokens=0.02,
            avg_latency_ms=500,
            max_tokens=128000,
            capabilities=['advanced_reasoning', 'complex_analysis', 'deep_thinking']
        ),
    }
    
    # Complexity thresholds
    COMPLEXITY_THRESHOLDS = {
        'light': {'max_words': 15, 'max_entities': 1},
        'medium': {'max_words': 50, 'max_entities': 3},
        'heavy': {'min_words': 50, 'min_entities': 3},
    }
    
    def __init__(self):
        self._model_health: Dict[str, str] = {
            name: "healthy" for name in self.MODELS
        }
        self._model_load: Dict[str, float] = {
            name: 0.0 for name in self.MODELS
        }
        self._selection_history: List[SelectionResult] = []
        self._initialized = True
    
    def select(
        self,
        query: str,
        complexity_score: float = 0.5,
        required_capabilities: Optional[List[str]] = None,
        budget_remaining: Optional[float] = None,
        max_latency_ms: Optional[float] = None,
        client_tier: str = "basic"
    ) -> SelectionResult:
        """
        Select optimal model for a query.
        
        Args:
            query: User query
            complexity_score: Query complexity (0-1)
            required_capabilities: Required model capabilities
            budget_remaining: Remaining budget
            max_latency_ms: Maximum allowed latency
            client_tier: Client tier for tier limits
            
        Returns:
            SelectionResult with selected model
        """
        # Determine target tier based on complexity
        target_tier = self._get_target_tier(complexity_score, client_tier)
        
        # Get candidate models
        candidates = self._get_candidates(
            target_tier,
            required_capabilities,
            budget_remaining,
            max_latency_ms
        )
        
        if not candidates:
            # Fallback to any available
            candidates = list(self.MODELS.keys())
        
        # Select best model
        selected = self._select_best(candidates, target_tier)
        
        # Get model info
        model_info = self.MODELS[selected]
        
        # Estimate cost and latency
        estimated_tokens = len(query.split()) * 2  # Rough estimate
        estimated_cost = (estimated_tokens / 1000) * model_info.cost_per_1k_tokens
        estimated_latency = model_info.avg_latency_ms
        
        # Get alternatives
        alternatives = [m for m in candidates if m != selected][:3]
        
        # Build selection explanation
        reason = self._build_reason(selected, target_tier, complexity_score)
        
        result = SelectionResult(
            selected_model=selected,
            tier=model_info.tier,
            reason=reason,
            estimated_cost=estimated_cost,
            estimated_latency_ms=estimated_latency,
            alternatives=alternatives,
            confidence=self._calculate_confidence(selected, candidates)
        )
        
        self._selection_history.append(result)
        
        return result
    
    def _get_target_tier(
        self,
        complexity_score: float,
        client_tier: str
    ) -> ModelTier:
        """Determine target tier based on complexity."""
        # Client tier limits
        tier_limits = {
            'basic': ModelTier.MEDIUM,
            'pro': ModelTier.MEDIUM,
            'enterprise': ModelTier.HEAVY,
        }
        max_tier = tier_limits.get(client_tier, ModelTier.MEDIUM)
        
        # Complexity mapping
        if complexity_score < 0.3:
            target = ModelTier.LIGHT
        elif complexity_score < 0.7:
            target = ModelTier.MEDIUM
        else:
            target = ModelTier.HEAVY
        
        # Enforce client limit
        tier_order = [ModelTier.LIGHT, ModelTier.MEDIUM, ModelTier.HEAVY]
        if tier_order.index(target) > tier_order.index(max_tier):
            target = max_tier
        
        return target
    
    def _get_candidates(
        self,
        target_tier: ModelTier,
        required_capabilities: Optional[List[str]],
        budget_remaining: Optional[float],
        max_latency_ms: Optional[float]
    ) -> List[str]:
        """Get candidate models based on constraints."""
        candidates = []
        
        for name, info in self.MODELS.items():
            # Check health
            if self._model_health.get(name) != "healthy":
                continue
            
            # Check tier
            if info.tier != target_tier:
                continue
            
            # Check capabilities
            if required_capabilities:
                if not all(c in info.capabilities for c in required_capabilities):
                    continue
            
            # Check budget
            if budget_remaining is not None:
                if info.cost_per_1k_tokens > budget_remaining:
                    continue
            
            # Check latency
            if max_latency_ms is not None:
                if info.avg_latency_ms > max_latency_ms:
                    continue
            
            candidates.append(name)
        
        return candidates
    
    def _select_best(
        self,
        candidates: List[str],
        target_tier: ModelTier
    ) -> str:
        """Select best model from candidates."""
        if not candidates:
            # Return default
            return 'junior'
        
        if len(candidates) == 1:
            return candidates[0]
        
        # Score candidates
        scores = {}
        for name in candidates:
            info = self.MODELS[name]
            load = self._model_load.get(name, 0)
            
            # Lower load is better
            load_score = 1 - load
            
            # Prefer lower cost for same tier
            cost_score = 1 / (info.cost_per_1k_tokens + 0.001)
            
            # Prefer lower latency
            latency_score = 1 / (info.avg_latency_ms + 1)
            
            # Combined score
            scores[name] = load_score * 0.4 + cost_score * 0.3 + latency_score * 0.3
        
        # Return highest scoring
        return max(scores, key=scores.get)
    
    def _build_reason(
        self,
        selected: str,
        target_tier: ModelTier,
        complexity_score: float
    ) -> str:
        """Build selection reason explanation."""
        info = self.MODELS[selected]
        
        reasons = []
        reasons.append(f"Selected {selected} ({target_tier.value} tier)")
        reasons.append(f"Complexity score: {complexity_score:.2f}")
        reasons.append(f"Health: {self._model_health.get(selected, 'unknown')}")
        reasons.append(f"Current load: {self._model_load.get(selected, 0):.1%}")
        
        return " | ".join(reasons)
    
    def _calculate_confidence(
        self,
        selected: str,
        candidates: List[str]
    ) -> float:
        """Calculate selection confidence."""
        if len(candidates) <= 1:
            return 1.0
        
        # Higher confidence if clear winner
        return 0.7 + (0.3 / len(candidates))
    
    def update_health(
        self,
        model_name: str,
        status: str
    ) -> None:
        """Update model health status."""
        self._model_health[model_name] = status
        logger.info(f"Updated {model_name} health to {status}")
    
    def update_load(
        self,
        model_name: str,
        load: float
    ) -> None:
        """Update model load."""
        self._model_load[model_name] = max(0, min(1, load))
    
    def get_model_info(self, model_name: str) -> Optional[ModelInfo]:
        """Get model information."""
        return self.MODELS.get(model_name)
    
    def list_available_models(
        self,
        tier: Optional[ModelTier] = None
    ) -> List[ModelInfo]:
        """List available models."""
        models = list(self.MODELS.values())
        
        if tier:
            models = [m for m in models if m.tier == tier]
        
        # Filter healthy only
        models = [
            m for m in models 
            if self._model_health.get(m.name) == "healthy"
        ]
        
        return models
    
    def get_stats(self) -> Dict[str, Any]:
        """Get selector statistics."""
        return {
            'total_selections': len(self._selection_history),
            'healthy_models': sum(
                1 for s in self._model_health.values() 
                if s == "healthy"
            ),
            'model_health': self._model_health,
            'model_load': self._model_load,
        }
    
    def is_initialized(self) -> bool:
        """Check if selector is initialized."""
        return self._initialized
