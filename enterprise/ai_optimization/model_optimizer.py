"""
Model Optimizer - Week 55 Advanced AI Optimization

Provides model optimization and quantization capabilities for AI models.
Supports multiple optimization types including quantization, pruning,
distillation, and fine-tuning.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Callable
from datetime import datetime
import json
import logging

logger = logging.getLogger(__name__)


class OptimizationType(Enum):
    """Types of model optimization techniques."""
    QUANTIZATION = "quantization"
    PRUNING = "pruning"
    DISTILLATION = "distillation"
    FINE_TUNING = "fine_tuning"


class PrecisionLevel(Enum):
    """Precision levels for model weights and activations."""
    FP32 = "fp32"  # 32-bit floating point
    FP16 = "fp16"  # 16-bit floating point
    INT8 = "int8"  # 8-bit integer
    INT4 = "int4"  # 4-bit integer


class OptimizationStatus(Enum):
    """Status of optimization process."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ModelMetrics:
    """Metrics for model performance measurement."""
    latency_ms: float = 0.0
    throughput_qps: float = 0.0
    memory_mb: float = 0.0
    model_size_mb: float = 0.0
    accuracy: float = 0.0
    f1_score: float = 0.0
    perplexity: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary."""
        return {
            "latency_ms": self.latency_ms,
            "throughput_qps": self.throughput_qps,
            "memory_mb": self.memory_mb,
            "model_size_mb": self.model_size_mb,
            "accuracy": self.accuracy,
            "f1_score": self.f1_score,
            "perplexity": self.perplexity,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ModelMetrics":
        """Create metrics from dictionary."""
        return cls(
            latency_ms=data.get("latency_ms", 0.0),
            throughput_qps=data.get("throughput_qps", 0.0),
            memory_mb=data.get("memory_mb", 0.0),
            model_size_mb=data.get("model_size_mb", 0.0),
            accuracy=data.get("accuracy", 0.0),
            f1_score=data.get("f1_score", 0.0),
            perplexity=data.get("perplexity"),
        )


@dataclass
class OptimizationConfig:
    """Configuration for optimization process."""
    optimization_type: OptimizationType
    target_precision: Optional[PrecisionLevel] = None
    compression_ratio: float = 0.5
    preserve_accuracy: bool = True
    max_accuracy_drop: float = 0.02  # 2% max accuracy drop
    calibration_samples: int = 100
    layer_specific_config: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary."""
        return {
            "optimization_type": self.optimization_type.value,
            "target_precision": self.target_precision.value if self.target_precision else None,
            "compression_ratio": self.compression_ratio,
            "preserve_accuracy": self.preserve_accuracy,
            "max_accuracy_drop": self.max_accuracy_drop,
            "calibration_samples": self.calibration_samples,
            "layer_specific_config": self.layer_specific_config,
        }


@dataclass
class OptimizationResult:
    """Result of model optimization."""
    optimization_id: str
    optimization_type: OptimizationType
    status: OptimizationStatus
    metrics_before: ModelMetrics
    metrics_after: ModelMetrics
    precision_before: PrecisionLevel
    precision_after: PrecisionLevel
    compression_ratio: float
    accuracy_impact: float
    optimization_time_seconds: float
    timestamp: datetime = field(default_factory=datetime.now)
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary."""
        return {
            "optimization_id": self.optimization_id,
            "optimization_type": self.optimization_type.value,
            "status": self.status.value,
            "metrics_before": self.metrics_before.to_dict(),
            "metrics_after": self.metrics_after.to_dict(),
            "precision_before": self.precision_before.value,
            "precision_after": self.precision_after.value,
            "compression_ratio": self.compression_ratio,
            "accuracy_impact": self.accuracy_impact,
            "optimization_time_seconds": self.optimization_time_seconds,
            "timestamp": self.timestamp.isoformat(),
            "error_message": self.error_message,
            "metadata": self.metadata,
        }
    
    def get_improvement_summary(self) -> Dict[str, float]:
        """Get summary of improvements."""
        return {
            "latency_improvement": (
                (self.metrics_before.latency_ms - self.metrics_after.latency_ms)
                / self.metrics_before.latency_ms * 100
                if self.metrics_before.latency_ms > 0 else 0
            ),
            "memory_reduction": (
                (self.metrics_before.memory_mb - self.metrics_after.memory_mb)
                / self.metrics_before.memory_mb * 100
                if self.metrics_before.memory_mb > 0 else 0
            ),
            "size_reduction": (
                (self.metrics_before.model_size_mb - self.metrics_after.model_size_mb)
                / self.metrics_before.model_size_mb * 100
                if self.metrics_before.model_size_mb > 0 else 0
            ),
            "throughput_improvement": (
                (self.metrics_after.throughput_qps - self.metrics_before.throughput_qps)
                / self.metrics_before.throughput_qps * 100
                if self.metrics_before.throughput_qps > 0 else 0
            ),
        }


class ModelOptimizer:
    """
    Main class for model optimization and quantization.
    
    Provides methods to optimize AI models using various techniques
    including quantization, pruning, distillation, and fine-tuning.
    """
    
    def __init__(
        self,
        model_id: str,
        default_precision: PrecisionLevel = PrecisionLevel.FP32,
        optimization_history: Optional[List[OptimizationResult]] = None,
    ):
        """
        Initialize the model optimizer.
        
        Args:
            model_id: Unique identifier for the model
            default_precision: Default precision level for the model
            optimization_history: Previous optimization results
        """
        self.model_id = model_id
        self.current_precision = default_precision
        self.optimization_history = optimization_history or []
        self._optimization_counter = 0
        self._model_metrics: Dict[str, ModelMetrics] = {}
        self._optimizers: Dict[OptimizationType, Callable] = {
            OptimizationType.QUANTIZATION: self._quantize,
            OptimizationType.PRUNING: self._prune,
            OptimizationType.DISTILLATION: self._distill,
            OptimizationType.FINE_TUNING: self._fine_tune,
        }
    
    def optimize(
        self,
        config: OptimizationConfig,
        current_metrics: Optional[ModelMetrics] = None,
    ) -> OptimizationResult:
        """
        Optimize the model using the specified configuration.
        
        Args:
            config: Optimization configuration
            current_metrics: Current model metrics (optional)
            
        Returns:
            OptimizationResult with before/after metrics
        """
        import time
        
        start_time = time.time()
        self._optimization_counter += 1
        optimization_id = f"{self.model_id}_opt_{self._optimization_counter}"
        
        # Get current metrics
        if current_metrics is None:
            current_metrics = self._get_current_metrics()
        
        precision_before = self.current_precision
        
        try:
            # Get the appropriate optimizer
            optimizer = self._optimizers.get(config.optimization_type)
            if optimizer is None:
                raise ValueError(f"Unknown optimization type: {config.optimization_type}")
            
            # Perform optimization
            optimized_metrics = optimizer(config, current_metrics)
            
            # Update precision if quantization
            if config.optimization_type == OptimizationType.QUANTIZATION:
                if config.target_precision:
                    self.current_precision = config.target_precision
            
            # Calculate results
            optimization_time = time.time() - start_time
            compression_ratio = self._calculate_compression_ratio(
                current_metrics, optimized_metrics
            )
            accuracy_impact = current_metrics.accuracy - optimized_metrics.accuracy
            
            result = OptimizationResult(
                optimization_id=optimization_id,
                optimization_type=config.optimization_type,
                status=OptimizationStatus.COMPLETED,
                metrics_before=current_metrics,
                metrics_after=optimized_metrics,
                precision_before=precision_before,
                precision_after=self.current_precision,
                compression_ratio=compression_ratio,
                accuracy_impact=accuracy_impact,
                optimization_time_seconds=optimization_time,
            )
            
            self.optimization_history.append(result)
            logger.info(f"Optimization {optimization_id} completed successfully")
            
            return result
            
        except Exception as e:
            logger.error(f"Optimization {optimization_id} failed: {e}")
            return OptimizationResult(
                optimization_id=optimization_id,
                optimization_type=config.optimization_type,
                status=OptimizationStatus.FAILED,
                metrics_before=current_metrics,
                metrics_after=ModelMetrics(),
                precision_before=precision_before,
                precision_after=self.current_precision,
                compression_ratio=0.0,
                accuracy_impact=0.0,
                optimization_time_seconds=time.time() - start_time,
                error_message=str(e),
            )
    
    def _quantize(
        self,
        config: OptimizationConfig,
        current_metrics: ModelMetrics,
    ) -> ModelMetrics:
        """
        Perform model quantization.
        
        Reduces precision of model weights and activations.
        """
        if config.target_precision is None:
            raise ValueError("Target precision must be specified for quantization")
        
        # Calculate size reduction based on precision
        precision_multipliers = {
            PrecisionLevel.FP32: 1.0,
            PrecisionLevel.FP16: 0.5,
            PrecisionLevel.INT8: 0.25,
            PrecisionLevel.INT4: 0.125,
        }
        
        size_multiplier = precision_multipliers.get(config.target_precision, 1.0)
        
        # Estimate accuracy impact
        accuracy_drop = self._estimate_accuracy_drop(config.target_precision)
        if accuracy_drop > config.max_accuracy_drop:
            logger.warning(
                f"Estimated accuracy drop {accuracy_drop:.4f} exceeds "
                f"max allowed {config.max_accuracy_drop:.4f}"
            )
        
        # Simulate optimization effects
        new_size = current_metrics.model_size_mb * size_multiplier
        new_memory = current_metrics.memory_mb * size_multiplier
        new_latency = current_metrics.latency_ms * (0.5 + 0.5 * size_multiplier)
        new_throughput = current_metrics.throughput_qps / size_multiplier
        
        return ModelMetrics(
            latency_ms=new_latency,
            throughput_qps=new_throughput,
            memory_mb=new_memory,
            model_size_mb=new_size,
            accuracy=current_metrics.accuracy - accuracy_drop,
            f1_score=current_metrics.f1_score - accuracy_drop * 0.5,
            perplexity=current_metrics.perplexity,
        )
    
    def _prune(
        self,
        config: OptimizationConfig,
        current_metrics: ModelMetrics,
    ) -> ModelMetrics:
        """
        Perform model pruning.
        
        Removes less important weights based on magnitude or gradient.
        """
        compression_ratio = config.compression_ratio
        
        # Estimate accuracy impact from pruning
        accuracy_drop = compression_ratio * 0.02  # 2% drop per 100% compression
        
        # Simulate pruning effects
        new_size = current_metrics.model_size_mb * (1 - compression_ratio)
        new_memory = current_metrics.memory_mb * (1 - compression_ratio)
        new_latency = current_metrics.latency_ms * (1 - compression_ratio * 0.3)
        
        return ModelMetrics(
            latency_ms=new_latency,
            throughput_qps=current_metrics.throughput_qps * (1 + compression_ratio * 0.5),
            memory_mb=new_memory,
            model_size_mb=new_size,
            accuracy=current_metrics.accuracy - accuracy_drop,
            f1_score=current_metrics.f1_score - accuracy_drop * 0.5,
            perplexity=current_metrics.perplexity,
        )
    
    def _distill(
        self,
        config: OptimizationConfig,
        current_metrics: ModelMetrics,
    ) -> ModelMetrics:
        """
        Perform knowledge distillation.
        
        Transfers knowledge from a larger teacher model to a smaller student model.
        """
        compression_ratio = config.compression_ratio
        
        # Distillation typically has smaller accuracy impact
        accuracy_drop = compression_ratio * 0.01  # 1% drop per 100% compression
        
        # Simulate distillation effects
        new_size = current_metrics.model_size_mb * (1 - compression_ratio)
        new_memory = current_metrics.memory_mb * (1 - compression_ratio)
        new_latency = current_metrics.latency_ms * (1 - compression_ratio * 0.5)
        
        return ModelMetrics(
            latency_ms=new_latency,
            throughput_qps=current_metrics.throughput_qps * (1 + compression_ratio * 0.8),
            memory_mb=new_memory,
            model_size_mb=new_size,
            accuracy=current_metrics.accuracy - accuracy_drop,
            f1_score=current_metrics.f1_score - accuracy_drop * 0.3,
            perplexity=current_metrics.perplexity,
        )
    
    def _fine_tune(
        self,
        config: OptimizationConfig,
        current_metrics: ModelMetrics,
    ) -> ModelMetrics:
        """
        Perform fine-tuning optimization.
        
        Adapts model to specific tasks or domains.
        """
        # Fine-tuning can improve accuracy but may increase size slightly
        accuracy_improvement = 0.01  # 1% accuracy improvement
        
        return ModelMetrics(
            latency_ms=current_metrics.latency_ms,
            throughput_qps=current_metrics.throughput_qps,
            memory_mb=current_metrics.memory_mb * 1.05,  # Slight increase
            model_size_mb=current_metrics.model_size_mb * 1.05,
            accuracy=current_metrics.accuracy + accuracy_improvement,
            f1_score=current_metrics.f1_score + accuracy_improvement * 0.8,
            perplexity=current_metrics.perplexity,
        )
    
    def _estimate_accuracy_drop(self, target_precision: PrecisionLevel) -> float:
        """Estimate accuracy drop from quantization."""
        drop_estimates = {
            PrecisionLevel.FP32: 0.0,
            PrecisionLevel.FP16: 0.005,  # 0.5%
            PrecisionLevel.INT8: 0.01,   # 1%
            PrecisionLevel.INT4: 0.03,   # 3%
        }
        return drop_estimates.get(target_precision, 0.0)
    
    def _calculate_compression_ratio(
        self,
        before: ModelMetrics,
        after: ModelMetrics,
    ) -> float:
        """Calculate the compression ratio."""
        if before.model_size_mb == 0:
            return 0.0
        return (before.model_size_mb - after.model_size_mb) / before.model_size_mb
    
    def _get_current_metrics(self) -> ModelMetrics:
        """Get current model metrics."""
        return self._model_metrics.get(
            self.model_id,
            ModelMetrics(
                latency_ms=100.0,
                throughput_qps=100.0,
                memory_mb=1000.0,
                model_size_mb=500.0,
                accuracy=0.95,
                f1_score=0.94,
            ),
        )
    
    def set_model_metrics(self, metrics: ModelMetrics) -> None:
        """Set the current model metrics."""
        self._model_metrics[self.model_id] = metrics
    
    def get_optimization_history(
        self,
        optimization_type: Optional[OptimizationType] = None,
        limit: int = 10,
    ) -> List[OptimizationResult]:
        """
        Get optimization history.
        
        Args:
            optimization_type: Filter by optimization type (optional)
            limit: Maximum number of results to return
            
        Returns:
            List of optimization results
        """
        history = self.optimization_history
        if optimization_type:
            history = [r for r in history if r.optimization_type == optimization_type]
        return history[-limit:]
    
    def get_best_optimization(self) -> Optional[OptimizationResult]:
        """Get the best optimization result based on accuracy/size tradeoff."""
        completed = [
            r for r in self.optimization_history
            if r.status == OptimizationStatus.COMPLETED
        ]
        if not completed:
            return None
        
        return max(
            completed,
            key=lambda r: (
                r.metrics_after.accuracy - r.accuracy_impact * 0.5,
                r.compression_ratio,
            ),
        )
    
    def supports_precision(self, precision: PrecisionLevel) -> bool:
        """Check if a precision level is supported."""
        return precision in PrecisionLevel
    
    def get_supported_optimizations(self) -> List[OptimizationType]:
        """Get list of supported optimization types."""
        return list(self._optimizers.keys())
    
    def export_history(self, filepath: str) -> None:
        """Export optimization history to a JSON file."""
        data = [r.to_dict() for r in self.optimization_history]
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2, default=str)
    
    def import_history(self, filepath: str) -> int:
        """
        Import optimization history from a JSON file.
        
        Returns:
            Number of records imported
        """
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        count = 0
        for item in data:
            result = OptimizationResult(
                optimization_id=item["optimization_id"],
                optimization_type=OptimizationType(item["optimization_type"]),
                status=OptimizationStatus(item["status"]),
                metrics_before=ModelMetrics.from_dict(item["metrics_before"]),
                metrics_after=ModelMetrics.from_dict(item["metrics_after"]),
                precision_before=PrecisionLevel(item["precision_before"]),
                precision_after=PrecisionLevel(item["precision_after"]),
                compression_ratio=item["compression_ratio"],
                accuracy_impact=item["accuracy_impact"],
                optimization_time_seconds=item["optimization_time_seconds"],
                timestamp=datetime.fromisoformat(item["timestamp"]),
                error_message=item.get("error_message"),
                metadata=item.get("metadata", {}),
            )
            self.optimization_history.append(result)
            count += 1
        
        return count
