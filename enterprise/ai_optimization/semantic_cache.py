"""
Semantic Similarity Caching for AI Optimization.

This module provides a semantic caching system that uses embedding-based
similarity matching to find semantically similar queries and responses.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union
import threading
import math
import hashlib
import json


@dataclass
class SimilarityThreshold:
    """Configuration for semantic similarity matching thresholds."""
    
    exact_match: float = 1.0
    high_similarity: float = 0.95
    medium_similarity: float = 0.85
    low_similarity: float = 0.70
    
    def get_category(self, similarity: float) -> str:
        """Categorize similarity score."""
        if similarity >= self.exact_match:
            return 'exact'
        elif similarity >= self.high_similarity:
            return 'high'
        elif similarity >= self.medium_similarity:
            return 'medium'
        elif similarity >= self.low_similarity:
            return 'low'
        return 'none'


@dataclass
class EmbeddingVector:
    """Represents an embedding vector with metadata."""
    
    vector: List[float]
    dimension: int
    model: str = "default"
    created_at: datetime = field(default_factory=datetime.now)
    
    def __post_init__(self):
        if self.dimension != len(self.vector):
            self.dimension = len(self.vector)
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            'vector': self.vector[:10],  # Truncate for readability
            'dimension': self.dimension,
            'model': self.model,
            'created_at': self.created_at.isoformat(),
        }


@dataclass
class SemanticCacheEntry:
    """Represents an entry in the semantic cache."""
    
    key: str
    query: str
    embedding: EmbeddingVector
    response: Any
    ttl: Optional[float] = None
    timestamp: datetime = field(default_factory=datetime.now)
    access_count: int = 0
    similarity_hits: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def is_expired(self) -> bool:
        """Check if the entry has expired."""
        if self.ttl is None:
            return False
        expiry_time = self.timestamp + timedelta(seconds=self.ttl)
        return datetime.now() > expiry_time


@dataclass
class SemanticSearchResult:
    """Result from a semantic cache search."""
    
    entry: SemanticCacheEntry
    similarity: float
    match_category: str
    query_embedding: Optional[EmbeddingVector] = None


class VectorIndex:
    """
    A simple in-memory vector index for similarity search.
    
    Uses cosine similarity for vector comparison.
    """
    
    def __init__(self, dimension: int = 1536):
        """
        Initialize the vector index.
        
        Args:
            dimension: Dimension of vectors to store
        """
        self._dimension = dimension
        self._vectors: List[List[float]] = []
        self._keys: List[str] = []
        self._lock = threading.RLock()
    
    def add(self, key: str, vector: List[float]) -> None:
        """Add a vector to the index."""
        with self._lock:
            if len(vector) != self._dimension:
                raise ValueError(f"Vector dimension {len(vector)} != index dimension {self._dimension}")
            self._vectors.append(vector)
            self._keys.append(key)
    
    def remove(self, key: str) -> bool:
        """Remove a vector from the index."""
        with self._lock:
            if key in self._keys:
                idx = self._keys.index(key)
                self._vectors.pop(idx)
                self._keys.pop(idx)
                return True
            return False
    
    def search(
        self,
        query_vector: List[float],
        k: int = 5,
        min_similarity: float = 0.0,
    ) -> List[Tuple[str, float]]:
        """
        Search for similar vectors.
        
        Args:
            query_vector: The query vector
            k: Maximum number of results
            min_similarity: Minimum similarity threshold
            
        Returns:
            List of (key, similarity) tuples
        """
        with self._lock:
            if not self._vectors:
                return []
            
            similarities = []
            for i, vec in enumerate(self._vectors):
                sim = self._cosine_similarity(query_vector, vec)
                if sim >= min_similarity:
                    similarities.append((self._keys[i], sim))
            
            # Sort by similarity descending
            similarities.sort(key=lambda x: x[1], reverse=True)
            return similarities[:k]
    
    def get_vector(self, key: str) -> Optional[List[float]]:
        """Get a vector by key."""
        with self._lock:
            if key in self._keys:
                idx = self._keys.index(key)
                return self._vectors[idx]
            return None
    
    def clear(self) -> None:
        """Clear all vectors from the index."""
        with self._lock:
            self._vectors.clear()
            self._keys.clear()
    
    def __len__(self) -> int:
        return len(self._vectors)
    
    @staticmethod
    def _cosine_similarity(v1: List[float], v2: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        if len(v1) != len(v2):
            raise ValueError("Vectors must have same dimension")
        
        dot_product = sum(a * b for a, b in zip(v1, v2))
        norm1 = math.sqrt(sum(a * a for a in v1))
        norm2 = math.sqrt(sum(b * b for b in v2))
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot_product / (norm1 * norm2)


class SemanticCache:
    """
    A cache that uses semantic similarity for key matching.
    
    Features:
    - Embedding-based key matching
    - Vector similarity search
    - Configurable similarity thresholds
    - TTL support
    - Thread-safe operations
    """
    
    def __init__(
        self,
        embedding_dimension: int = 1536,
        similarity_threshold: Optional[SimilarityThreshold] = None,
        max_entries: int = 1000,
        default_ttl: Optional[float] = None,
        min_similarity_for_match: float = 0.85,
    ):
        """
        Initialize the semantic cache.
        
        Args:
            embedding_dimension: Dimension of embedding vectors
            similarity_threshold: Threshold configuration
            max_entries: Maximum cache entries
            default_ttl: Default TTL in seconds
            min_similarity_for_match: Minimum similarity to consider a match
        """
        self._embedding_dimension = embedding_dimension
        self._similarity_threshold = similarity_threshold or SimilarityThreshold()
        self._max_entries = max_entries
        self._default_ttl = default_ttl
        self._min_similarity = min_similarity_for_match
        
        self._entries: Dict[str, SemanticCacheEntry] = {}
        self._vector_index = VectorIndex(dimension=embedding_dimension)
        self._lock = threading.RLock()
        
        # Statistics
        self._stats = {
            'total_queries': 0,
            'exact_matches': 0,
            'semantic_matches': 0,
            'misses': 0,
            'evictions': 0,
        }
    
    def semantic_get(
        self,
        query_embedding: List[float],
        min_similarity: Optional[float] = None,
    ) -> Optional[SemanticSearchResult]:
        """
        Retrieve the most similar cached response.
        
        Args:
            query_embedding: Embedding of the query
            min_similarity: Override minimum similarity threshold
            
        Returns:
            SemanticSearchResult if found, None otherwise
        """
        with self._lock:
            self._stats['total_queries'] += 1
            threshold = min_similarity or self._min_similarity
            
            # Search for similar vectors
            results = self._vector_index.search(
                query_embedding,
                k=1,
                min_similarity=threshold,
            )
            
            if not results:
                self._stats['misses'] += 1
                return None
            
            key, similarity = results[0]
            entry = self._entries.get(key)
            
            if entry is None or entry.is_expired():
                # Clean up expired entry
                if entry:
                    self._remove_entry(key)
                self._stats['misses'] += 1
                return None
            
            # Update entry metadata
            entry.access_count += 1
            entry.similarity_hits += 1
            
            # Update stats
            if similarity >= self._similarity_threshold.exact_match:
                self._stats['exact_matches'] += 1
            else:
                self._stats['semantic_matches'] += 1
            
            return SemanticSearchResult(
                entry=entry,
                similarity=similarity,
                match_category=self._similarity_threshold.get_category(similarity),
            )
    
    def semantic_set(
        self,
        query: str,
        query_embedding: List[float],
        response: Any,
        ttl: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Store a query-response pair in the semantic cache.
        
        Args:
            query: The original query text
            query_embedding: Embedding of the query
            response: The response to cache
            ttl: Time-to-live in seconds
            metadata: Optional metadata
            
        Returns:
            The cache key for the entry
        """
        with self._lock:
            # Generate key
            key = self._generate_key(query, query_embedding)
            
            # Check capacity and evict if necessary
            while len(self._entries) >= self._max_entries:
                self._evict_oldest()
            
            # Create embedding vector
            embedding = EmbeddingVector(
                vector=query_embedding,
                dimension=len(query_embedding),
            )
            
            # Create entry
            entry = SemanticCacheEntry(
                key=key,
                query=query,
                embedding=embedding,
                response=response,
                ttl=ttl if ttl is not None else self._default_ttl,
                timestamp=datetime.now(),
                metadata=metadata or {},
            )
            
            # Store entry
            self._entries[key] = entry
            self._vector_index.add(key, query_embedding)
            
            return key
    
    def get_by_key(self, key: str) -> Optional[SemanticCacheEntry]:
        """Get a cached entry by its exact key."""
        with self._lock:
            entry = self._entries.get(key)
            if entry and not entry.is_expired():
                return entry
            return None
    
    def search_similar(
        self,
        query_embedding: List[float],
        k: int = 5,
        min_similarity: float = 0.5,
    ) -> List[SemanticSearchResult]:
        """
        Search for similar cached queries.
        
        Args:
            query_embedding: Embedding of the query
            k: Maximum number of results
            min_similarity: Minimum similarity threshold
            
        Returns:
            List of SemanticSearchResult
        """
        with self._lock:
            results = self._vector_index.search(
                query_embedding,
                k=k,
                min_similarity=min_similarity,
            )
            
            search_results = []
            for key, similarity in results:
                entry = self._entries.get(key)
                if entry and not entry.is_expired():
                    search_results.append(SemanticSearchResult(
                        entry=entry,
                        similarity=similarity,
                        match_category=self._similarity_threshold.get_category(similarity),
                    ))
            
            return search_results
    
    def invalidate(self, key: str) -> bool:
        """Remove an entry by key."""
        with self._lock:
            return self._remove_entry(key)
    
    def clear(self) -> None:
        """Clear all entries from the cache."""
        with self._lock:
            self._entries.clear()
            self._vector_index.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            total = self._stats['total_queries']
            exact_rate = self._stats['exact_matches'] / total if total > 0 else 0
            semantic_rate = self._stats['semantic_matches'] / total if total > 0 else 0
            miss_rate = self._stats['misses'] / total if total > 0 else 0
            
            return {
                **self._stats,
                'total_entries': len(self._entries),
                'exact_match_rate': exact_rate,
                'semantic_match_rate': semantic_rate,
                'miss_rate': miss_rate,
                'hit_rate': exact_rate + semantic_rate,
            }
    
    def cleanup_expired(self) -> int:
        """Remove all expired entries."""
        with self._lock:
            keys_to_remove = []
            for key, entry in self._entries.items():
                if entry.is_expired():
                    keys_to_remove.append(key)
            
            for key in keys_to_remove:
                self._remove_entry(key)
            
            return len(keys_to_remove)
    
    def get_all_queries(self) -> List[str]:
        """Get all cached queries."""
        with self._lock:
            return [entry.query for entry in self._entries.values() if not entry.is_expired()]
    
    def __len__(self) -> int:
        return len(self._entries)
    
    def _generate_key(self, query: str, embedding: List[float]) -> str:
        """Generate a unique key for a query."""
        data = {
            'query': query,
            'embedding_hash': hashlib.sha256(
                json.dumps(embedding[:10]).encode()
            ).hexdigest()[:16],
        }
        return hashlib.sha256(json.dumps(data).encode()).hexdigest()[:32]
    
    def _remove_entry(self, key: str) -> bool:
        """Remove an entry from cache and index."""
        if key in self._entries:
            del self._entries[key]
            self._vector_index.remove(key)
            return True
        return False
    
    def _evict_oldest(self) -> None:
        """Evict the oldest entry."""
        if not self._entries:
            return
        
        oldest_key = min(
            self._entries.keys(),
            key=lambda k: self._entries[k].timestamp,
        )
        self._remove_entry(oldest_key)
        self._stats['evictions'] += 1


def compute_cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """
    Compute cosine similarity between two vectors.
    
    Args:
        v1: First vector
        v2: Second vector
        
    Returns:
        Similarity score between -1 and 1
    """
    return VectorIndex._cosine_similarity(v1, v2)


def normalize_vector(vector: List[float]) -> List[float]:
    """
    Normalize a vector to unit length.
    
    Args:
        vector: Input vector
        
    Returns:
        Normalized vector
    """
    norm = math.sqrt(sum(x * x for x in vector))
    if norm == 0:
        return vector
    return [x / norm for x in vector]
