"""
Comprehensive tests for Cache Manager modules.

This test suite covers:
- ResponseCache (response_cache.py)
- SemanticCache (semantic_cache.py)
- CacheWarmer (cache_warmer.py)
"""

import pytest
import time
import threading
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch
import math


# =============================================================================
# Response Cache Tests
# =============================================================================

class TestCacheEntry:
    """Tests for CacheEntry dataclass."""
    
    def test_cache_entry_creation(self):
        """Test creating a cache entry."""
        from enterprise.ai_optimization.response_cache import CacheEntry
        
        entry = CacheEntry(
            key="test_key",
            value="test_value",
            ttl=60,
        )
        
        assert entry.key == "test_key"
        assert entry.value == "test_value"
        assert entry.ttl == 60
        assert entry.access_count == 0
    
    def test_cache_entry_expiration(self):
        """Test cache entry expiration check."""
        from enterprise.ai_optimization.response_cache import CacheEntry
        
        # Not expired entry
        entry = CacheEntry(
            key="key",
            value="value",
            ttl=3600,
        )
        assert not entry.is_expired()
        
        # Expired entry (ttl in the past)
        entry_expired = CacheEntry(
            key="key",
            value="value",
            ttl=0.001,
            timestamp=datetime.now() - timedelta(seconds=1),
        )
        assert entry_expired.is_expired()
    
    def test_cache_entry_touch(self):
        """Test touch method updates access metadata."""
        from enterprise.ai_optimization.response_cache import CacheEntry
        
        entry = CacheEntry(key="key", value="value")
        initial_count = entry.access_count
        initial_accessed = entry.last_accessed
        
        time.sleep(0.01)  # Small delay
        entry.touch()
        
        assert entry.access_count == initial_count + 1
        assert entry.last_accessed > initial_accessed


class TestCacheStats:
    """Tests for CacheStats dataclass."""
    
    def test_cache_stats_hit_rate(self):
        """Test hit rate calculation."""
        from enterprise.ai_optimization.response_cache import CacheStats
        
        stats = CacheStats(hits=80, misses=20)
        assert stats.hit_rate == 0.8
        assert abs(stats.miss_rate - 0.2) < 0.001  # Floating point comparison
    
    def test_cache_stats_zero_requests(self):
        """Test hit rate with zero requests."""
        from enterprise.ai_optimization.response_cache import CacheStats
        
        stats = CacheStats()
        assert stats.hit_rate == 0.0


class TestResponseCache:
    """Tests for ResponseCache class."""
    
    def test_response_cache_get_set(self):
        """Test basic get and set operations."""
        from enterprise.ai_optimization.response_cache import ResponseCache
        
        cache = ResponseCache()
        cache.set("key1", "value1")
        
        assert cache.get("key1") == "value1"
        assert cache.get("nonexistent") is None
    
    def test_response_cache_invalidate(self):
        """Test cache invalidation."""
        from enterprise.ai_optimization.response_cache import ResponseCache
        
        cache = ResponseCache()
        cache.set("key1", "value1")
        
        assert cache.invalidate("key1") is True
        assert cache.get("key1") is None
        assert cache.invalidate("key1") is False
    
    def test_response_cache_lru_eviction(self):
        """Test LRU eviction policy."""
        from enterprise.ai_optimization.response_cache import ResponseCache
        
        cache = ResponseCache(max_size=3)
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")
        cache.set("key4", "value4")  # Should evict key1
        
        assert cache.get("key1") is None
        assert cache.get("key2") == "value2"
        assert cache.get("key3") == "value3"
        assert cache.get("key4") == "value4"
    
    def test_response_cache_ttl(self):
        """Test TTL-based expiration."""
        from enterprise.ai_optimization.response_cache import ResponseCache
        
        cache = ResponseCache()
        cache.set("key1", "value1", ttl=0.1)
        
        assert cache.get("key1") == "value1"
        time.sleep(0.15)
        assert cache.get("key1") is None
    
    def test_response_cache_statistics(self):
        """Test cache statistics."""
        from enterprise.ai_optimization.response_cache import ResponseCache
        
        cache = ResponseCache()
        cache.set("key1", "value1")
        
        # Hit
        cache.get("key1")
        # Miss
        cache.get("nonexistent")
        
        stats = cache.get_stats()
        assert stats.hits == 1
        assert stats.misses == 1
        assert stats.hit_rate == 0.5
    
    def test_response_cache_pattern_invalidation(self):
        """Test pattern-based invalidation."""
        from enterprise.ai_optimization.response_cache import ResponseCache
        
        cache = ResponseCache()
        cache.set("user:1", "value1")
        cache.set("user:2", "value2")
        cache.set("product:1", "value3")
        
        count = cache.invalidate_pattern("user:*")
        
        assert count == 2
        assert cache.get("user:1") is None
        assert cache.get("user:2") is None
        assert cache.get("product:1") == "value3"
    
    def test_response_cache_get_or_set(self):
        """Test get_or_set method."""
        from enterprise.ai_optimization.response_cache import ResponseCache
        
        cache = ResponseCache()
        
        # Factory is called when key doesn't exist
        value = cache.get_or_set("key1", lambda: "computed_value")
        assert value == "computed_value"
        
        # Factory is not called when key exists
        value = cache.get_or_set("key1", lambda: "different_value")
        assert value == "computed_value"
    
    def test_response_cache_clear(self):
        """Test cache clearing."""
        from enterprise.ai_optimization.response_cache import ResponseCache
        
        cache = ResponseCache()
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        
        cache.clear()
        
        assert len(cache) == 0
        assert cache.get("key1") is None
    
    def test_response_cache_generate_key(self):
        """Test key generation from arguments."""
        from enterprise.ai_optimization.response_cache import ResponseCache
        
        key1 = ResponseCache.generate_key("arg1", "arg2", kwarg="value")
        key2 = ResponseCache.generate_key("arg1", "arg2", kwarg="value")
        key3 = ResponseCache.generate_key("arg1", "arg2", kwarg="different")
        
        assert key1 == key2
        assert key1 != key3


# =============================================================================
# Semantic Cache Tests
# =============================================================================

class TestSimilarityThreshold:
    """Tests for SimilarityThreshold class."""
    
    def test_similarity_threshold_categories(self):
        """Test similarity categorization."""
        from enterprise.ai_optimization.semantic_cache import SimilarityThreshold
        
        threshold = SimilarityThreshold()
        
        assert threshold.get_category(1.0) == 'exact'
        assert threshold.get_category(0.95) == 'high'
        assert threshold.get_category(0.85) == 'medium'
        assert threshold.get_category(0.70) == 'low'
        assert threshold.get_category(0.50) == 'none'
    
    def test_similarity_threshold_custom(self):
        """Test custom threshold values."""
        from enterprise.ai_optimization.semantic_cache import SimilarityThreshold
        
        threshold = SimilarityThreshold(
            exact_match=1.0,
            high_similarity=0.90,
            medium_similarity=0.80,
            low_similarity=0.60,
        )
        
        assert threshold.get_category(0.92) == 'high'
        assert threshold.get_category(0.75) == 'low'  # 0.75 < 0.80 (medium threshold)


class TestEmbeddingVector:
    """Tests for EmbeddingVector dataclass."""
    
    def test_embedding_vector_creation(self):
        """Test creating an embedding vector."""
        from enterprise.ai_optimization.semantic_cache import EmbeddingVector
        
        vector = EmbeddingVector(
            vector=[0.1, 0.2, 0.3],
            dimension=3,
            model="test-model"
        )
        
        assert vector.vector == [0.1, 0.2, 0.3]
        assert vector.dimension == 3
        assert vector.model == "test-model"
    
    def test_embedding_vector_auto_dimension(self):
        """Test auto-setting dimension."""
        from enterprise.ai_optimization.semantic_cache import EmbeddingVector
        
        vector = EmbeddingVector(
            vector=[0.1, 0.2, 0.3, 0.4],
            dimension=10  # Will be corrected
        )
        
        assert vector.dimension == 4


class TestVectorIndex:
    """Tests for VectorIndex class."""
    
    def test_vector_index_add_and_search(self):
        """Test adding vectors and searching."""
        from enterprise.ai_optimization.semantic_cache import VectorIndex
        
        index = VectorIndex(dimension=3)
        
        # Add vectors
        index.add("key1", [1.0, 0.0, 0.0])
        index.add("key2", [0.0, 1.0, 0.0])
        index.add("key3", [0.0, 0.0, 1.0])
        
        # Search for similar to [1, 0, 0]
        results = index.search([1.0, 0.0, 0.0], k=2)
        
        assert len(results) == 2
        assert results[0][0] == "key1"
        assert results[0][1] > 0.99  # Should be ~1.0
    
    def test_vector_index_cosine_similarity(self):
        """Test cosine similarity calculation."""
        from enterprise.ai_optimization.semantic_cache import VectorIndex
        
        # Identical vectors
        sim = VectorIndex._cosine_similarity([1, 0, 0], [1, 0, 0])
        assert abs(sim - 1.0) < 0.01
        
        # Orthogonal vectors
        sim = VectorIndex._cosine_similarity([1, 0, 0], [0, 1, 0])
        assert abs(sim) < 0.01
        
        # Opposite vectors
        sim = VectorIndex._cosine_similarity([1, 0, 0], [-1, 0, 0])
        assert abs(sim - (-1.0)) < 0.01
    
    def test_vector_index_remove(self):
        """Test removing vectors from index."""
        from enterprise.ai_optimization.semantic_cache import VectorIndex
        
        index = VectorIndex(dimension=3)
        index.add("key1", [1.0, 0.0, 0.0])
        
        assert index.remove("key1") is True
        assert len(index) == 0
        assert index.remove("nonexistent") is False


class TestSemanticCache:
    """Tests for SemanticCache class."""
    
    def test_semantic_cache_set_and_get(self):
        """Test basic semantic cache operations."""
        from enterprise.ai_optimization.semantic_cache import SemanticCache
        
        cache = SemanticCache(embedding_dimension=3)
        
        # Store an entry
        embedding = [1.0, 0.0, 0.0]
        key = cache.semantic_set("query1", embedding, "response1")
        
        # Retrieve with same embedding
        result = cache.semantic_get(embedding)
        
        assert result is not None
        assert result.entry.response == "response1"
        assert result.similarity > 0.99
    
    def test_semantic_cache_similarity_threshold(self):
        """Test similarity threshold filtering."""
        from enterprise.ai_optimization.semantic_cache import SemanticCache
        
        cache = SemanticCache(
            embedding_dimension=3,
            min_similarity_for_match=0.9
        )
        
        # Store entry
        cache.semantic_set("query1", [1.0, 0.0, 0.0], "response1")
        
        # Similar but not exact
        result = cache.semantic_get([0.7, 0.7, 0.0])
        
        # Should not match due to threshold
        # Note: cosine similarity ~0.707 which is below 0.9
        assert result is None
    
    def test_semantic_cache_stats(self):
        """Test semantic cache statistics."""
        from enterprise.ai_optimization.semantic_cache import SemanticCache
        
        cache = SemanticCache(embedding_dimension=3)
        
        cache.semantic_set("query1", [1.0, 0.0, 0.0], "response1")
        cache.semantic_get([1.0, 0.0, 0.0])  # Hit
        cache.semantic_get([0.0, 0.0, 1.0])  # Miss
        
        stats = cache.get_stats()
        
        assert stats['total_queries'] == 2
        assert stats['exact_matches'] + stats['semantic_matches'] == 1
        assert stats['misses'] == 1
    
    def test_semantic_cache_search_similar(self):
        """Test searching for similar entries."""
        from enterprise.ai_optimization.semantic_cache import SemanticCache
        
        cache = SemanticCache(embedding_dimension=3)
        
        cache.semantic_set("query1", [1.0, 0.0, 0.0], "response1")
        cache.semantic_set("query2", [0.9, 0.1, 0.0], "response2")
        cache.semantic_set("query3", [0.0, 1.0, 0.0], "response3")
        
        results = cache.search_similar([1.0, 0.0, 0.0], k=2)
        
        assert len(results) == 2
        assert results[0].similarity > results[1].similarity
    
    def test_semantic_cache_invalidate(self):
        """Test invalidating semantic cache entries."""
        from enterprise.ai_optimization.semantic_cache import SemanticCache
        
        cache = SemanticCache(embedding_dimension=3)
        
        key = cache.semantic_set("query1", [1.0, 0.0, 0.0], "response1")
        
        assert cache.invalidate(key) is True
        assert cache.get_by_key(key) is None
        assert cache.invalidate(key) is False
    
    def test_semantic_cache_clear(self):
        """Test clearing semantic cache."""
        from enterprise.ai_optimization.semantic_cache import SemanticCache
        
        cache = SemanticCache(embedding_dimension=3)
        
        cache.semantic_set("query1", [1.0, 0.0, 0.0], "response1")
        cache.semantic_set("query2", [0.0, 1.0, 0.0], "response2")
        
        cache.clear()
        
        assert len(cache) == 0


# =============================================================================
# Cache Warmer Tests
# =============================================================================

class TestWarmupTask:
    """Tests for WarmupTask dataclass."""
    
    def test_warmup_task_creation(self):
        """Test creating a warmup task."""
        from enterprise.ai_optimization.cache_warmer import (
            WarmupTask, WarmingStrategy, WarmingPriority, WarmingStatus
        )
        
        task = WarmupTask(
            task_id="task1",
            key="cache_key",
            loader=lambda: "value",
            strategy=WarmingStrategy.PREDICTIVE,
        )
        
        assert task.task_id == "task1"
        assert task.status == WarmingStatus.PENDING
        assert task.priority == WarmingPriority.MEDIUM
    
    def test_warmup_task_status_transitions(self):
        """Test task status transitions."""
        from enterprise.ai_optimization.cache_warmer import (
            WarmupTask, WarmingStrategy, WarmingStatus
        )
        
        task = WarmupTask(
            task_id="task1",
            key="key",
            loader=lambda: "value",
            strategy=WarmingStrategy.PREDICTIVE,
        )
        
        assert task.status == WarmingStatus.PENDING
        
        task.mark_running()
        assert task.status == WarmingStatus.RUNNING
        assert task.started_at is not None
        
        task.mark_completed()
        assert task.status == WarmingStatus.COMPLETED
        assert task.completed_at is not None
    
    def test_warmup_task_retry(self):
        """Test task retry logic."""
        from enterprise.ai_optimization.cache_warmer import (
            WarmupTask, WarmingStrategy, WarmingStatus
        )
        
        task = WarmupTask(
            task_id="task1",
            key="key",
            loader=lambda: "value",
            strategy=WarmingStrategy.PREDICTIVE,
            max_retries=2,
        )
        
        task.mark_failed("Test error")
        assert task.can_retry() is True
        
        task.increment_retry()
        assert task.retries == 1
        assert task.status == WarmingStatus.PENDING
        
        task.mark_failed("Another error")
        task.increment_retry()
        assert task.retries == 2
        assert task.can_retry() is False  # Max retries reached


class TestWarmingStrategy:
    """Tests for WarmingStrategy enum."""
    
    def test_warming_strategy_values(self):
        """Test warming strategy enum values."""
        from enterprise.ai_optimization.cache_warmer import WarmingStrategy
        
        assert WarmingStrategy.PREDICTIVE.value == "predictive"
        assert WarmingStrategy.SCHEDULED.value == "scheduled"
        assert WarmingStrategy.ADAPTIVE.value == "adaptive"


class TestAccessPattern:
    """Tests for AccessPattern dataclass."""
    
    def test_access_pattern_recording(self):
        """Test recording access patterns."""
        from enterprise.ai_optimization.cache_warmer import AccessPattern
        
        pattern = AccessPattern(key="test_key")
        
        pattern.record_access()
        assert pattern.access_count == 1
        
        pattern.record_access()
        assert pattern.access_count == 2
    
    def test_access_pattern_importance(self):
        """Test importance score calculation."""
        from enterprise.ai_optimization.cache_warmer import AccessPattern
        
        pattern = AccessPattern(key="test_key")
        pattern.record_access()
        pattern.record_access()
        
        score = pattern.importance_score
        assert score > 0
    
    def test_access_pattern_prediction(self):
        """Test next access prediction."""
        from enterprise.ai_optimization.cache_warmer import AccessPattern
        
        pattern = AccessPattern(key="test_key")
        
        # No prediction without history
        assert pattern.predict_next_access() is None
        
        # Record some accesses
        pattern.record_access()
        time.sleep(0.1)
        pattern.record_access()
        
        # Should have a prediction now
        prediction = pattern.predict_next_access()
        assert prediction is not None


class TestCacheWarmer:
    """Tests for CacheWarmer class."""
    
    def test_cache_warmer_warm(self):
        """Test queueing keys for warming."""
        from enterprise.ai_optimization.cache_warmer import (
            CacheWarmer, WarmingStrategy
        )
        from enterprise.ai_optimization.response_cache import ResponseCache
        
        cache = ResponseCache()
        warmer = CacheWarmer(cache)
        
        task_ids = warmer.warm(
            keys=["key1", "key2"],
            loader=lambda: "value",
            strategy=WarmingStrategy.SCHEDULED,
        )
        
        assert len(task_ids) == 2
        assert len(warmer.get_pending_tasks()) == 2
    
    def test_cache_warmer_prefill(self):
        """Test prefilling cache with data."""
        from enterprise.ai_optimization.cache_warmer import (
            CacheWarmer, WarmingStrategy
        )
        from enterprise.ai_optimization.response_cache import ResponseCache
        
        cache = ResponseCache()
        warmer = CacheWarmer(cache)
        
        data = {
            "key1": "value1",
            "key2": "value2",
            "key3": "value3",
        }
        
        count = warmer.prefill(data, strategy=WarmingStrategy.SCHEDULED)
        
        assert count == 3
        assert cache.get("key1") == "value1"
        assert cache.get("key2") == "value2"
    
    def test_cache_warmer_execute_now(self):
        """Test immediate task execution."""
        from enterprise.ai_optimization.cache_warmer import CacheWarmer
        from enterprise.ai_optimization.response_cache import ResponseCache
        
        cache = ResponseCache()
        warmer = CacheWarmer(cache)
        
        warmer.warm(
            keys=["key1"],
            loader=lambda: "loaded_value",
        )
        
        count = warmer.execute_now()
        
        assert count == 1
        assert cache.get("key1") == "loaded_value"
    
    def test_cache_warmer_cancel_task(self):
        """Test cancelling a task."""
        from enterprise.ai_optimization.cache_warmer import CacheWarmer
        from enterprise.ai_optimization.response_cache import ResponseCache
        
        cache = ResponseCache()
        warmer = CacheWarmer(cache)
        
        task_ids = warmer.warm(
            keys=["key1"],
            loader=lambda: "value",
        )
        
        result = warmer.cancel_task(task_ids[0])
        
        assert result is True
        task = warmer.get_task(task_ids[0])
        from enterprise.ai_optimization.cache_warmer import WarmingStatus
        assert task.status == WarmingStatus.CANCELLED
    
    def test_cache_warmer_record_access(self):
        """Test recording access patterns."""
        from enterprise.ai_optimization.cache_warmer import CacheWarmer
        from enterprise.ai_optimization.response_cache import ResponseCache
        
        cache = ResponseCache()
        warmer = CacheWarmer(cache)
        
        warmer.record_access("key1")
        warmer.record_access("key1")
        warmer.record_access("key2")
        warmer.record_access("key2")  # Need 2 accesses to meet min_access_count
        
        predictive_keys = warmer.get_predictive_keys(top_n=10, min_access_count=2)
        
        assert "key1" in predictive_keys
        assert "key2" in predictive_keys
    
    def test_cache_warmer_statistics(self):
        """Test warming statistics."""
        from enterprise.ai_optimization.cache_warmer import (
            CacheWarmer, WarmingStrategy
        )
        from enterprise.ai_optimization.response_cache import ResponseCache
        
        cache = ResponseCache()
        warmer = CacheWarmer(cache)
        
        warmer.warm(
            keys=["key1"],
            loader=lambda: "value",
        )
        warmer.execute_now()
        
        stats = warmer.get_stats()
        
        assert stats.total_tasks == 1
        assert stats.completed_tasks == 1
    
    def test_cache_warmer_schedule_warmup(self):
        """Test scheduling a warmup."""
        from enterprise.ai_optimization.cache_warmer import CacheWarmer
        from enterprise.ai_optimization.response_cache import ResponseCache
        
        cache = ResponseCache()
        warmer = CacheWarmer(cache)
        
        warmer.schedule_warmup(
            schedule_id="schedule1",
            keys=["key1", "key2"],
            trigger_time=datetime.now() + timedelta(hours=1),
        )
        
        warmer.cancel_schedule("schedule1")
        # No exception means success
    
    def test_cache_warmer_retry_failed(self):
        """Test retrying failed tasks."""
        from enterprise.ai_optimization.cache_warmer import CacheWarmer
        from enterprise.ai_optimization.response_cache import ResponseCache
        
        cache = ResponseCache()
        warmer = CacheWarmer(cache)
        
        # Create a task that will fail
        def failing_loader():
            raise Exception("Test failure")
        
        warmer.warm(keys=["key1"], loader=failing_loader)
        warmer.execute_now()
        
        # Task should have failed
        pending = warmer.get_pending_tasks()
        assert len(pending) == 0
        
        # Retry
        retry_count = warmer.retry_failed()
        assert retry_count == 1


class TestWarmingStats:
    """Tests for WarmingStats dataclass."""
    
    def test_warming_stats_record_completion(self):
        """Test recording task completion."""
        from enterprise.ai_optimization.cache_warmer import (
            WarmingStats, WarmupTask, WarmingStrategy
        )
        
        stats = WarmingStats()
        task = WarmupTask(
            task_id="task1",
            key="key",
            loader=lambda: "value",
            strategy=WarmingStrategy.PREDICTIVE,
        )
        task.mark_running()
        task.mark_completed()
        
        stats.record_completion(task)
        
        assert stats.completed_tasks == 1
        assert stats.total_keys_warmed == 1
    
    def test_warming_stats_to_dict(self):
        """Test serializing stats to dictionary."""
        from enterprise.ai_optimization.cache_warmer import WarmingStats
        
        stats = WarmingStats(
            total_tasks=10,
            completed_tasks=8,
            failed_tasks=2,
        )
        
        result = stats.to_dict()
        
        assert result['total_tasks'] == 10
        assert result['completed_tasks'] == 8
        assert result['success_rate'] == 0.8


# =============================================================================
# Integration Tests
# =============================================================================

class TestIntegration:
    """Integration tests for cache manager components."""
    
    def test_response_cache_with_warming(self):
        """Test ResponseCache integration with CacheWarmer."""
        from enterprise.ai_optimization.response_cache import ResponseCache
        from enterprise.ai_optimization.cache_warmer import CacheWarmer
        
        cache = ResponseCache()
        warmer = CacheWarmer(cache)
        
        # Warm the cache
        warmer.prefill({"key1": "value1", "key2": "value2"})
        
        # Access should be a hit
        assert cache.get("key1") == "value1"
        
        stats = cache.get_stats()
        assert stats.hits == 1
    
    def test_semantic_cache_workflow(self):
        """Test complete semantic cache workflow."""
        from enterprise.ai_optimization.semantic_cache import (
            SemanticCache, compute_cosine_similarity
        )
        
        cache = SemanticCache(embedding_dimension=4)
        
        # Store several queries
        queries = [
            ("What is AI?", [1.0, 0.0, 0.0, 0.0], "AI is artificial intelligence."),
            ("What is ML?", [0.9, 0.1, 0.0, 0.0], "ML is machine learning."),
            ("What is NLP?", [0.0, 1.0, 0.0, 0.0], "NLP is natural language processing."),
        ]
        
        for query, embedding, response in queries:
            cache.semantic_set(query, embedding, response)
        
        # Query with similar embedding
        result = cache.semantic_get([1.0, 0.0, 0.0, 0.0])
        
        assert result is not None
        assert "AI" in result.entry.response
    
    def test_combined_cache_workflow(self):
        """Test combined workflow with all cache types."""
        from enterprise.ai_optimization.response_cache import ResponseCache
        from enterprise.ai_optimization.semantic_cache import SemanticCache
        from enterprise.ai_optimization.cache_warmer import CacheWarmer, WarmingStrategy
        
        # Create caches
        response_cache = ResponseCache()
        semantic_cache = SemanticCache(embedding_dimension=3)
        
        # Warm response cache
        warmer = CacheWarmer(response_cache)
        warmer.prefill({"hot_key": "hot_value"}, strategy=WarmingStrategy.SCHEDULED)
        
        # Verify warming worked
        assert response_cache.get("hot_key") == "hot_value"
        
        # Store in semantic cache
        semantic_cache.semantic_set("query", [1, 0, 0], "response")
        
        # Verify semantic cache works
        result = semantic_cache.semantic_get([1, 0, 0])
        assert result is not None


# =============================================================================
# Edge Case Tests
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and error handling."""
    
    def test_response_cache_empty_value(self):
        """Test caching empty values."""
        from enterprise.ai_optimization.response_cache import ResponseCache
        
        cache = ResponseCache()
        cache.set("empty", "")
        
        assert cache.get("empty") == ""
    
    def test_response_cache_none_value(self):
        """Test caching None values."""
        from enterprise.ai_optimization.response_cache import ResponseCache
        
        cache = ResponseCache()
        cache.set("none_key", None)
        
        # None is cached, but get returns None for miss too
        # So we check the entry directly
        entry = cache.get_entry("none_key")
        assert entry is not None
        assert entry.value is None
    
    def test_semantic_cache_empty_index(self):
        """Test searching empty semantic cache."""
        from enterprise.ai_optimization.semantic_cache import SemanticCache
        
        cache = SemanticCache(embedding_dimension=3)
        
        result = cache.semantic_get([1, 0, 0])
        assert result is None
    
    def test_vector_index_dimension_mismatch(self):
        """Test vector dimension validation."""
        from enterprise.ai_optimization.semantic_cache import VectorIndex
        
        index = VectorIndex(dimension=3)
        
        with pytest.raises(ValueError):
            index.add("key", [1, 2, 3, 4])  # Wrong dimension
    
    def test_cache_warmer_empty_keys(self):
        """Test warming with empty key list."""
        from enterprise.ai_optimization.cache_warmer import CacheWarmer
        from enterprise.ai_optimization.response_cache import ResponseCache
        
        cache = ResponseCache()
        warmer = CacheWarmer(cache)
        
        task_ids = warmer.warm([], loader=lambda: "value")
        assert len(task_ids) == 0
    
    def test_cache_warmer_concurrent_access(self):
        """Test concurrent access to cache warmer."""
        from enterprise.ai_optimization.cache_warmer import CacheWarmer
        from enterprise.ai_optimization.response_cache import ResponseCache
        
        cache = ResponseCache()
        warmer = CacheWarmer(cache)
        
        results = []
        
        def warm_thread(i):
            task_ids = warmer.warm([f"key{i}"], loader=lambda: f"value{i}")
            results.extend(task_ids)
        
        threads = [threading.Thread(target=warm_thread, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert len(results) == 5
