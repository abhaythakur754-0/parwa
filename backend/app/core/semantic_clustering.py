"""
Semantic Clustering Engine (F-071): Groups similar tickets by embedding
similarity for batch operations (batch approval, bulk resolution,
trend identification).

Uses deterministic hash-based embeddings with cosine similarity.
No LLM calls — all operations are heuristic-based.

BC-001: All operations tenant-isolated by company_id.
BC-004: Background job compatible (pure computation, no I/O).
BC-007: AI quality maintained — deterministic, reproducible embeddings.
BC-008: Never crashes — graceful degradation on any input.
"""

from __future__ import annotations

import hashlib
import math
import struct
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from app.logger import get_logger

logger = get_logger("semantic_clustering")


# ══════════════════════════════════════════════════════════════════
# CONSTANTS
# ══════════════════════════════════════════════════════════════════

# Default embedding dimension for hash-based vectors.
EMBEDDING_DIMENSION: int = 128

# Minimum text length to generate a meaningful embedding.
MIN_TEXT_LENGTH: int = 2


# ══════════════════════════════════════════════════════════════════
# DATA CLASSES
# ══════════════════════════════════════════════════════════════════


class ClusterStatus(str, Enum):
    """Status of a semantic cluster."""

    PENDING = "pending"
    PARTIAL = "partial"
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass
class ClusterConfig:
    """Configuration for clustering parameters.

    Attributes:
        min_similarity: Minimum cosine similarity to group tickets.
        max_cluster_size: Maximum tickets per cluster.
        cluster_ttl_hours: Hours before a cluster expires.
        max_clusters_per_company: Max clusters per tenant per run.
        embedding_dimension: Dimensionality of embedding vectors.
    """

    min_similarity: float = 0.75
    max_cluster_size: int = 50
    cluster_ttl_hours: int = 168  # 7 days
    max_clusters_per_company: int = 200
    embedding_dimension: int = EMBEDDING_DIMENSION

    def __post_init__(self) -> None:
        """Validate config values (BC-008: never crash)."""
        try:
            self.min_similarity = float(max(0.0, min(1.0, self.min_similarity)))
            self.max_cluster_size = int(max(1, self.max_cluster_size))
            self.cluster_ttl_hours = int(max(1, self.cluster_ttl_hours))
            self.max_clusters_per_company = int(max(1, self.max_clusters_per_company))
            self.embedding_dimension = int(max(1, self.embedding_dimension))
        except (TypeError, ValueError):
            # BC-008: fall back to safe defaults on garbage input
            self.min_similarity = 0.75
            self.max_cluster_size = 50
            self.cluster_ttl_hours = 168
            self.max_clusters_per_company = 200
            self.embedding_dimension = EMBEDDING_DIMENSION


@dataclass(frozen=True)
class ClusterConfigFrozen:
    """Frozen (immutable) version of ClusterConfig for safe sharing."""

    min_similarity: float = 0.75
    max_cluster_size: int = 50
    cluster_ttl_hours: int = 168
    max_clusters_per_company: int = 200
    embedding_dimension: int = EMBEDDING_DIMENSION


@dataclass
class TicketInput:
    """Input ticket for clustering.

    Attributes:
        ticket_id: Unique ticket identifier.
        text: Ticket text/content for embedding generation.
        confidence: AI classification confidence (0.0-1.0).
        intent_label: Classified intent label.
        metadata: Arbitrary extra data attached to the ticket.
    """

    ticket_id: str
    text: str = ""
    confidence: float = 0.0
    intent_label: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TicketSimilarity:
    """Result of comparing a ticket against a cluster or query.

    Attributes:
        ticket_id: Matching ticket identifier.
        similarity_score: Cosine similarity (0.0-1.0).
        confidence_score: Confidence of the match.
    """

    ticket_id: str
    similarity_score: float
    confidence_score: float


@dataclass
class ClusterTicket:
    """A ticket belonging to a cluster.

    Attributes:
        ticket_id: Ticket identifier.
        similarity_score: Similarity to cluster center.
        confidence_score: Ticket classification confidence.
        approval_record_id: Optional approval record for batch operations.
    """

    ticket_id: str
    similarity_score: float
    confidence_score: float
    approval_record_id: Optional[str] = None


@dataclass
class SemanticCluster:
    """A cluster of semantically similar tickets.

    Attributes:
        id: Unique cluster identifier.
        company_id: Tenant identifier (BC-001).
        intent_label: Dominant intent label in the cluster.
        embedding_center: Centroid embedding vector.
        avg_confidence: Average confidence of tickets in cluster.
        ticket_count: Number of tickets in the cluster.
        status: Cluster lifecycle status.
        tickets: List of tickets in this cluster.
        created_at: UTC timestamp of cluster creation.
        expires_at: UTC timestamp when cluster expires.
    """

    id: str
    company_id: str
    intent_label: str = ""
    embedding_center: List[float] = field(default_factory=list)
    avg_confidence: float = 0.0
    ticket_count: int = 0
    status: str = ClusterStatus.PENDING.value
    tickets: List[ClusterTicket] = field(default_factory=list)
    created_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        """Set defaults for timestamps if not provided."""
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)
        if self.expires_at is None:
            self.expires_at = self.created_at  # caller should set TTL


# ══════════════════════════════════════════════════════════════════
# EMBEDDING GENERATION
# ══════════════════════════════════════════════════════════════════


def generate_embedding(
    text: str,
    dimension: int = EMBEDDING_DIMENSION,
) -> List[float]:
    """Generate a deterministic hash-based embedding from text.

    Uses a sliding-window hash approach so that similar text produces
    similar embeddings. Same text always produces the same embedding.

    Args:
        text: Input text to embed.
        dimension: Vector dimensionality (default 128).

    Returns:
        Fixed-length float vector of the specified dimension.
    """
    try:
        if not isinstance(text, str):
            text = str(text) if text is not None else ""

        text = text.lower().strip()

        if len(text) < MIN_TEXT_LENGTH:
            # Return zero vector for too-short input
            return [0.0] * dimension

        # Ensure dimension is valid
        dimension = max(1, int(dimension))

        # Generate embeddings using overlapping character n-gram hashes
        embedding = [0.0] * dimension
        window_size = 3  # trigram windows
        seen_hashes: Dict[int, int] = {}

        for i in range(len(text) - window_size + 1):
            ngram = text[i:i + window_size]
            h = hashlib.md5(ngram.encode("utf-8", errors="replace")).digest()
            # Use first 4 bytes of hash as a dimension index
            idx = struct.unpack("<I", h[:4])[0] % dimension
            # Use next 4 bytes as a weight value (normalized to [-1, 1])
            val = struct.unpack("<i", h[4:8])[0]
            normalized_val = (val % 1000) / 500.0 - 1.0
            # Accumulate (TF-IDF-ish: repeated n-grams strengthen signal)
            if idx in seen_hashes:
                seen_hashes[idx] += 1
                # Diminishing returns for repeated n-grams
                embedding[idx] += normalized_val / (seen_hashes[idx] ** 0.5)
            else:
                seen_hashes[idx] = 1
                embedding[idx] += normalized_val

        # Add character-level bigram features for finer granularity
        for i in range(len(text) - 1):
            bigram = text[i:i + 2]
            h = hashlib.sha1(bigram.encode("utf-8", errors="replace")).digest()
            idx = struct.unpack("<I", h[:4])[0] % dimension
            val = struct.unpack("<i", h[4:8])[0]
            normalized_val = (val % 500) / 500.0 - 0.5
            embedding[idx] += normalized_val * 0.3  # lower weight for bigrams

        # Normalize the vector to unit length for cosine similarity
        magnitude = math.sqrt(sum(x * x for x in embedding))
        if magnitude > 1e-10:
            embedding = [x / magnitude for x in embedding]

        return embedding

    except Exception:
        # BC-008: never crash
        logger.warning(
            "embedding_generation_failed",
            error="unexpected_error",
        )
        try:
            safe_dim = max(1, int(dimension))
        except (TypeError, ValueError):
            safe_dim = EMBEDDING_DIMENSION
        return [0.0] * safe_dim


# ══════════════════════════════════════════════════════════════════
# SIMILARITY FUNCTIONS
# ══════════════════════════════════════════════════════════════════


def cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    """Compute cosine similarity between two vectors.

    Handles zero vectors, mismatched dimensions, and garbage input
    gracefully (BC-008).

    Args:
        vec_a: First vector.
        vec_b: Second vector.

    Returns:
        Cosine similarity in range [-1.0, 1.0]. Returns 0.0 for
        zero vectors or invalid input.
    """
    try:
        if not vec_a or not vec_b:
            return 0.0

        # BC-008: reject vectors containing NaN or Inf
        import math as _math
        for val in vec_a:
            if _math.isnan(val) or _math.isinf(val):
                return 0.0
        for val in vec_b:
            if _math.isnan(val) or _math.isinf(val):
                return 0.0

        # Pad shorter vector with zeros if dimensions differ
        max_len = max(len(vec_a), len(vec_b))
        if len(vec_a) < max_len:
            vec_a = vec_a + [0.0] * (max_len - len(vec_a))
        if len(vec_b) < max_len:
            vec_b = vec_b + [0.0] * (max_len - len(vec_b))

        dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
        mag_a = math.sqrt(sum(a * a for a in vec_a))
        mag_b = math.sqrt(sum(b * b for b in vec_b))

        if mag_a < 1e-10 or mag_b < 1e-10:
            return 0.0

        similarity = dot_product / (mag_a * mag_b)
        # Clamp to valid range
        return max(-1.0, min(1.0, similarity))

    except Exception:
        # BC-008: never crash
        return 0.0


# ══════════════════════════════════════════════════════════════════
# SEMANTIC CLUSTERING ENGINE
# ══════════════════════════════════════════════════════════════════


class SemanticClusteringEngine:
    """Core engine for semantic ticket clustering (F-071).

    Groups similar tickets by embedding similarity using greedy
    agglomerative clustering. Supports batch approval (F-075),
    trend identification, and bulk resolution.

    BC-001: All operations tenant-isolated by company_id.
    BC-004: Background job compatible (pure computation).
    BC-007: Deterministic, reproducible embeddings.
    BC-008: Never crashes on any input.
    """

    def __init__(self, config: Optional[ClusterConfig] = None) -> None:
        """Initialize the clustering engine.

        Args:
            config: Optional clustering configuration. Uses defaults if None.
        """
        self._config = config or ClusterConfig()

    @property
    def config(self) -> ClusterConfig:
        """Return the current clustering configuration."""
        return self._config

    def cluster_tickets(
        self,
        company_id: str,
        tickets: List[Any],
        min_similarity: Optional[float] = None,
        max_cluster_size: Optional[int] = None,
    ) -> List[SemanticCluster]:
        """Cluster tickets by embedding similarity.

        Uses greedy agglomerative clustering: starts with each ticket
        as its own cluster, then iteratively merges the most similar
        pair above the threshold until no more merges are possible.

        Args:
            company_id: Tenant identifier (BC-001).
            tickets: List of ticket dicts or TicketInput objects.
            min_similarity: Override config min_similarity.
            max_cluster_size: Override config max_cluster_size.

        Returns:
            List of SemanticCluster objects, sorted by ticket_count desc.
        """
        start = time.monotonic()

        # BC-008: safe defaults for garbage input
        try:
            company_id = str(company_id) if company_id is not None else ""
        except Exception:
            company_id = ""

        if not company_id:
            logger.warning(
                "cluster_tickets_empty_company",
                reason="empty_company_id",
            )
            return []

        # Normalize tickets to TicketInput objects
        if not tickets:
            return []
        normalized = self._normalize_tickets(tickets)
        if not normalized:
            return []

        threshold = (
            min_similarity
            if min_similarity is not None
            else self._config.min_similarity
        )
        max_size = (
            max_cluster_size
            if max_cluster_size is not None
            else self._config.max_cluster_size
        )

        # Clamp values safely
        try:
            threshold = float(max(0.0, min(1.0, threshold)))
            max_size = int(max(1, max_size))
        except (TypeError, ValueError):
            threshold = self._config.min_similarity
            max_size = self._config.max_cluster_size

        # Generate embeddings for all tickets
        embeddings: Dict[str, List[float]] = {}
        for ticket in normalized:
            embeddings[ticket.ticket_id] = generate_embedding(
                ticket.text,
                self._config.embedding_dimension,
            )

        # Initialize: each ticket is its own cluster
        clusters: Dict[str, List[str]] = {
            t.ticket_id: [t.ticket_id] for t in normalized
        }
        ticket_map: Dict[str, TicketInput] = {
            t.ticket_id: t for t in normalized
        }

        # Greedy agglomerative merging
        changed = True
        while changed and len(clusters) > 1:
            changed = False
            best_sim = -1.0
            best_pair: Optional[Tuple[str, str]] = None

            cluster_ids = list(clusters.keys())

            # Find the most similar pair of clusters
            for i in range(len(cluster_ids)):
                for j in range(i + 1, len(cluster_ids)):
                    c1_id = cluster_ids[i]
                    c2_id = cluster_ids[j]
                    c1_tickets = clusters[c1_id]
                    c2_tickets = clusters[c2_id]

                    # Don't merge if combined size exceeds max
                    if len(c1_tickets) + len(c2_tickets) > max_size:
                        continue

                    # Compare cluster centers
                    center1 = self._compute_cluster_center(
                        c1_tickets, embeddings
                    )
                    center2 = self._compute_cluster_center(
                        c2_tickets, embeddings
                    )
                    sim = cosine_similarity(center1, center2)

                    if sim > best_sim and sim >= threshold:
                        best_sim = sim
                        best_pair = (c1_id, c2_id)

            if best_pair is not None:
                c1_id, c2_id = best_pair
                clusters[c1_id] = clusters[c1_id] + clusters[c2_id]
                del clusters[c2_id]
                changed = True

        # Convert internal clusters to SemanticCluster objects
        results = []
        for cluster_id, ticket_ids in clusters.items():
            if not ticket_ids:
                continue

            cluster_tickets = []
            center = self._compute_cluster_center(ticket_ids, embeddings)
            total_confidence = 0.0
            intent_counts: Dict[str, int] = {}

            for tid in ticket_ids:
                t_input = ticket_map.get(tid)
                if t_input is None:
                    continue

                sim = cosine_similarity(
                    embeddings.get(tid, []),
                    center,
                )
                cluster_tickets.append(
                    ClusterTicket(
                        ticket_id=tid,
                        similarity_score=round(sim, 4),
                        confidence_score=round(t_input.confidence, 4),
                    )
                )
                total_confidence += t_input.confidence
                if t_input.intent_label:
                    intent_counts[t_input.intent_label] = (
                        intent_counts.get(t_input.intent_label, 0) + 1
                    )

            # Determine dominant intent
            dominant_intent = ""
            if intent_counts:
                dominant_intent = max(
                    intent_counts, key=intent_counts.get
                )

            avg_conf = (
                round(total_confidence / len(cluster_tickets), 4)
                if cluster_tickets
                else 0.0
            )

            now = datetime.now(timezone.utc)
            results.append(
                SemanticCluster(
                    id=f"cl_{uuid.uuid4().hex[:12]}",
                    company_id=company_id,
                    intent_label=dominant_intent,
                    embedding_center=center,
                    avg_confidence=avg_conf,
                    ticket_count=len(cluster_tickets),
                    status=ClusterStatus.PENDING.value,
                    tickets=cluster_tickets,
                    created_at=now,
                    expires_at=now,
                )
            )

        # Sort by ticket_count descending
        results.sort(key=lambda c: c.ticket_count, reverse=True)

        elapsed = round((time.monotonic() - start) * 1000, 2)
        logger.info(
            "cluster_tickets_complete",
            company_id=company_id,
            input_count=len(normalized),
            cluster_count=len(results),
            threshold=threshold,
            elapsed_ms=elapsed,
        )

        return results

    def find_similar_tickets(
        self,
        query_embedding: List[float],
        candidates: List[TicketSimilarity],
        threshold: float = 0.75,
    ) -> List[TicketSimilarity]:
        """Find tickets similar to a query embedding.

        Filters candidate tickets by similarity threshold and sorts
        by similarity score descending.

        Args:
            query_embedding: The query vector to compare against.
            candidates: Candidate tickets with their embeddings.
            threshold: Minimum similarity score (default 0.75).

        Returns:
            List of TicketSimilarity objects above threshold, sorted
            by similarity descending.
        """
        try:
            threshold = float(max(0.0, min(1.0, threshold)))
        except (TypeError, ValueError):
            threshold = 0.75

        if not query_embedding or not candidates:
            return []

        results = []
        for candidate in candidates:
            # Build a simple embedding from candidate for comparison
            # In production this would use the stored embedding;
            # here we just filter by the candidate's similarity_score
            if candidate.similarity_score >= threshold:
                results.append(candidate)

        # Sort by similarity descending
        results.sort(
            key=lambda c: c.similarity_score,
            reverse=True,
        )
        return results

    def find_similar_tickets_by_text(
        self,
        query_text: str,
        tickets: List[TicketInput],
        threshold: float = 0.75,
    ) -> List[TicketSimilarity]:
        """Find tickets similar to a query text.

        Generates embedding for the query text and compares against
        all ticket embeddings.

        Args:
            query_text: Query text to find similar tickets for.
            tickets: List of TicketInput objects to search.
            threshold: Minimum similarity score (default 0.75).

        Returns:
            List of TicketSimilarity objects above threshold.
        """
        try:
            if not isinstance(query_text, str) or not query_text.strip():
                return []
        except Exception:
            return []

        query_emb = generate_embedding(
            query_text, self._config.embedding_dimension
        )

        results: List[TicketSimilarity] = []
        for ticket in tickets:
            ticket_emb = generate_embedding(
                ticket.text, self._config.embedding_dimension
            )
            sim = cosine_similarity(query_emb, ticket_emb)
            if sim >= threshold:
                results.append(
                    TicketSimilarity(
                        ticket_id=ticket.ticket_id,
                        similarity_score=round(sim, 4),
                        confidence_score=round(ticket.confidence, 4),
                    )
                )

        results.sort(
            key=lambda c: c.similarity_score,
            reverse=True,
        )
        return results

    def calculate_cluster_center(
        self, embeddings: List[List[float]],
    ) -> List[float]:
        """Calculate the centroid (mean) of a list of embeddings.

        Args:
            embeddings: List of embedding vectors.

        Returns:
            Mean embedding vector. Returns empty list for empty input.
        """
        try:
            if not embeddings:
                return []

            # Normalize all to same dimension
            max_dim = max(len(e) for e in embeddings)
            padded = []
            for e in embeddings:
                if len(e) < max_dim:
                    padded.append(e + [0.0] * (max_dim - len(e)))
                else:
                    padded.append(e[:max_dim])

            n = len(padded)
            center = []
            for i in range(max_dim):
                avg = sum(e[i] for e in padded) / n
                center.append(avg)

            return center

        except Exception:
            # BC-008: never crash
            logger.warning(
                "calculate_cluster_center_failed",
                error="unexpected_error",
            )
            return []

    def get_cluster_summary(
        self, cluster: SemanticCluster,
    ) -> Dict[str, Any]:
        """Get a summary dictionary for a cluster.

        Useful for API responses and logging.

        Args:
            cluster: The cluster to summarize.

        Returns:
            Dictionary with cluster metadata.
        """
        return {
            "id": cluster.id,
            "company_id": cluster.company_id,
            "intent_label": cluster.intent_label,
            "avg_confidence": cluster.avg_confidence,
            "ticket_count": cluster.ticket_count,
            "status": cluster.status,
            "ticket_ids": [t.ticket_id for t in cluster.tickets],
            "created_at": (
                cluster.created_at.isoformat()
                if cluster.created_at
                else None
            ),
            "expires_at": (
                cluster.expires_at.isoformat()
                if cluster.expires_at
                else None
            ),
        }

    def get_frozen_config(self) -> ClusterConfigFrozen:
        """Return an immutable snapshot of the current config.

        Useful for safely passing config to background jobs (BC-004).
        """
        return ClusterConfigFrozen(
            min_similarity=self._config.min_similarity,
            max_cluster_size=self._config.max_cluster_size,
            cluster_ttl_hours=self._config.cluster_ttl_hours,
            max_clusters_per_company=self._config.max_clusters_per_company,
            embedding_dimension=self._config.embedding_dimension,
        )

    # ── Internal Helpers ───────────────────────────────────────

    @staticmethod
    def _normalize_tickets(tickets: List[Any]) -> List[TicketInput]:
        """Normalize various ticket formats to TicketInput objects.

        Accepts:
        - TicketInput objects (passed through)
        - Dicts with keys: ticket_id, text, confidence, intent_label
        - Any object with ticket_id attribute and text attribute

        Returns:
            List of TicketInput objects. Invalid entries are skipped.
        """
        normalized: List[TicketInput] = []

        for ticket in tickets:
            try:
                if isinstance(ticket, TicketInput):
                    normalized.append(ticket)
                elif isinstance(ticket, dict):
                    normalized.append(
                        TicketInput(
                            ticket_id=str(ticket.get("ticket_id", "")),
                            text=str(ticket.get("text", "")),
                            confidence=float(ticket.get("confidence", 0.0)),
                            intent_label=str(ticket.get("intent_label", "")),
                            metadata=dict(ticket.get("metadata", {})),
                        )
                    )
                elif hasattr(ticket, "ticket_id"):
                    normalized.append(
                        TicketInput(
                            ticket_id=str(ticket.ticket_id),
                            text=str(getattr(ticket, "text", "")),
                            confidence=float(
                                getattr(ticket, "confidence", 0.0)
                            ),
                            intent_label=str(
                                getattr(ticket, "intent_label", "")
                            ),
                        )
                    )
            except Exception:
                # BC-008: skip invalid tickets silently
                continue

        return normalized

    @staticmethod
    def _compute_cluster_center(
        ticket_ids: List[str],
        embeddings: Dict[str, List[float]],
    ) -> List[float]:
        """Compute the centroid of ticket embeddings in a cluster.

        Args:
            ticket_ids: IDs of tickets in the cluster.
            embeddings: Mapping of ticket_id to embedding vector.

        Returns:
            Centroid embedding vector.
        """
        cluster_embeddings = [
            embeddings[tid]
            for tid in ticket_ids
            if tid in embeddings and embeddings[tid]
        ]

        if not cluster_embeddings:
            return []

        dim = len(cluster_embeddings[0])
        center = [0.0] * dim
        n = len(cluster_embeddings)

        for emb in cluster_embeddings:
            # Pad if needed
            if len(emb) < dim:
                emb = emb + [0.0] * (dim - len(emb))
            for i in range(dim):
                center[i] += emb[i]

        center = [c / n for c in center]

        # Normalize to unit vector
        magnitude = math.sqrt(sum(c * c for c in center))
        if magnitude > 1e-10:
            center = [c / magnitude for c in center]

        return center
