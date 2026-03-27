"""
A/B Testing Experiment Manager for Smart Router
Experiment creation, traffic splitting, and winner determination
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import random
import hashlib
import logging

logger = logging.getLogger(__name__)


class ExperimentStatus(Enum):
    """Experiment status"""
    DRAFT = "draft"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ExperimentType(Enum):
    """Experiment types"""
    MODEL_COMPARISON = "model_comparison"
    ROUTING_STRATEGY = "routing_strategy"
    FEATURE_FLAG = "feature_flag"


@dataclass
class ExperimentVariant:
    """Experiment variant"""
    name: str
    config: Dict[str, Any]
    traffic_percentage: float
    metrics: Dict[str, float] = field(default_factory=dict)


@dataclass
class Experiment:
    """A/B experiment definition"""
    experiment_id: str
    name: str
    description: str
    experiment_type: ExperimentType
    status: ExperimentStatus
    variants: List[ExperimentVariant]
    start_time: Optional[datetime]
    end_time: Optional[datetime]
    target_metric: str
    min_sample_size: int
    winner: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExperimentResult:
    """Experiment results"""
    experiment_id: str
    variant_results: Dict[str, Dict[str, float]]
    statistical_significance: float
    winner: Optional[str]
    confidence: float
    recommendation: str


class ExperimentManager:
    """
    Manages A/B experiments for routing optimization.
    Handles traffic splitting and statistical analysis.
    """
    
    # Significance threshold
    SIGNIFICANCE_THRESHOLD = 0.95
    MIN_SAMPLE_SIZE = 100
    
    def __init__(self):
        self._experiments: Dict[str, Experiment] = {}
        self._assignments: Dict[str, Dict[str, str]] = {}  # session_id -> {exp_id: variant}
        self._metrics: Dict[str, Dict[str, List[float]]] = {}  # exp_id -> {variant: [metrics]}
        self._initialized = True
    
    def create_experiment(
        self,
        name: str,
        description: str,
        experiment_type: ExperimentType,
        variants: List[Dict[str, Any]],
        target_metric: str = "accuracy",
        min_sample_size: int = None,
        traffic_split: Optional[List[float]] = None
    ) -> Experiment:
        """
        Create a new A/B experiment.
        
        Args:
            name: Experiment name
            description: Experiment description
            experiment_type: Type of experiment
            variants: List of variant configurations
            target_metric: Primary metric to optimize
            min_sample_size: Minimum samples required
            traffic_split: Traffic allocation per variant
            
        Returns:
            Created Experiment
        """
        experiment_id = self._generate_id(name)
        
        # Create variants
        if traffic_split is None:
            # Equal split
            split = 1.0 / len(variants)
            traffic_split = [split] * len(variants)
        
        experiment_variants = []
        for i, v in enumerate(variants):
            variant = ExperimentVariant(
                name=v['name'],
                config=v.get('config', {}),
                traffic_percentage=traffic_split[i]
            )
            experiment_variants.append(variant)
        
        experiment = Experiment(
            experiment_id=experiment_id,
            name=name,
            description=description,
            experiment_type=experiment_type,
            status=ExperimentStatus.DRAFT,
            variants=experiment_variants,
            start_time=None,
            end_time=None,
            target_metric=target_metric,
            min_sample_size=min_sample_size or self.MIN_SAMPLE_SIZE
        )
        
        self._experiments[experiment_id] = experiment
        self._metrics[experiment_id] = {
            v.name: [] for v in experiment_variants
        }
        
        logger.info(f"Created experiment: {experiment_id}")
        
        return experiment
    
    def _generate_id(self, name: str) -> str:
        """Generate unique experiment ID."""
        data = f"{name}:{datetime.now().isoformat()}"
        hash_val = hashlib.sha256(data.encode()).hexdigest()[:8]
        return f"exp_{hash_val}"
    
    def start_experiment(
        self,
        experiment_id: str
    ) -> bool:
        """
        Start an experiment.
        
        Args:
            experiment_id: Experiment to start
            
        Returns:
            True if started successfully
        """
        experiment = self._experiments.get(experiment_id)
        if not experiment:
            return False
        
        if experiment.status != ExperimentStatus.DRAFT:
            return False
        
        experiment.status = ExperimentStatus.RUNNING
        experiment.start_time = datetime.now()
        
        logger.info(f"Started experiment: {experiment_id}")
        
        return True
    
    def pause_experiment(
        self,
        experiment_id: str
    ) -> bool:
        """Pause an experiment."""
        experiment = self._experiments.get(experiment_id)
        if not experiment:
            return False
        
        experiment.status = ExperimentStatus.PAUSED
        logger.info(f"Paused experiment: {experiment_id}")
        
        return True
    
    def get_variant(
        self,
        experiment_id: str,
        session_id: str
    ) -> Optional[str]:
        """
        Get variant for a session.
        
        Args:
            experiment_id: Experiment identifier
            session_id: Session identifier
            
        Returns:
            Variant name or None
        """
        experiment = self._experiments.get(experiment_id)
        if not experiment or experiment.status != ExperimentStatus.RUNNING:
            return None
        
        # Check existing assignment
        if session_id in self._assignments:
            if experiment_id in self._assignments[session_id]:
                return self._assignments[session_id][experiment_id]
        
        # Assign variant based on traffic split
        variant = self._assign_variant(experiment, session_id)
        
        # Store assignment
        if session_id not in self._assignments:
            self._assignments[session_id] = {}
        self._assignments[session_id][experiment_id] = variant
        
        return variant
    
    def _assign_variant(
        self,
        experiment: Experiment,
        session_id: str
    ) -> str:
        """Assign variant using consistent hashing."""
        # Use hash for consistent assignment
        hash_val = int(
            hashlib.sha256(f"{experiment.experiment_id}:{session_id}".encode())
            .hexdigest(), 16
        )
        
        # Normalize to 0-1
        normalized = (hash_val % 10000) / 10000
        
        # Assign based on traffic split
        cumulative = 0
        for variant in experiment.variants:
            cumulative += variant.traffic_percentage
            if normalized <= cumulative:
                return variant.name
        
        # Default to last variant
        return experiment.variants[-1].name
    
    def record_metric(
        self,
        experiment_id: str,
        variant: str,
        metric_name: str,
        value: float
    ) -> None:
        """Record a metric for an experiment variant."""
        if experiment_id not in self._metrics:
            return
        
        if variant not in self._metrics[experiment_id]:
            return
        
        if metric_name == experiment.target_metric:
            self._metrics[experiment_id][variant].append(value)
    
    def analyze_results(
        self,
        experiment_id: str
    ) -> Optional[ExperimentResult]:
        """
        Analyze experiment results.
        
        Args:
            experiment_id: Experiment to analyze
            
        Returns:
            ExperimentResult or None
        """
        experiment = self._experiments.get(experiment_id)
        if not experiment:
            return None
        
        metrics = self._metrics.get(experiment_id, {})
        
        # Calculate variant statistics
        variant_results = {}
        for variant_name, values in metrics.items():
            if not values:
                continue
            
            variant_results[variant_name] = {
                'mean': sum(values) / len(values),
                'count': len(values),
                'sum': sum(values),
            }
        
        # Determine winner
        winner = None
        confidence = 0
        
        if len(variant_results) >= 2:
            # Simple comparison (production would use proper statistical test)
            best_variant = max(
                variant_results.items(),
                key=lambda x: x[1]['mean']
            )
            
            # Check sample size
            if best_variant[1]['count'] >= experiment.min_sample_size:
                # Calculate confidence (simplified)
                confidence = self._calculate_confidence(
                    variant_results,
                    best_variant[0]
                )
                
                if confidence >= self.SIGNIFICANCE_THRESHOLD:
                    winner = best_variant[0]
        
        # Generate recommendation
        recommendation = self._generate_recommendation(
            experiment,
            variant_results,
            winner,
            confidence
        )
        
        return ExperimentResult(
            experiment_id=experiment_id,
            variant_results=variant_results,
            statistical_significance=confidence,
            winner=winner,
            confidence=confidence,
            recommendation=recommendation
        )
    
    def _calculate_confidence(
        self,
        variant_results: Dict[str, Dict[str, float]],
        best_variant: str
    ) -> float:
        """Calculate statistical confidence (simplified)."""
        # Production would use t-test or similar
        best_mean = variant_results[best_variant]['mean']
        best_count = variant_results[best_variant]['count']
        
        # Compare with others
        other_means = [
            v['mean'] for k, v in variant_results.items()
            if k != best_variant
        ]
        
        if not other_means:
            return 0
        
        avg_other = sum(other_means) / len(other_means)
        
        # Simple effect size based confidence
        effect = (best_mean - avg_other) / max(avg_other, 0.001)
        
        # Scale to 0-1
        confidence = min(1.0, max(0, effect * 5 + 0.5))
        
        # Adjust for sample size
        sample_factor = min(1.0, best_count / self.MIN_SAMPLE_SIZE)
        
        return confidence * sample_factor
    
    def _generate_recommendation(
        self,
        experiment: Experiment,
        variant_results: Dict,
        winner: Optional[str],
        confidence: float
    ) -> str:
        """Generate recommendation string."""
        if not variant_results:
            return "Insufficient data to make recommendation"
        
        if winner and confidence >= self.SIGNIFICANCE_THRESHOLD:
            return f"Recommend promoting variant '{winner}' with {confidence:.1%} confidence"
        
        if confidence > 0.8:
            return f"Early indication favors '{winner}' but need more data"
        
        return "Continue experiment until statistical significance is reached"
    
    def conclude_experiment(
        self,
        experiment_id: str,
        promote_winner: bool = True
    ) -> Optional[str]:
        """
        Conclude an experiment and optionally promote winner.
        
        Args:
            experiment_id: Experiment to conclude
            promote_winner: Whether to promote winning variant
            
        Returns:
            Winner variant name or None
        """
        experiment = self._experiments.get(experiment_id)
        if not experiment:
            return None
        
        result = self.analyze_results(experiment_id)
        
        if result and result.winner:
            experiment.winner = result.winner
        
        experiment.status = ExperimentStatus.COMPLETED
        experiment.end_time = datetime.now()
        
        logger.info(f"Concluded experiment {experiment_id}: winner = {experiment.winner}")
        
        return experiment.winner
    
    def get_experiment(
        self,
        experiment_id: str
    ) -> Optional[Experiment]:
        """Get experiment by ID."""
        return self._experiments.get(experiment_id)
    
    def list_experiments(
        self,
        status: Optional[ExperimentStatus] = None
    ) -> List[Experiment]:
        """List experiments."""
        experiments = list(self._experiments.values())
        
        if status:
            experiments = [e for e in experiments if e.status == status]
        
        return experiments
    
    def is_initialized(self) -> bool:
        """Check if manager is initialized."""
        return self._initialized
    
    def get_stats(self) -> Dict[str, Any]:
        """Get manager statistics."""
        return {
            'total_experiments': len(self._experiments),
            'running_experiments': sum(
                1 for e in self._experiments.values()
                if e.status == ExperimentStatus.RUNNING
            ),
            'total_assignments': len(self._assignments),
        }
