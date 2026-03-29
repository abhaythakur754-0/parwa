"""
Model Compressor - Week 55 Advanced AI Optimization

Provides model compression techniques for AI models.
Supports weight pruning, knowledge distillation, and weight sharing.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Callable, Tuple
from datetime import datetime
import time
import logging
import json
from collections import defaultdict

logger = logging.getLogger(__name__)


class CompressionType(Enum):
    """Types of model compression techniques."""
    WEIGHT_PRUNING = "weight_pruning"
    KNOWLEDGE_DISTILLATION = "knowledge_distillation"
    WEIGHT_SHARING = "weight_sharing"


class CompressionStatus(Enum):
    """Status of compression process."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class PruningStrategy(Enum):
    """Strategies for weight pruning."""
    MAGNITUDE = "magnitude"
    GRADIENT = "gradient"
    RANDOM = "random"
    STRUCTURED = "structured"
    UNSTRUCTURED = "unstructured"


@dataclass
class LayerCompressionConfig:
    """Configuration for compressing a specific layer."""
    layer_name: str
    compression_ratio: float = 0.5
    pruning_strategy: PruningStrategy = PruningStrategy.MAGNITUDE
    min_parameters: int = 100
    importance_threshold: float = 0.01
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary."""
        return {
            "layer_name": self.layer_name,
            "compression_ratio": self.compression_ratio,
            "pruning_strategy": self.pruning_strategy.value,
            "min_parameters": self.min_parameters,
            "importance_threshold": self.importance_threshold,
        }


@dataclass
class CompressionConfig:
    """Configuration for model compression."""
    compression_type: CompressionType
    target_compression_ratio: float = 0.5
    max_accuracy_drop: float = 0.02
    layer_configs: List[LayerCompressionConfig] = field(default_factory=list)
    fine_tune_after: bool = True
    fine_tune_epochs: int = 5
    distillation_temperature: float = 2.0
    weight_sharing_clusters: int = 16
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary."""
        return {
            "compression_type": self.compression_type.value,
            "target_compression_ratio": self.target_compression_ratio,
            "max_accuracy_drop": self.max_accuracy_drop,
            "layer_configs": [c.to_dict() for c in self.layer_configs],
            "fine_tune_after": self.fine_tune_after,
            "fine_tune_epochs": self.fine_tune_epochs,
            "distillation_temperature": self.distillation_temperature,
            "weight_sharing_clusters": self.weight_sharing_clusters,
        }


@dataclass
class LayerCompressionResult:
    """Result of compressing a specific layer."""
    layer_name: str
    original_parameters: int
    compressed_parameters: int
    compression_ratio: float
    accuracy_impact: float
    execution_time_seconds: float
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary."""
        return {
            "layer_name": self.layer_name,
            "original_parameters": self.original_parameters,
            "compressed_parameters": self.compressed_parameters,
            "compression_ratio": self.compression_ratio,
            "accuracy_impact": self.accuracy_impact,
            "execution_time_seconds": self.execution_time_seconds,
        }


@dataclass
class CompressionResult:
    """Result of model compression."""
    compression_id: str
    compression_type: CompressionType
    status: CompressionStatus
    original_size_mb: float
    compressed_size_mb: float
    compression_ratio: float
    accuracy_before: float
    accuracy_after: float
    accuracy_impact: float
    layer_results: List[LayerCompressionResult] = field(default_factory=list)
    total_parameters_before: int = 0
    total_parameters_after: int = 0
    execution_time_seconds: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary."""
        return {
            "compression_id": self.compression_id,
            "compression_type": self.compression_type.value,
            "status": self.status.value,
            "original_size_mb": self.original_size_mb,
            "compressed_size_mb": self.compressed_size_mb,
            "compression_ratio": self.compression_ratio,
            "accuracy_before": self.accuracy_before,
            "accuracy_after": self.accuracy_after,
            "accuracy_impact": self.accuracy_impact,
            "layer_results": [r.to_dict() for r in self.layer_results],
            "total_parameters_before": self.total_parameters_before,
            "total_parameters_after": self.total_parameters_after,
            "execution_time_seconds": self.execution_time_seconds,
            "timestamp": self.timestamp.isoformat(),
            "error_message": self.error_message,
            "metadata": self.metadata,
        }
    
    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of the compression result."""
        return {
            "compression_ratio": f"{self.compression_ratio:.2%}",
            "size_reduction_mb": self.original_size_mb - self.compressed_size_mb,
            "accuracy_impact": f"{self.accuracy_impact:.2%}",
            "parameter_reduction": self.total_parameters_before - self.total_parameters_after,
            "layers_compressed": len(self.layer_results),
            "execution_time": f"{self.execution_time_seconds:.2f}s",
        }


@dataclass
class LayerInfo:
    """Information about a model layer."""
    name: str
    parameter_count: int
    shape: Tuple[int, ...]
    dtype: str = "float32"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert info to dictionary."""
        return {
            "name": self.name,
            "parameter_count": self.parameter_count,
            "shape": list(self.shape),
            "dtype": self.dtype,
        }


class ModelCompressor:
    """
    Main class for model compression.
    
    Provides methods to compress AI models using various techniques
    including weight pruning, knowledge distillation, and weight sharing.
    """
    
    def __init__(
        self,
        model_id: str,
        model_size_mb: float = 1000.0,
        model_accuracy: float = 0.95,
        layers: Optional[List[LayerInfo]] = None,
    ):
        """
        Initialize the model compressor.
        
        Args:
            model_id: Unique identifier for the model
            model_size_mb: Original model size in megabytes
            model_accuracy: Original model accuracy
            layers: Information about model layers
        """
        self.model_id = model_id
        self.original_size_mb = model_size_mb
        self.original_accuracy = model_accuracy
        self.layers = layers or self._get_default_layers()
        
        self._compression_counter = 0
        self._compression_history: List[CompressionResult] = []
        
        # Compression handlers
        self._compressors: Dict[CompressionType, Callable] = {
            CompressionType.WEIGHT_PRUNING: self._prune_weights,
            CompressionType.KNOWLEDGE_DISTILLATION: self._distill_knowledge,
            CompressionType.WEIGHT_SHARING: self._share_weights,
        }
    
    def compress(
        self,
        config: CompressionConfig,
    ) -> CompressionResult:
        """
        Compress the model using the specified configuration.
        
        Args:
            config: Compression configuration
            
        Returns:
            CompressionResult with before/after metrics
        """
        start_time = time.time()
        self._compression_counter += 1
        compression_id = f"{self.model_id}_comp_{self._compression_counter}"
        
        try:
            # Get the appropriate compressor
            compressor = self._compressors.get(config.compression_type)
            if compressor is None:
                raise ValueError(f"Unknown compression type: {config.compression_type}")
            
            # Perform compression
            compressed_size, accuracy_after, layer_results = compressor(config)
            
            # Calculate results
            execution_time = time.time() - start_time
            compression_ratio = (self.original_size_mb - compressed_size) / self.original_size_mb
            accuracy_impact = self.original_accuracy - accuracy_after
            
            result = CompressionResult(
                compression_id=compression_id,
                compression_type=config.compression_type,
                status=CompressionStatus.COMPLETED,
                original_size_mb=self.original_size_mb,
                compressed_size_mb=compressed_size,
                compression_ratio=compression_ratio,
                accuracy_before=self.original_accuracy,
                accuracy_after=accuracy_after,
                accuracy_impact=accuracy_impact,
                layer_results=layer_results,
                total_parameters_before=sum(l.parameter_count for l in self.layers),
                total_parameters_after=int(sum(l.parameter_count for l in self.layers) * (1 - compression_ratio)),
                execution_time_seconds=execution_time,
            )
            
            self._compression_history.append(result)
            logger.info(f"Compression {compression_id} completed successfully")
            
            return result
            
        except Exception as e:
            logger.error(f"Compression {compression_id} failed: {e}")
            return CompressionResult(
                compression_id=compression_id,
                compression_type=config.compression_type,
                status=CompressionStatus.FAILED,
                original_size_mb=self.original_size_mb,
                compressed_size_mb=self.original_size_mb,
                compression_ratio=0.0,
                accuracy_before=self.original_accuracy,
                accuracy_after=self.original_accuracy,
                accuracy_impact=0.0,
                execution_time_seconds=time.time() - start_time,
                error_message=str(e),
            )
    
    def _prune_weights(
        self,
        config: CompressionConfig,
    ) -> Tuple[float, float, List[LayerCompressionResult]]:
        """
        Perform weight pruning.
        
        Removes less important weights based on magnitude or gradient.
        """
        target_ratio = config.target_compression_ratio
        layer_results = []
        
        # Get layer-specific configs or use default
        layer_configs = config.layer_configs or [
            LayerCompressionConfig(
                layer_name=l.name,
                compression_ratio=target_ratio,
            )
            for l in self.layers
        ]
        
        for layer_config in layer_configs:
            layer_start = time.time()
            
            # Find the corresponding layer
            layer = next(
                (l for l in self.layers if l.name == layer_config.layer_name),
                None
            )
            if layer is None:
                continue
            
            # Calculate pruning impact
            # More aggressive pruning = more accuracy loss
            accuracy_impact = layer_config.compression_ratio * 0.02
            
            result = LayerCompressionResult(
                layer_name=layer.name,
                original_parameters=layer.parameter_count,
                compressed_parameters=int(layer.parameter_count * (1 - layer_config.compression_ratio)),
                compression_ratio=layer_config.compression_ratio,
                accuracy_impact=accuracy_impact,
                execution_time_seconds=time.time() - layer_start,
            )
            layer_results.append(result)
        
        # Calculate overall metrics
        total_compression = sum(r.compression_ratio for r in layer_results) / len(layer_results) if layer_results else 0
        compressed_size = self.original_size_mb * (1 - total_compression)
        accuracy_after = self.original_accuracy - sum(r.accuracy_impact for r in layer_results) / len(layer_results) if layer_results else self.original_accuracy
        
        # Fine-tuning can recover some accuracy
        if config.fine_tune_after:
            accuracy_after += 0.01  # Recover 1% from fine-tuning
        
        return compressed_size, accuracy_after, layer_results
    
    def _distill_knowledge(
        self,
        config: CompressionConfig,
    ) -> Tuple[float, float, List[LayerCompressionResult]]:
        """
        Perform knowledge distillation.
        
        Transfers knowledge from a larger teacher model to a smaller student model.
        """
        target_ratio = config.target_compression_ratio
        layer_results = []
        
        # Simulate distillation across layers
        for layer in self.layers:
            layer_start = time.time()
            
            # Distillation typically has less accuracy impact than pruning
            accuracy_impact = target_ratio * 0.01  # 1% drop per 100% compression
            
            result = LayerCompressionResult(
                layer_name=layer.name,
                original_parameters=layer.parameter_count,
                compressed_parameters=int(layer.parameter_count * (1 - target_ratio)),
                compression_ratio=target_ratio,
                accuracy_impact=accuracy_impact,
                execution_time_seconds=time.time() - layer_start,
            )
            layer_results.append(result)
        
        compressed_size = self.original_size_mb * (1 - target_ratio)
        accuracy_after = self.original_accuracy - target_ratio * 0.01
        
        # Temperature scaling affects accuracy
        accuracy_after += (config.distillation_temperature - 2.0) * 0.002
        
        return compressed_size, accuracy_after, layer_results
    
    def _share_weights(
        self,
        config: CompressionConfig,
    ) -> Tuple[float, float, List[LayerCompressionResult]]:
        """
        Perform weight sharing.
        
        Clusters weights to share values, reducing model size.
        """
        clusters = config.weight_sharing_clusters
        layer_results = []
        
        # Weight sharing compression ratio depends on cluster count
        # More clusters = less compression but better accuracy
        compression_ratio = 1 - (clusters / 256)  # 256 = 8-bit values
        
        for layer in self.layers:
            layer_start = time.time()
            
            # Weight sharing has minimal accuracy impact
            accuracy_impact = (1 - clusters / 256) * 0.005
            
            result = LayerCompressionResult(
                layer_name=layer.name,
                original_parameters=layer.parameter_count,
                compressed_parameters=int(layer.parameter_count * compression_ratio),
                compression_ratio=compression_ratio,
                accuracy_impact=accuracy_impact,
                execution_time_seconds=time.time() - layer_start,
            )
            layer_results.append(result)
        
        compressed_size = self.original_size_mb * compression_ratio
        accuracy_after = self.original_accuracy - sum(r.accuracy_impact for r in layer_results) / len(layer_results) if layer_results else self.original_accuracy
        
        return compressed_size, accuracy_after, layer_results
    
    def _get_default_layers(self) -> List[LayerInfo]:
        """Get default layer information for simulation."""
        return [
            LayerInfo(name="embedding", parameter_count=10000000, shape=(50000, 200)),
            LayerInfo(name="encoder_0", parameter_count=5000000, shape=(200, 200)),
            LayerInfo(name="encoder_1", parameter_count=5000000, shape=(200, 200)),
            LayerInfo(name="encoder_2", parameter_count=5000000, shape=(200, 200)),
            LayerInfo(name="decoder_0", parameter_count=5000000, shape=(200, 200)),
            LayerInfo(name="decoder_1", parameter_count=5000000, shape=(200, 200)),
            LayerInfo(name="output", parameter_count=10000000, shape=(200, 50000)),
        ]
    
    def get_layer_info(self, layer_name: str) -> Optional[LayerInfo]:
        """Get information about a specific layer."""
        return next((l for l in self.layers if l.name == layer_name), None)
    
    def get_compression_history(
        self,
        compression_type: Optional[CompressionType] = None,
        limit: int = 10,
    ) -> List[CompressionResult]:
        """
        Get compression history.
        
        Args:
            compression_type: Filter by compression type (optional)
            limit: Maximum number of results to return
            
        Returns:
            List of compression results
        """
        history = self._compression_history
        if compression_type:
            history = [r for r in history if r.compression_type == compression_type]
        return history[-limit:]
    
    def get_best_compression(self) -> Optional[CompressionResult]:
        """Get the best compression result based on accuracy/size tradeoff."""
        completed = [
            r for r in self._compression_history
            if r.status == CompressionStatus.COMPLETED
        ]
        if not completed:
            return None
        
        return max(
            completed,
            key=lambda r: (
                r.accuracy_after - r.accuracy_impact * 0.5,
                r.compression_ratio,
            ),
        )
    
    def get_supported_compressions(self) -> List[CompressionType]:
        """Get list of supported compression types."""
        return list(self._compressors.keys())
    
    def estimate_compression(
        self,
        config: CompressionConfig,
    ) -> Dict[str, Any]:
        """
        Estimate compression results without actually compressing.
        
        Args:
            config: Compression configuration
            
        Returns:
            Dictionary with estimated metrics
        """
        # Get base estimates from compression type
        if config.compression_type == CompressionType.WEIGHT_PRUNING:
            accuracy_impact = config.target_compression_ratio * 0.02
            size_reduction = config.target_compression_ratio
        elif config.compression_type == CompressionType.KNOWLEDGE_DISTILLATION:
            accuracy_impact = config.target_compression_ratio * 0.01
            size_reduction = config.target_compression_ratio
        elif config.compression_type == CompressionType.WEIGHT_SHARING:
            accuracy_impact = (1 - config.weight_sharing_clusters / 256) * 0.005
            size_reduction = 1 - (config.weight_sharing_clusters / 256)
        else:
            accuracy_impact = 0.0
            size_reduction = 0.0
        
        if config.fine_tune_after:
            accuracy_impact -= 0.01  # Fine-tuning helps
        
        return {
            "estimated_size_mb": self.original_size_mb * (1 - size_reduction),
            "estimated_accuracy": self.original_accuracy - accuracy_impact,
            "estimated_accuracy_impact": accuracy_impact,
            "estimated_compression_ratio": size_reduction,
            "within_tolerance": abs(accuracy_impact) <= config.max_accuracy_drop,
        }
    
    def create_layer_config(
        self,
        compression_ratio: float,
        strategy: PruningStrategy = PruningStrategy.MAGNITUDE,
    ) -> List[LayerCompressionConfig]:
        """Create layer-wise compression configs."""
        configs = []
        
        for layer in self.layers:
            # Adjust compression ratio based on layer type
            if "embedding" in layer.name or "output" in layer.name:
                # Less aggressive for embedding/output layers
                ratio = compression_ratio * 0.5
            else:
                ratio = compression_ratio
            
            configs.append(LayerCompressionConfig(
                layer_name=layer.name,
                compression_ratio=ratio,
                pruning_strategy=strategy,
            ))
        
        return configs
    
    def export_history(self, filepath: str) -> None:
        """Export compression history to a JSON file."""
        data = [r.to_dict() for r in self._compression_history]
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2, default=str)
    
    def import_history(self, filepath: str) -> int:
        """
        Import compression history from a JSON file.
        
        Returns:
            Number of records imported
        """
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        count = 0
        for item in data:
            layer_results = [
                LayerCompressionResult(
                    layer_name=lr["layer_name"],
                    original_parameters=lr["original_parameters"],
                    compressed_parameters=lr["compressed_parameters"],
                    compression_ratio=lr["compression_ratio"],
                    accuracy_impact=lr["accuracy_impact"],
                    execution_time_seconds=lr["execution_time_seconds"],
                )
                for lr in item.get("layer_results", [])
            ]
            
            result = CompressionResult(
                compression_id=item["compression_id"],
                compression_type=CompressionType(item["compression_type"]),
                status=CompressionStatus(item["status"]),
                original_size_mb=item["original_size_mb"],
                compressed_size_mb=item["compressed_size_mb"],
                compression_ratio=item["compression_ratio"],
                accuracy_before=item["accuracy_before"],
                accuracy_after=item["accuracy_after"],
                accuracy_impact=item["accuracy_impact"],
                layer_results=layer_results,
                total_parameters_before=item.get("total_parameters_before", 0),
                total_parameters_after=item.get("total_parameters_after", 0),
                execution_time_seconds=item["execution_time_seconds"],
                timestamp=datetime.fromisoformat(item["timestamp"]),
                error_message=item.get("error_message"),
                metadata=item.get("metadata", {}),
            )
            self._compression_history.append(result)
            count += 1
        
        return count
    
    def get_stats(self) -> Dict[str, Any]:
        """Get compressor statistics."""
        return {
            "model_id": self.model_id,
            "original_size_mb": self.original_size_mb,
            "original_accuracy": self.original_accuracy,
            "layer_count": len(self.layers),
            "total_compressions": len(self._compression_history),
            "successful_compressions": len([
                r for r in self._compression_history
                if r.status == CompressionStatus.COMPLETED
            ]),
            "best_compression_ratio": max(
                (r.compression_ratio for r in self._compression_history
                 if r.status == CompressionStatus.COMPLETED),
                default=0.0,
            ),
        }
