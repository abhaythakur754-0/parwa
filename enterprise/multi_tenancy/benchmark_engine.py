"""
Benchmark Engine

Provides benchmarking capabilities for tenant performance comparison.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)


class BenchmarkType(str, Enum):
    """Types of benchmarks"""
    PERFORMANCE = "performance"
    USAGE = "usage"
    EFFICIENCY = "efficiency"
    GROWTH = "growth"
    ENGAGEMENT = "engagement"


@dataclass
class BenchmarkResult:
    """Result of a benchmark calculation"""
    benchmark_id: str
    benchmark_type: BenchmarkType
    tenant_id: str
    score: float
    percentile: float
    rank: Optional[int] = None
    total_tenants: int = 0
    metrics: Dict[str, float] = field(default_factory=dict)
    calculated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class BenchmarkDefinition:
    """Definition of a benchmark"""
    benchmark_id: str
    name: str
    benchmark_type: BenchmarkType
    metrics: List[str]
    weights: Dict[str, float]
    description: str = ""


class BenchmarkEngine:
    """
    Engine for tenant benchmarking.

    Features:
    - Multiple benchmark types
    - Percentile scoring
    - Trend tracking
    - Privacy-preserving rankings
    """

    def __init__(self, min_tenants_for_ranking: int = 5):
        self.min_tenants_for_ranking = min_tenants_for_ranking

        # Benchmark definitions
        self._definitions: Dict[str, BenchmarkDefinition] = {}

        # Results cache
        self._results: List[BenchmarkResult] = []

        # Initialize default benchmarks
        self._initialize_benchmarks()

    def _initialize_benchmarks(self) -> None:
        """Initialize default benchmark definitions"""
        defaults = [
            BenchmarkDefinition(
                benchmark_id="overall_performance",
                name="Overall Performance",
                benchmark_type=BenchmarkType.PERFORMANCE,
                metrics=["response_time", "throughput", "error_rate"],
                weights={"response_time": 0.3, "throughput": 0.4, "error_rate": 0.3},
                description="Overall system performance score"
            ),
            BenchmarkDefinition(
                benchmark_id="usage_efficiency",
                name="Usage Efficiency",
                benchmark_type=BenchmarkType.EFFICIENCY,
                metrics=["quota_utilization", "feature_adoption", "resource_efficiency"],
                weights={"quota_utilization": 0.4, "feature_adoption": 0.3, "resource_efficiency": 0.3},
                description="How efficiently resources are used"
            ),
            BenchmarkDefinition(
                benchmark_id="growth_score",
                name="Growth Score",
                benchmark_type=BenchmarkType.GROWTH,
                metrics=["user_growth", "ticket_growth", "engagement_growth"],
                weights={"user_growth": 0.4, "ticket_growth": 0.3, "engagement_growth": 0.3},
                description="Growth trajectory score"
            )
        ]

        for d in defaults:
            self._definitions[d.benchmark_id] = d

    def calculate_benchmark(
        self,
        tenant_id: str,
        benchmark_id: str,
        metric_values: Dict[str, float]
    ) -> Optional[BenchmarkResult]:
        """Calculate benchmark score for a tenant"""
        definition = self._definitions.get(benchmark_id)
        if not definition:
            return None

        # Calculate weighted score
        score = 0
        total_weight = 0

        for metric, weight in definition.weights.items():
            if metric in metric_values:
                score += metric_values[metric] * weight
                total_weight += weight

        if total_weight == 0:
            return None

        score = score / total_weight

        result = BenchmarkResult(
            benchmark_id=benchmark_id,
            benchmark_type=definition.benchmark_type,
            tenant_id=tenant_id,
            score=score,
            percentile=0,  # Will be calculated later
            metrics=metric_values
        )

        self._results.append(result)
        return result

    def get_percentile_ranking(
        self,
        tenant_id: str,
        benchmark_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get percentile ranking for a tenant in a benchmark"""
        tenant_results = [
            r for r in self._results
            if r.benchmark_id == benchmark_id
        ]

        if len(tenant_results) < self.min_tenants_for_ranking:
            return None

        # Sort by score
        sorted_results = sorted(tenant_results, key=lambda x: x.score, reverse=True)

        # Find tenant position
        for rank, result in enumerate(sorted_results, 1):
            if result.tenant_id == tenant_id:
                percentile = (1 - (rank - 1) / len(sorted_results)) * 100

                return {
                    "tenant_id": tenant_id,
                    "benchmark_id": benchmark_id,
                    "score": result.score,
                    "rank": rank,
                    "total_tenants": len(sorted_results),
                    "percentile": round(percentile, 1)
                }

        return None

    def get_top_performers(
        self,
        benchmark_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get top performers (anonymized) for a benchmark"""
        results = [
            r for r in self._results
            if r.benchmark_id == benchmark_id
        ]

        if len(results) < self.min_tenants_for_ranking:
            return []

        # Sort by score and take top
        sorted_results = sorted(results, key=lambda x: x.score, reverse=True)[:limit]

        return [
            {
                "rank": i + 1,
                "score": r.score,
                "percentile": round((1 - i / len(results)) * 100, 1)
            }
            for i, r in enumerate(sorted_results)
        ]

    def get_benchmark_distribution(
        self,
        benchmark_id: str
    ) -> Dict[str, Any]:
        """Get distribution of scores for a benchmark"""
        results = [
            r for r in self._results
            if r.benchmark_id == benchmark_id
        ]

        if not results:
            return {"error": "No results found"}

        scores = [r.score for r in results]

        return {
            "benchmark_id": benchmark_id,
            "count": len(scores),
            "min": min(scores),
            "max": max(scores),
            "avg": sum(scores) / len(scores),
            "distribution": {
                "top_10": len([s for s in scores if s >= 90]),
                "top_25": len([s for s in scores if s >= 75]),
                "median": len([s for s in scores if 40 <= s < 60]),
                "bottom_25": len([s for s in scores if s < 25])
            }
        }

    def add_benchmark_definition(
        self,
        benchmark_id: str,
        name: str,
        benchmark_type: BenchmarkType,
        metrics: List[str],
        weights: Dict[str, float],
        description: str = ""
    ) -> BenchmarkDefinition:
        """Add a new benchmark definition"""
        definition = BenchmarkDefinition(
            benchmark_id=benchmark_id,
            name=name,
            benchmark_type=benchmark_type,
            metrics=metrics,
            weights=weights,
            description=description
        )

        self._definitions[benchmark_id] = definition
        return definition

    def get_benchmark_definition(self, benchmark_id: str) -> Optional[BenchmarkDefinition]:
        """Get benchmark definition"""
        return self._definitions.get(benchmark_id)

    def list_benchmarks(self) -> List[BenchmarkDefinition]:
        """List all benchmark definitions"""
        return list(self._definitions.values())

    def get_tenant_benchmarks(self, tenant_id: str) -> List[BenchmarkResult]:
        """Get all benchmark results for a tenant"""
        return [r for r in self._results if r.tenant_id == tenant_id]

    def compare_to_peers(
        self,
        tenant_id: str,
        benchmark_id: str
    ) -> Optional[Dict[str, Any]]:
        """Compare tenant to peer group (anonymized)"""
        ranking = self.get_percentile_ranking(tenant_id, benchmark_id)
        if not ranking:
            return None

        distribution = self.get_benchmark_distribution(benchmark_id)

        return {
            "tenant_id": tenant_id,
            "benchmark_id": benchmark_id,
            "tenant_score": ranking["score"],
            "tenant_percentile": ranking["percentile"],
            "average_score": distribution["avg"],
            "comparison": "above_average" if ranking["score"] > distribution["avg"] else "below_average"
        }
