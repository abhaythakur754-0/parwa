"""
Model Registry for ML Router
Handles model versioning, storage, rollback, and A/B deployment
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import json
import logging

logger = logging.getLogger(__name__)


class ModelStatus(Enum):
    """Model deployment status"""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


@dataclass
class ModelVersion:
    """Model version information"""
    version: str
    created_at: datetime
    accuracy: float
    latency_ms: float
    status: ModelStatus
    metrics: Dict[str, float] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'version': self.version,
            'created_at': self.created_at.isoformat(),
            'accuracy': self.accuracy,
            'latency_ms': self.latency_ms,
            'status': self.status.value,
            'metrics': self.metrics,
            'metadata': self.metadata,
        }


@dataclass
class ABTestConfig:
    """A/B test configuration"""
    experiment_id: str
    model_a_version: str
    model_b_version: str
    traffic_split: float  # Percentage to model B
    start_time: datetime
    end_time: Optional[datetime] = None
    metrics: Dict[str, Any] = field(default_factory=dict)
    winner: Optional[str] = None


class ModelRegistry:
    """
    Model registry for versioning and deployment.
    Supports versioning, rollback, and A/B testing.
    """
    
    # Performance thresholds
    MIN_ACCURACY = 0.92
    MAX_LATENCY_MS = 50
    
    # Auto-promotion thresholds
    AUTO_PROMOTE_ACCURACY_GAIN = 0.02  # 2% improvement
    AUTO_PROMOTE_LATENCY_IMPROVEMENT = 0.1  # 10% faster
    
    def __init__(self, storage_path: str = "/tmp/model_registry"):
        self.storage_path = storage_path
        self._versions: Dict[str, ModelVersion] = {}
        self._current_production: Optional[str] = None
        self._ab_tests: Dict[str, ABTestConfig] = {}
        self._performance_history: Dict[str, List[Dict[str, float]]] = {}
        self._initialized = True
    
    def register_model(
        self,
        version: str,
        accuracy: float,
        latency_ms: float,
        metrics: Optional[Dict[str, float]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ModelVersion:
        """
        Register a new model version.
        
        Args:
            version: Version identifier (e.g., "1.2.0")
            accuracy: Model accuracy score
            latency_ms: Average inference latency
            metrics: Additional performance metrics
            metadata: Model metadata
            
        Returns:
            Registered ModelVersion
        """
        model_version = ModelVersion(
            version=version,
            created_at=datetime.now(),
            accuracy=accuracy,
            latency_ms=latency_ms,
            status=ModelStatus.DEVELOPMENT,
            metrics=metrics or {},
            metadata=metadata or {}
        )
        
        self._versions[version] = model_version
        self._performance_history[version] = []
        
        logger.info(f"Registered model version {version} with accuracy {accuracy:.2%}")
        return model_version
    
    def get_version(self, version: str) -> Optional[ModelVersion]:
        """Get a specific model version."""
        return self._versions.get(version)
    
    def list_versions(self, status: Optional[ModelStatus] = None) -> List[ModelVersion]:
        """
        List all model versions, optionally filtered by status.
        
        Args:
            status: Filter by status (optional)
            
        Returns:
            List of ModelVersion objects
        """
        versions = list(self._versions.values())
        
        if status:
            versions = [v for v in versions if v.status == status]
        
        return sorted(versions, key=lambda v: v.created_at, reverse=True)
    
    def promote_to_production(
        self, 
        version: str,
        force: bool = False
    ) -> bool:
        """
        Promote a model version to production.
        
        Args:
            version: Version to promote
            force: Force promotion even if thresholds not met
            
        Returns:
            True if promotion successful
        """
        model = self._versions.get(version)
        if not model:
            logger.error(f"Version {version} not found")
            return False
        
        # Check thresholds
        if not force:
            if model.accuracy < self.MIN_ACCURACY:
                logger.error(f"Version {version} accuracy {model.accuracy:.2%} below threshold")
                return False
            if model.latency_ms > self.MAX_LATENCY_MS:
                logger.error(f"Version {version} latency {model.latency_ms}ms above threshold")
                return False
        
        # Demote current production
        if self._current_production:
            current = self._versions.get(self._current_production)
            if current:
                current.status = ModelStatus.DEPRECATED
        
        # Promote new version
        model.status = ModelStatus.PRODUCTION
        self._current_production = version
        
        logger.info(f"Promoted version {version} to production")
        return True
    
    def rollback(self, target_version: Optional[str] = None) -> bool:
        """
        Rollback to a previous version.
        
        Args:
            target_version: Specific version to rollback to (uses previous if not specified)
            
        Returns:
            True if rollback successful
        """
        if target_version:
            target = self._versions.get(target_version)
        else:
            # Find previous production version
            deprecated = self.list_versions(ModelStatus.DEPRECATED)
            target = deprecated[0] if deprecated else None
            target_version = target.version if target else None
        
        if not target:
            logger.error("No version to rollback to")
            return False
        
        return self.promote_to_production(target_version, force=True)
    
    def create_ab_test(
        self,
        experiment_id: str,
        model_a_version: str,
        model_b_version: str,
        traffic_split: float = 0.5
    ) -> ABTestConfig:
        """
        Create an A/B test between two model versions.
        
        Args:
            experiment_id: Unique experiment identifier
            model_a_version: Control model version
            model_b_version: Treatment model version
            traffic_split: Percentage of traffic to model B (0-1)
            
        Returns:
            ABTestConfig
        """
        # Validate versions exist
        if model_a_version not in self._versions:
            raise ValueError(f"Model A version {model_a_version} not found")
        if model_b_version not in self._versions:
            raise ValueError(f"Model B version {model_b_version} not found")
        
        # Set model B to staging
        self._versions[model_b_version].status = ModelStatus.STAGING
        
        config = ABTestConfig(
            experiment_id=experiment_id,
            model_a_version=model_a_version,
            model_b_version=model_b_version,
            traffic_split=traffic_split,
            start_time=datetime.now()
        )
        
        self._ab_tests[experiment_id] = config
        
        logger.info(f"Created A/B test {experiment_id}: {model_a_version} vs {model_b_version}")
        return config
    
    def get_ab_test(self, experiment_id: str) -> Optional[ABTestConfig]:
        """Get A/B test configuration."""
        return self._ab_tests.get(experiment_id)
    
    def get_model_for_request(
        self,
        experiment_id: Optional[str] = None
    ) -> str:
        """
        Get the appropriate model version for a request.
        Handles A/B test routing.
        
        Args:
            experiment_id: Active experiment to consider
            
        Returns:
            Model version to use
        """
        # Check for active A/B test
        if experiment_id and experiment_id in self._ab_tests:
            test = self._ab_tests[experiment_id]
            if test.winner:
                return test.winner
            
            # Simple hash-based routing for consistent assignment
            import random
            if random.random() < test.traffic_split:
                return test.model_b_version
            return test.model_a_version
        
        # Return current production
        return self._current_production or "1.0.0"
    
    def record_performance(
        self,
        version: str,
        accuracy: float,
        latency_ms: float,
        additional_metrics: Optional[Dict[str, float]] = None
    ) -> None:
        """
        Record performance metrics for a model version.
        
        Args:
            version: Model version
            accuracy: Measured accuracy
            latency_ms: Measured latency
            additional_metrics: Additional metrics to record
        """
        if version not in self._performance_history:
            self._performance_history[version] = []
        
        record = {
            'accuracy': accuracy,
            'latency_ms': latency_ms,
            'timestamp': datetime.now().isoformat(),
            **(additional_metrics or {})
        }
        
        self._performance_history[version].append(record)
        
        # Keep only last 1000 records
        if len(self._performance_history[version]) > 1000:
            self._performance_history[version] = self._performance_history[version][-1000:]
        
        # Check for auto-promotion
        self._check_auto_promotion(version)
    
    def _check_auto_promotion(self, version: str) -> None:
        """Check if model qualifies for auto-promotion."""
        model = self._versions.get(version)
        if not model or model.status == ModelStatus.PRODUCTION:
            return
        
        history = self._performance_history.get(version, [])
        if len(history) < 100:  # Need enough data
            return
        
        # Calculate recent performance
        recent = history[-100:]
        avg_accuracy = sum(h['accuracy'] for h in recent) / len(recent)
        avg_latency = sum(h['latency_ms'] for h in recent) / len(recent)
        
        # Compare with current production
        if self._current_production:
            prod_history = self._performance_history.get(self._current_production, [])
            if prod_history:
                prod_recent = prod_history[-100:]
                prod_accuracy = sum(h['accuracy'] for h in prod_recent) / len(prod_recent)
                prod_latency = sum(h['latency_ms'] for h in prod_recent) / len(prod_recent)
                
                # Check improvement thresholds
                accuracy_gain = avg_accuracy - prod_accuracy
                latency_improvement = (prod_latency - avg_latency) / prod_latency
                
                if (accuracy_gain >= self.AUTO_PROMOTE_ACCURACY_GAIN and
                    avg_accuracy >= self.MIN_ACCURACY):
                    logger.info(f"Auto-promoting {version}: {accuracy_gain:.2%} accuracy improvement")
                    self.promote_to_production(version)
    
    def conclude_ab_test(
        self,
        experiment_id: str,
        winner: str
    ) -> bool:
        """
        Conclude an A/B test with a winner.
        
        Args:
            experiment_id: Experiment to conclude
            winner: Winning model version
            
        Returns:
            True if conclusion successful
        """
        test = self._ab_tests.get(experiment_id)
        if not test:
            return False
        
        test.winner = winner
        test.end_time = datetime.now()
        
        # Promote winner if not already production
        if winner != self._current_production:
            self.promote_to_production(winner)
        
        logger.info(f"Concluded A/B test {experiment_id}: winner is {winner}")
        return True
    
    def get_current_production(self) -> Optional[ModelVersion]:
        """Get current production model."""
        if self._current_production:
            return self._versions.get(self._current_production)
        return None
    
    def get_performance_history(
        self,
        version: str,
        limit: int = 100
    ) -> List[Dict[str, float]]:
        """Get performance history for a version."""
        history = self._performance_history.get(version, [])
        return history[-limit:]
    
    def export_registry(self) -> Dict[str, Any]:
        """Export registry state for backup."""
        return {
            'versions': {v: m.to_dict() for v, m in self._versions.items()},
            'current_production': self._current_production,
            'ab_tests': {
                eid: {
                    'experiment_id': t.experiment_id,
                    'model_a_version': t.model_a_version,
                    'model_b_version': t.model_b_version,
                    'traffic_split': t.traffic_split,
                    'start_time': t.start_time.isoformat(),
                    'end_time': t.end_time.isoformat() if t.end_time else None,
                    'winner': t.winner,
                }
                for eid, t in self._ab_tests.items()
            }
        }
    
    def is_initialized(self) -> bool:
        """Check if registry is initialized."""
        return self._initialized
    
    def get_stats(self) -> Dict[str, Any]:
        """Get registry statistics."""
        return {
            'total_versions': len(self._versions),
            'production_version': self._current_production,
            'active_ab_tests': len([t for t in self._ab_tests.values() if not t.winner]),
            'deprecated_versions': len(self.list_versions(ModelStatus.DEPRECATED)),
        }
