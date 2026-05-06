"""
Ensemble Voter for Agent Lightning 94% Accuracy.

Combines multiple models for improved accuracy.
"""
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone
from dataclasses import dataclass, field
import asyncio

from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


@dataclass
class VotingResult:
    """Result of ensemble voting."""
    prediction: str
    confidence: float
    votes: Dict[str, int] = field(default_factory=dict)
    weights_used: Dict[str, float] = field(default_factory=dict)
    agreement_ratio: float = 0.0
    voting_method: str = "majority"


class EnsembleVoter:
    """
    Ensemble voting for improved accuracy.
    
    Features:
    - Multi-model voting
    - Weighted voting
    - Confidence aggregation
    - Disagreement detection
    - Dynamic weighting
    """
    
    def __init__(
        self,
        models: Optional[Dict[str, Any]] = None,
        weights: Optional[Dict[str, float]] = None
    ):
        """
        Initialize ensemble voter.
        
        Args:
            models: Dictionary of model name to model instance
            weights: Dictionary of model name to weight
        """
        self.models = models or {}
        self.weights = weights or {}
        self._default_weights = True
        
        if weights:
            self._default_weights = False
    
    def add_model(
        self,
        name: str,
        model: Any,
        weight: float = 1.0
    ) -> None:
        """Add a model to the ensemble."""
        self.models[name] = model
        self.weights[name] = weight
        self._default_weights = False
    
    async def predict(
        self,
        query: str,
        method: str = "weighted"
    ) -> VotingResult:
        """
        Get ensemble prediction.
        
        Args:
            query: Input query
            method: Voting method ('majority', 'weighted', 'confidence')
            
        Returns:
            VotingResult with ensemble prediction
        """
        if not self.models:
            return VotingResult(
                prediction="unknown",
                confidence=0.0
            )
        
        # Get predictions from all models
        predictions = await self._get_all_predictions(query)
        
        if method == "majority":
            return self._majority_vote(predictions)
        elif method == "weighted":
            return self._weighted_vote(predictions)
        elif method == "confidence":
            return self._confidence_vote(predictions)
        
        return self._majority_vote(predictions)
    
    async def _get_all_predictions(
        self,
        query: str
    ) -> Dict[str, Tuple[str, float]]:
        """Get predictions from all models."""
        predictions = {}
        
        for name, model in self.models.items():
            try:
                if asyncio.iscoroutinefunction(model.predict):
                    result = await model.predict(query)
                else:
                    result = model.predict(query)
                
                if isinstance(result, tuple):
                    predictions[name] = result
                elif isinstance(result, dict):
                    predictions[name] = (
                        result.get("action", "unknown"),
                        result.get("confidence", 0.5)
                    )
                else:
                    predictions[name] = (str(result), 0.5)
                    
            except Exception as e:
                logger.error({
                    "event": "model_prediction_error",
                    "model": name,
                    "error": str(e)
                })
        
        return predictions
    
    def _majority_vote(
        self,
        predictions: Dict[str, Tuple[str, float]]
    ) -> VotingResult:
        """Perform majority voting."""
        votes: Dict[str, int] = {}
        confidences: Dict[str, List[float]] = {}
        
        for model_name, (pred, conf) in predictions.items():
            votes[pred] = votes.get(pred, 0) + 1
            if pred not in confidences:
                confidences[pred] = []
            confidences[pred].append(conf)
        
        # Find majority
        majority_pred = max(votes, key=votes.get)
        avg_confidence = sum(confidences[majority_pred]) / len(confidences[majority_pred])
        
        total_votes = sum(votes.values())
        agreement_ratio = votes[majority_pred] / total_votes if total_votes > 0 else 0
        
        return VotingResult(
            prediction=majority_pred,
            confidence=avg_confidence,
            votes=votes,
            agreement_ratio=agreement_ratio,
            voting_method="majority"
        )
    
    def _weighted_vote(
        self,
        predictions: Dict[str, Tuple[str, float]]
    ) -> VotingResult:
        """Perform weighted voting."""
        weighted_scores: Dict[str, float] = {}
        weights_used: Dict[str, float] = {}
        
        for model_name, (pred, conf) in predictions.items():
            weight = self.weights.get(model_name, 1.0)
            weights_used[model_name] = weight
            score = weight * conf
            
            weighted_scores[pred] = weighted_scores.get(pred, 0) + score
        
        winner = max(weighted_scores, key=weighted_scores.get)
        
        # Calculate agreement
        total_score = sum(weighted_scores.values())
        agreement_ratio = weighted_scores[winner] / total_score if total_score > 0 else 0
        
        return VotingResult(
            prediction=winner,
            confidence=agreement_ratio,
            weights_used=weights_used,
            agreement_ratio=agreement_ratio,
            voting_method="weighted"
        )
    
    def _confidence_vote(
        self,
        predictions: Dict[str, Tuple[str, float]]
    ) -> VotingResult:
        """Select prediction with highest confidence."""
        best_pred = "unknown"
        best_conf = 0.0
        
        for model_name, (pred, conf) in predictions.items():
            if conf > best_conf:
                best_pred = pred
                best_conf = conf
        
        return VotingResult(
            prediction=best_pred,
            confidence=best_conf,
            voting_method="confidence"
        )
    
    def update_weights(
        self,
        performance: Dict[str, float]
    ) -> None:
        """
        Update model weights based on performance.
        
        Args:
            performance: Dictionary of model name to accuracy
        """
        total_perf = sum(performance.values())
        
        if total_perf > 0:
            for name, acc in performance.items():
                # Weight proportional to accuracy
                self.weights[name] = acc / total_perf * len(performance)
        
        logger.info({
            "event": "weights_updated",
            "weights": self.weights
        })
    
    def get_model_count(self) -> int:
        """Get number of models in ensemble."""
        return len(self.models)
