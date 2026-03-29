"""Tests for Context Manager Module - Week 55, Builder 4"""
import pytest
from datetime import datetime

from enterprise.ai_optimization.context_optimizer import (
    ContextOptimizer, ContextWindow, OptimizationStrategy
)
from enterprise.ai_optimization.memory_manager import (
    AIMemoryManager, MemoryBlock, MemoryPool, MemoryPriority
)
from enterprise.ai_optimization.context_compressor import (
    ContextCompressor, CompressionResult, CompressionMethod
)


class TestContextOptimizer:
    def test_init(self):
        optimizer = ContextOptimizer()
        assert optimizer.default_max_tokens == 4096
        assert optimizer.strategy == OptimizationStrategy.TRUNCATION

    def test_optimize_under_limit(self):
        optimizer = ContextOptimizer(max_tokens=1000)
        content = ["Short content"]
        window = optimizer.optimize(content)
        assert len(window.content) == 1

    def test_optimize_truncation(self):
        optimizer = ContextOptimizer(max_tokens=10, strategy=OptimizationStrategy.TRUNCATION)
        content = ["A" * 100, "B" * 100]
        window = optimizer.optimize(content)
        assert window.current_tokens <= window.max_tokens

    def test_optimize_summarization(self):
        optimizer = ContextOptimizer(max_tokens=10, strategy=OptimizationStrategy.SUMMARIZATION)
        content = ["Long content here", "More content"]
        window = optimizer.optimize(content)
        assert window.current_tokens <= window.max_tokens

    def test_optimize_prioritization(self):
        optimizer = ContextOptimizer(max_tokens=10, strategy=OptimizationStrategy.PRIORITIZATION)
        content = ["Long content", "Short"]
        window = optimizer.optimize(content)
        assert window.current_tokens <= window.max_tokens

    def test_count_tokens(self):
        optimizer = ContextOptimizer()
        count = optimizer.count_tokens("test content")
        assert count > 0

    def test_set_strategy(self):
        optimizer = ContextOptimizer()
        optimizer.set_strategy(OptimizationStrategy.SUMMARIZATION)
        assert optimizer.strategy == OptimizationStrategy.SUMMARIZATION


class TestContextWindow:
    def test_init(self):
        window = ContextWindow()
        assert window.max_tokens == 4096
        assert window.current_tokens == 0

    def test_available_tokens(self):
        window = ContextWindow(max_tokens=100, current_tokens=30)
        assert window.available_tokens == 70

    def test_utilization(self):
        window = ContextWindow(max_tokens=100, current_tokens=50)
        assert window.utilization == 0.5


class TestAIMemoryManager:
    def test_init(self):
        manager = AIMemoryManager()
        assert "default" in manager.pools

    def test_allocate(self):
        manager = AIMemoryManager()
        block = manager.allocate("test_block", 100, "test usage")
        assert block is not None
        assert block.id == "test_block"

    def test_deallocate(self):
        manager = AIMemoryManager()
        manager.allocate("test_block", 100)
        result = manager.deallocate("test_block")
        assert result

    def test_get(self):
        manager = AIMemoryManager()
        manager.allocate("test_block", 100, data="test_data")
        block = manager.get("test_block")
        assert block is not None
        assert block.data == "test_data"

    def test_create_pool(self):
        manager = AIMemoryManager()
        manager.create_pool("custom", 2048)
        assert "custom" in manager.pools

    def test_remove_pool(self):
        manager = AIMemoryManager()
        manager.create_pool("custom", 2048)
        assert manager.remove_pool("custom")
        assert "custom" not in manager.pools

    def test_remove_default_pool_fails(self):
        manager = AIMemoryManager()
        assert not manager.remove_pool("default")

    def test_gc(self):
        manager = AIMemoryManager()
        manager.allocate("low_block", 100, priority=MemoryPriority.LOW)
        manager.allocate("high_block", 100, priority=MemoryPriority.HIGH)
        freed = manager.gc()
        assert freed >= 0


class TestMemoryBlock:
    def test_init(self):
        block = MemoryBlock(id="test", size=100, usage="test")
        assert block.id == "test"
        assert block.size == 100

    def test_touch(self):
        block = MemoryBlock(id="test", size=100, usage="test")
        old_time = block.last_accessed
        block.touch()
        assert block.last_accessed >= old_time


class TestMemoryPool:
    def test_init(self):
        pool = MemoryPool(name="test")
        assert pool.name == "test"
        assert pool.max_size == 1024 * 1024

    def test_available_size(self):
        pool = MemoryPool(name="test", max_size=1000, used_size=300)
        assert pool.available_size == 700

    def test_utilization(self):
        pool = MemoryPool(name="test", max_size=1000, used_size=500)
        assert pool.utilization == 0.5


class TestContextCompressor:
    def test_init(self):
        compressor = ContextCompressor()
        assert compressor.method == CompressionMethod.LOSSY

    def test_compress_lossless(self):
        compressor = ContextCompressor(method=CompressionMethod.LOSSLESS)
        result = compressor.compress("hello hello hello world")
        assert result.method == CompressionMethod.LOSSLESS

    def test_compress_lossy(self):
        compressor = ContextCompressor(method=CompressionMethod.LOSSY)
        result = compressor.compress("The quick brown fox jumps over the lazy dog", target_ratio=0.5)
        assert result.method == CompressionMethod.LOSSY
        assert len(result.compressed) <= len(result.original)

    def test_compress_semantic(self):
        compressor = ContextCompressor(method=CompressionMethod.SEMANTIC)
        text = "First sentence. Second sentence with important data. Third sentence."
        result = compressor.compress(text, target_ratio=0.5)
        assert result.method == CompressionMethod.SEMANTIC

    def test_set_method(self):
        compressor = ContextCompressor()
        compressor.set_method(CompressionMethod.SEMANTIC)
        assert compressor.method == CompressionMethod.SEMANTIC

    def test_add_important_pattern(self):
        compressor = ContextCompressor()
        compressor.add_important_pattern(r"\bCUSTOM\b")
        assert r"\bCUSTOM\b" in compressor._important_patterns

    def test_get_compression_ratio(self):
        compressor = ContextCompressor()
        ratio = compressor.get_compression_ratio("original text here", "compressed")
        assert 0 <= ratio <= 1


class TestCompressionResult:
    def test_savings(self):
        result = CompressionResult(
            original="original",
            compressed="comp",
            method=CompressionMethod.LOSSY,
            ratio=0.5
        )
        assert result.savings == 0.5
