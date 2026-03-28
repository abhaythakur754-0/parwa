"""
Tests for Week 55 Advanced AI Optimization - Model Optimizer Module

Tests cover:
- ModelOptimizer (model_optimizer.py)
- InferenceAccelerator (inference_accelerator.py)
- ModelCompressor (model_compressor.py)
"""

import pytest
import tempfile
import os
import time
from datetime import datetime
from unittest.mock import Mock, patch

# Model Optimizer imports
from enterprise.ai_optimization.model_optimizer import (
    ModelOptimizer,
    OptimizationType,
    PrecisionLevel,
    OptimizationStatus,
    ModelMetrics,
    OptimizationConfig,
    OptimizationResult,
)

# Inference Accelerator imports
from enterprise.ai_optimization.inference_accelerator import (
    InferenceAccelerator,
    AccelerationMethod,
    AccelerationStatus,
    InferenceConfig,
    InferenceRequest,
    InferenceResult,
    BenchmarkResult,
)

# Model Compressor imports
from enterprise.ai_optimization.model_compressor import (
    ModelCompressor,
    CompressionType,
    CompressionStatus,
    PruningStrategy,
    LayerCompressionConfig,
    CompressionConfig,
    CompressionResult,
    LayerCompressionResult,
    LayerInfo,
)


# ============================================================================
# Model Optimizer Tests
# ============================================================================

class TestOptimizationType:
    """Tests for OptimizationType enum."""
    
    def test_optimization_types_exist(self):
        """Test that all required optimization types exist."""
        assert OptimizationType.QUANTIZATION.value == "quantization"
        assert OptimizationType.PRUNING.value == "pruning"
        assert OptimizationType.DISTILLATION.value == "distillation"
        assert OptimizationType.FINE_TUNING.value == "fine_tuning"
    
    def test_optimization_type_count(self):
        """Test that we have exactly 4 optimization types."""
        assert len(OptimizationType) == 4


class TestPrecisionLevel:
    """Tests for PrecisionLevel enum."""
    
    def test_precision_levels_exist(self):
        """Test that all required precision levels exist."""
        assert PrecisionLevel.FP32.value == "fp32"
        assert PrecisionLevel.FP16.value == "fp16"
        assert PrecisionLevel.INT8.value == "int8"
        assert PrecisionLevel.INT4.value == "int4"
    
    def test_precision_level_count(self):
        """Test that we have exactly 4 precision levels."""
        assert len(PrecisionLevel) == 4


class TestModelMetrics:
    """Tests for ModelMetrics dataclass."""
    
    def test_model_metrics_creation(self):
        """Test creating ModelMetrics with default values."""
        metrics = ModelMetrics()
        assert metrics.latency_ms == 0.0
        assert metrics.throughput_qps == 0.0
        assert metrics.memory_mb == 0.0
        assert metrics.model_size_mb == 0.0
        assert metrics.accuracy == 0.0
        assert metrics.f1_score == 0.0
        assert metrics.perplexity is None
    
    def test_model_metrics_to_dict(self):
        """Test converting ModelMetrics to dictionary."""
        metrics = ModelMetrics(
            latency_ms=100.0,
            throughput_qps=50.0,
            memory_mb=1000.0,
            model_size_mb=500.0,
            accuracy=0.95,
            f1_score=0.94,
            perplexity=10.5,
        )
        data = metrics.to_dict()
        
        assert data["latency_ms"] == 100.0
        assert data["throughput_qps"] == 50.0
        assert data["accuracy"] == 0.95
        assert data["perplexity"] == 10.5
    
    def test_model_metrics_from_dict(self):
        """Test creating ModelMetrics from dictionary."""
        data = {
            "latency_ms": 50.0,
            "throughput_qps": 100.0,
            "memory_mb": 500.0,
            "model_size_mb": 250.0,
            "accuracy": 0.92,
            "f1_score": 0.90,
            "perplexity": 15.0,
        }
        metrics = ModelMetrics.from_dict(data)
        
        assert metrics.latency_ms == 50.0
        assert metrics.throughput_qps == 100.0
        assert metrics.accuracy == 0.92


class TestOptimizationResult:
    """Tests for OptimizationResult dataclass."""
    
    def test_optimization_result_creation(self):
        """Test creating OptimizationResult."""
        result = OptimizationResult(
            optimization_id="test_opt_1",
            optimization_type=OptimizationType.QUANTIZATION,
            status=OptimizationStatus.COMPLETED,
            metrics_before=ModelMetrics(accuracy=0.95),
            metrics_after=ModelMetrics(accuracy=0.94),
            precision_before=PrecisionLevel.FP32,
            precision_after=PrecisionLevel.INT8,
            compression_ratio=0.75,
            accuracy_impact=0.01,
            optimization_time_seconds=10.5,
        )
        
        assert result.optimization_id == "test_opt_1"
        assert result.optimization_type == OptimizationType.QUANTIZATION
        assert result.compression_ratio == 0.75
    
    def test_optimization_result_get_improvement_summary(self):
        """Test getting improvement summary."""
        result = OptimizationResult(
            optimization_id="test_opt_1",
            optimization_type=OptimizationType.QUANTIZATION,
            status=OptimizationStatus.COMPLETED,
            metrics_before=ModelMetrics(
                latency_ms=100.0,
                throughput_qps=100.0,
                memory_mb=1000.0,
                model_size_mb=500.0,
            ),
            metrics_after=ModelMetrics(
                latency_ms=50.0,
                throughput_qps=200.0,
                memory_mb=250.0,
                model_size_mb=125.0,
            ),
            precision_before=PrecisionLevel.FP32,
            precision_after=PrecisionLevel.INT8,
            compression_ratio=0.75,
            accuracy_impact=0.01,
            optimization_time_seconds=10.5,
        )
        
        summary = result.get_improvement_summary()
        
        assert summary["latency_improvement"] == 50.0  # 50% improvement
        assert summary["memory_reduction"] == 75.0  # 75% reduction
        assert summary["size_reduction"] == 75.0  # 75% reduction
        assert summary["throughput_improvement"] == 100.0  # 100% improvement


class TestModelOptimizer:
    """Tests for ModelOptimizer class."""
    
    def test_model_optimizer_creation(self):
        """Test creating a ModelOptimizer."""
        optimizer = ModelOptimizer("test_model")
        assert optimizer.model_id == "test_model"
        assert optimizer.current_precision == PrecisionLevel.FP32
        assert len(optimizer.optimization_history) == 0
    
    def test_model_optimizer_optimize_quantization(self):
        """Test quantization optimization."""
        optimizer = ModelOptimizer("test_model")
        config = OptimizationConfig(
            optimization_type=OptimizationType.QUANTIZATION,
            target_precision=PrecisionLevel.INT8,
        )
        metrics = ModelMetrics(
            latency_ms=100.0,
            throughput_qps=100.0,
            memory_mb=1000.0,
            model_size_mb=500.0,
            accuracy=0.95,
            f1_score=0.94,
        )
        
        result = optimizer.optimize(config, metrics)
        
        assert result.status == OptimizationStatus.COMPLETED
        assert result.precision_after == PrecisionLevel.INT8
        assert result.metrics_after.model_size_mb < result.metrics_before.model_size_mb
    
    def test_model_optimizer_optimize_pruning(self):
        """Test pruning optimization."""
        optimizer = ModelOptimizer("test_model")
        config = OptimizationConfig(
            optimization_type=OptimizationType.PRUNING,
            compression_ratio=0.5,
        )
        metrics = ModelMetrics(
            latency_ms=100.0,
            throughput_qps=100.0,
            memory_mb=1000.0,
            model_size_mb=500.0,
            accuracy=0.95,
        )
        
        result = optimizer.optimize(config, metrics)
        
        assert result.status == OptimizationStatus.COMPLETED
        assert result.compression_ratio > 0
        assert result.metrics_after.model_size_mb < result.metrics_before.model_size_mb
    
    def test_model_optimizer_optimize_distillation(self):
        """Test distillation optimization."""
        optimizer = ModelOptimizer("test_model")
        config = OptimizationConfig(
            optimization_type=OptimizationType.DISTILLATION,
            compression_ratio=0.5,
        )
        metrics = ModelMetrics(
            latency_ms=100.0,
            throughput_qps=100.0,
            memory_mb=1000.0,
            model_size_mb=500.0,
            accuracy=0.95,
        )
        
        result = optimizer.optimize(config, metrics)
        
        assert result.status == OptimizationStatus.COMPLETED
        assert result.metrics_after.model_size_mb < result.metrics_before.model_size_mb
    
    def test_model_optimizer_optimize_fine_tuning(self):
        """Test fine-tuning optimization."""
        optimizer = ModelOptimizer("test_model")
        config = OptimizationConfig(
            optimization_type=OptimizationType.FINE_TUNING,
        )
        metrics = ModelMetrics(
            latency_ms=100.0,
            throughput_qps=100.0,
            memory_mb=1000.0,
            model_size_mb=500.0,
            accuracy=0.95,
        )
        
        result = optimizer.optimize(config, metrics)
        
        assert result.status == OptimizationStatus.COMPLETED
        # Fine-tuning can improve accuracy
        assert result.metrics_after.accuracy >= result.metrics_before.accuracy
    
    def test_model_optimizer_history(self):
        """Test optimization history tracking."""
        optimizer = ModelOptimizer("test_model")
        
        # Run multiple optimizations
        for opt_type in OptimizationType:
            config = OptimizationConfig(optimization_type=opt_type)
            if opt_type == OptimizationType.QUANTIZATION:
                config.target_precision = PrecisionLevel.INT8
            optimizer.optimize(config)
        
        history = optimizer.get_optimization_history()
        assert len(history) == 4
    
    def test_model_optimizer_supports_precision(self):
        """Test precision support checking."""
        optimizer = ModelOptimizer("test_model")
        
        assert optimizer.supports_precision(PrecisionLevel.FP32)
        assert optimizer.supports_precision(PrecisionLevel.FP16)
        assert optimizer.supports_precision(PrecisionLevel.INT8)
        assert optimizer.supports_precision(PrecisionLevel.INT4)


# ============================================================================
# Inference Accelerator Tests
# ============================================================================

class TestAccelerationMethod:
    """Tests for AccelerationMethod enum."""
    
    def test_acceleration_methods_exist(self):
        """Test that all required acceleration methods exist."""
        assert AccelerationMethod.BATCHING.value == "batching"
        assert AccelerationMethod.CACHING.value == "caching"
        assert AccelerationMethod.SPECULATIVE.value == "speculative"
        assert AccelerationMethod.PARALLEL.value == "parallel"
    
    def test_acceleration_method_count(self):
        """Test that we have exactly 4 acceleration methods."""
        assert len(AccelerationMethod) == 4


class TestInferenceConfig:
    """Tests for InferenceConfig dataclass."""
    
    def test_inference_config_creation(self):
        """Test creating InferenceConfig with default values."""
        config = InferenceConfig()
        assert config.batch_size == 32
        assert config.max_batch_size == 128
        assert config.enable_caching is True
        assert config.cache_ttl_seconds == 3600.0
    
    def test_inference_config_to_dict(self):
        """Test converting InferenceConfig to dictionary."""
        config = InferenceConfig(
            batch_size=64,
            max_batch_size=256,
            enable_caching=False,
        )
        data = config.to_dict()
        
        assert data["batch_size"] == 64
        assert data["max_batch_size"] == 256
        assert data["enable_caching"] is False
    
    def test_inference_config_from_dict(self):
        """Test creating InferenceConfig from dictionary."""
        data = {
            "batch_size": 128,
            "max_batch_size": 512,
            "batch_timeout_ms": 20.0,
        }
        config = InferenceConfig.from_dict(data)
        
        assert config.batch_size == 128
        assert config.max_batch_size == 512
        assert config.batch_timeout_ms == 20.0


class TestInferenceRequest:
    """Tests for InferenceRequest dataclass."""
    
    def test_inference_request_creation(self):
        """Test creating InferenceRequest."""
        request = InferenceRequest(
            request_id="req_001",
            input_data="test input",
            priority=1,
        )
        
        assert request.request_id == "req_001"
        assert request.input_data == "test input"
        assert request.priority == 1
    
    def test_inference_request_to_dict(self):
        """Test converting InferenceRequest to dictionary."""
        request = InferenceRequest(
            request_id="req_001",
            input_data="test input",
        )
        data = request.to_dict()
        
        assert data["request_id"] == "req_001"
        assert "test input" in data["input_data"]


class TestInferenceAccelerator:
    """Tests for InferenceAccelerator class."""
    
    def test_inference_accelerator_creation(self):
        """Test creating an InferenceAccelerator."""
        accelerator = InferenceAccelerator("test_model")
        assert accelerator.model_id == "test_model"
        assert accelerator.status == AccelerationStatus.IDLE
    
    def test_inference_accelerator_accelerate_batching(self):
        """Test batching acceleration method."""
        accelerator = InferenceAccelerator("test_model")
        request = InferenceRequest(
            request_id="req_001",
            input_data="test input",
        )
        
        result = accelerator.accelerate(request, AccelerationMethod.BATCHING)
        
        assert result.request_id == "req_001"
        assert result.error_message is None
        assert result.latency_ms > 0
    
    def test_inference_accelerator_accelerate_caching(self):
        """Test caching acceleration method."""
        accelerator = InferenceAccelerator("test_model")
        request = InferenceRequest(
            request_id="req_001",
            input_data="test input",
        )
        
        # First request - cache miss
        result1 = accelerator.accelerate(request, AccelerationMethod.CACHING)
        assert result1.cached is False
        
        # Second identical request - cache hit
        result2 = accelerator.accelerate(request, AccelerationMethod.CACHING)
        assert result2.cached is True
    
    def test_inference_accelerator_accelerate_speculative(self):
        """Test speculative acceleration method."""
        accelerator = InferenceAccelerator("test_model")
        request = InferenceRequest(
            request_id="req_001",
            input_data="test input",
        )
        
        result = accelerator.accelerate(request, AccelerationMethod.SPECULATIVE)
        
        assert result.request_id == "req_001"
        assert result.error_message is None
        assert "speculative_tokens" in result.metadata
    
    def test_inference_accelerator_accelerate_parallel(self):
        """Test parallel acceleration method."""
        accelerator = InferenceAccelerator("test_model")
        request = InferenceRequest(
            request_id="req_001",
            input_data="test input",
        )
        
        result = accelerator.accelerate(request, AccelerationMethod.PARALLEL)
        
        assert result.request_id == "req_001"
        assert result.error_message is None
        assert "parallel_workers" in result.metadata
    
    def test_inference_accelerator_benchmark(self):
        """Test benchmarking functionality."""
        accelerator = InferenceAccelerator("test_model")
        requests = [
            InferenceRequest(request_id=f"req_{i}", input_data=f"input_{i}")
            for i in range(10)
        ]
        
        result = accelerator.benchmark(requests, AccelerationMethod.BATCHING)
        
        assert result.total_requests == 10
        assert result.successful_requests == 10
        assert result.throughput_qps > 0
    
    def test_inference_accelerator_clear_cache(self):
        """Test clearing the cache."""
        accelerator = InferenceAccelerator("test_model")
        request = InferenceRequest(
            request_id="req_001",
            input_data="test input",
        )
        
        # Add to cache
        accelerator.accelerate(request, AccelerationMethod.CACHING)
        
        # Clear cache
        count = accelerator.clear_cache()
        assert count >= 1
    
    def test_inference_accelerator_get_stats(self):
        """Test getting accelerator statistics."""
        accelerator = InferenceAccelerator("test_model")
        
        stats = accelerator.get_stats()
        
        assert stats["model_id"] == "test_model"
        assert stats["status"] == "idle"


# ============================================================================
# Model Compressor Tests
# ============================================================================

class TestCompressionType:
    """Tests for CompressionType enum."""
    
    def test_compression_types_exist(self):
        """Test that all required compression types exist."""
        assert CompressionType.WEIGHT_PRUNING.value == "weight_pruning"
        assert CompressionType.KNOWLEDGE_DISTILLATION.value == "knowledge_distillation"
        assert CompressionType.WEIGHT_SHARING.value == "weight_sharing"
    
    def test_compression_type_count(self):
        """Test that we have exactly 3 compression types."""
        assert len(CompressionType) == 3


class TestPruningStrategy:
    """Tests for PruningStrategy enum."""
    
    def test_pruning_strategies_exist(self):
        """Test that all required pruning strategies exist."""
        assert PruningStrategy.MAGNITUDE.value == "magnitude"
        assert PruningStrategy.GRADIENT.value == "gradient"
        assert PruningStrategy.RANDOM.value == "random"
        assert PruningStrategy.STRUCTURED.value == "structured"
        assert PruningStrategy.UNSTRUCTURED.value == "unstructured"


class TestCompressionConfig:
    """Tests for CompressionConfig dataclass."""
    
    def test_compression_config_creation(self):
        """Test creating CompressionConfig."""
        config = CompressionConfig(
            compression_type=CompressionType.WEIGHT_PRUNING,
            target_compression_ratio=0.5,
            max_accuracy_drop=0.02,
        )
        
        assert config.compression_type == CompressionType.WEIGHT_PRUNING
        assert config.target_compression_ratio == 0.5
        assert config.max_accuracy_drop == 0.02
    
    def test_compression_config_to_dict(self):
        """Test converting CompressionConfig to dictionary."""
        config = CompressionConfig(
            compression_type=CompressionType.KNOWLEDGE_DISTILLATION,
            target_compression_ratio=0.7,
            fine_tune_after=True,
            fine_tune_epochs=10,
        )
        data = config.to_dict()
        
        assert data["compression_type"] == "knowledge_distillation"
        assert data["target_compression_ratio"] == 0.7
        assert data["fine_tune_after"] is True


class TestCompressionResult:
    """Tests for CompressionResult dataclass."""
    
    def test_compression_result_creation(self):
        """Test creating CompressionResult."""
        result = CompressionResult(
            compression_id="comp_001",
            compression_type=CompressionType.WEIGHT_PRUNING,
            status=CompressionStatus.COMPLETED,
            original_size_mb=1000.0,
            compressed_size_mb=500.0,
            compression_ratio=0.5,
            accuracy_before=0.95,
            accuracy_after=0.94,
            accuracy_impact=0.01,
        )
        
        assert result.compression_id == "comp_001"
        assert result.compression_ratio == 0.5
        assert result.accuracy_impact == 0.01
    
    def test_compression_result_get_summary(self):
        """Test getting compression summary."""
        result = CompressionResult(
            compression_id="comp_001",
            compression_type=CompressionType.WEIGHT_PRUNING,
            status=CompressionStatus.COMPLETED,
            original_size_mb=1000.0,
            compressed_size_mb=500.0,
            compression_ratio=0.5,
            accuracy_before=0.95,
            accuracy_after=0.94,
            accuracy_impact=0.01,
            total_parameters_before=1000000,
            total_parameters_after=500000,
            execution_time_seconds=10.5,
        )
        
        summary = result.get_summary()
        
        assert "50.00%" in summary["compression_ratio"]
        assert summary["size_reduction_mb"] == 500.0


class TestModelCompressor:
    """Tests for ModelCompressor class."""
    
    def test_model_compressor_creation(self):
        """Test creating a ModelCompressor."""
        compressor = ModelCompressor("test_model")
        assert compressor.model_id == "test_model"
        assert len(compressor.layers) > 0
    
    def test_model_compressor_compress_weight_pruning(self):
        """Test weight pruning compression."""
        compressor = ModelCompressor(
            "test_model",
            model_size_mb=1000.0,
            model_accuracy=0.95,
        )
        config = CompressionConfig(
            compression_type=CompressionType.WEIGHT_PRUNING,
            target_compression_ratio=0.5,
        )
        
        result = compressor.compress(config)
        
        assert result.status == CompressionStatus.COMPLETED
        assert result.compressed_size_mb < result.original_size_mb
        assert len(result.layer_results) > 0
    
    def test_model_compressor_compress_knowledge_distillation(self):
        """Test knowledge distillation compression."""
        compressor = ModelCompressor(
            "test_model",
            model_size_mb=1000.0,
            model_accuracy=0.95,
        )
        config = CompressionConfig(
            compression_type=CompressionType.KNOWLEDGE_DISTILLATION,
            target_compression_ratio=0.5,
            distillation_temperature=3.0,
        )
        
        result = compressor.compress(config)
        
        assert result.status == CompressionStatus.COMPLETED
        assert result.compressed_size_mb < result.original_size_mb
    
    def test_model_compressor_compress_weight_sharing(self):
        """Test weight sharing compression."""
        compressor = ModelCompressor(
            "test_model",
            model_size_mb=1000.0,
            model_accuracy=0.95,
        )
        config = CompressionConfig(
            compression_type=CompressionType.WEIGHT_SHARING,
            weight_sharing_clusters=32,
        )
        
        result = compressor.compress(config)
        
        assert result.status == CompressionStatus.COMPLETED
        assert result.compressed_size_mb < result.original_size_mb
    
    def test_model_compressor_estimate_compression(self):
        """Test compression estimation."""
        compressor = ModelCompressor(
            "test_model",
            model_size_mb=1000.0,
            model_accuracy=0.95,
        )
        config = CompressionConfig(
            compression_type=CompressionType.WEIGHT_PRUNING,
            target_compression_ratio=0.5,
        )
        
        estimate = compressor.estimate_compression(config)
        
        assert "estimated_size_mb" in estimate
        assert "estimated_accuracy" in estimate
        assert "within_tolerance" in estimate
    
    def test_model_compressor_create_layer_config(self):
        """Test creating layer-wise compression configs."""
        compressor = ModelCompressor("test_model")
        
        configs = compressor.create_layer_config(
            compression_ratio=0.5,
            strategy=PruningStrategy.MAGNITUDE,
        )
        
        assert len(configs) == len(compressor.layers)
        for cfg in configs:
            assert cfg.compression_ratio >= 0
            assert cfg.pruning_strategy == PruningStrategy.MAGNITUDE
    
    def test_model_compressor_get_stats(self):
        """Test getting compressor statistics."""
        compressor = ModelCompressor(
            "test_model",
            model_size_mb=1000.0,
            model_accuracy=0.95,
        )
        
        # Run a compression
        config = CompressionConfig(
            compression_type=CompressionType.WEIGHT_PRUNING,
            target_compression_ratio=0.5,
        )
        compressor.compress(config)
        
        stats = compressor.get_stats()
        
        assert stats["model_id"] == "test_model"
        assert stats["total_compressions"] == 1
        assert stats["successful_compressions"] == 1


# ============================================================================
# Integration Tests
# ============================================================================

class TestIntegration:
    """Integration tests across all modules."""
    
    def test_optimization_to_compression_workflow(self):
        """Test workflow from optimization to compression."""
        # Step 1: Optimize the model
        optimizer = ModelOptimizer("workflow_model")
        opt_config = OptimizationConfig(
            optimization_type=OptimizationType.QUANTIZATION,
            target_precision=PrecisionLevel.INT8,
        )
        opt_result = optimizer.optimize(opt_config)
        
        assert opt_result.status == OptimizationStatus.COMPLETED
        
        # Step 2: Compress the optimized model
        compressor = ModelCompressor(
            "workflow_model",
            model_size_mb=opt_result.metrics_after.model_size_mb,
            model_accuracy=opt_result.metrics_after.accuracy,
        )
        comp_config = CompressionConfig(
            compression_type=CompressionType.WEIGHT_PRUNING,
            target_compression_ratio=0.3,
        )
        comp_result = compressor.compress(comp_config)
        
        assert comp_result.status == CompressionStatus.COMPLETED
    
    def test_acceleration_with_optimized_model(self):
        """Test inference acceleration with optimized model."""
        # Create accelerator
        accelerator = InferenceAccelerator(
            "optimized_model",
            config=InferenceConfig(
                batch_size=16,
                enable_caching=True,
            ),
        )
        
        # Process requests
        requests = [
            InferenceRequest(request_id=f"req_{i}", input_data=f"input_{i}")
            for i in range(5)
        ]
        
        # Compare different acceleration methods
        results = accelerator.compare_methods(requests)
        
        assert len(results) == 4  # All 4 methods
        for method, result in results.items():
            assert result.successful_requests > 0
    
    def test_full_optimization_pipeline(self):
        """Test full optimization pipeline."""
        model_id = "pipeline_model"
        
        # Step 1: Quantize
        optimizer = ModelOptimizer(model_id)
        quant_result = optimizer.optimize(
            OptimizationConfig(
                optimization_type=OptimizationType.QUANTIZATION,
                target_precision=PrecisionLevel.INT8,
            )
        )
        assert quant_result.status == OptimizationStatus.COMPLETED
        
        # Step 2: Prune
        prune_result = optimizer.optimize(
            OptimizationConfig(
                optimization_type=OptimizationType.PRUNING,
                compression_ratio=0.3,
            )
        )
        assert prune_result.status == OptimizationStatus.COMPLETED
        
        # Step 3: Fine-tune
        ft_result = optimizer.optimize(
            OptimizationConfig(
                optimization_type=OptimizationType.FINE_TUNING,
            )
        )
        assert ft_result.status == OptimizationStatus.COMPLETED
        
        # Check history
        history = optimizer.get_optimization_history()
        assert len(history) == 3


# ============================================================================
# Edge Case Tests
# ============================================================================

class TestEdgeCases:
    """Tests for edge cases and error handling."""
    
    def test_model_optimizer_zero_metrics(self):
        """Test optimization with zero metrics."""
        optimizer = ModelOptimizer("test_model")
        config = OptimizationConfig(
            optimization_type=OptimizationType.QUANTIZATION,
            target_precision=PrecisionLevel.INT8,
        )
        metrics = ModelMetrics()  # All zeros
        
        result = optimizer.optimize(config, metrics)
        
        assert result.status == OptimizationStatus.COMPLETED
    
    def test_model_compressor_empty_layers(self):
        """Test compression with empty layer list."""
        compressor = ModelCompressor(
            "test_model",
            layers=[],
        )
        config = CompressionConfig(
            compression_type=CompressionType.WEIGHT_PRUNING,
        )
        
        result = compressor.compress(config)
        
        # Should handle gracefully
        assert result.status == CompressionStatus.COMPLETED
    
    def test_inference_accelerator_cache_expiry(self):
        """Test cache expiry."""
        config = InferenceConfig(
            cache_ttl_seconds=0.1,  # Very short TTL
        )
        accelerator = InferenceAccelerator("test_model", config=config)
        request = InferenceRequest(
            request_id="req_001",
            input_data="test input",
        )
        
        # First request - cache miss
        result1 = accelerator.accelerate(request, AccelerationMethod.CACHING)
        assert result1.cached is False
        
        # Wait for cache to expire
        time.sleep(0.2)
        
        # Second request - should be cache miss due to expiry
        result2 = accelerator.accelerate(request, AccelerationMethod.CACHING)
        assert result2.cached is False
    
    def test_benchmark_empty_requests(self):
        """Test benchmarking with no requests."""
        accelerator = InferenceAccelerator("test_model")
        
        result = accelerator.benchmark([], AccelerationMethod.BATCHING)
        
        assert result.total_requests == 0
        assert result.avg_latency_ms == 0.0
