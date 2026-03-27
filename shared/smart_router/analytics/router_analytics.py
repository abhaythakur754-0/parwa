"""
Router Analytics for Smart Router
Routing accuracy tracking, tier distribution, and performance metrics
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import statistics
import logging

logger = logging.getLogger(__name__)


class MetricType(Enum):
    """Metric types"""
    ACCURACY = "accuracy"
    LATENCY = "latency"
    COST = "cost"
    THROUGHPUT = "throughput"
    ERROR_RATE = "error_rate"
    SATISFACTION = "satisfaction"


@dataclass
class RoutingEvent:
    """Single routing event"""
    timestamp: datetime
    session_id: str
    client_id: str
    query: str
    predicted_tier: str
    actual_tier: str
    model_used: str
    latency_ms: float
    cost: float
    success: bool
    user_satisfied: Optional[bool] = None
    fallback_used: bool = False


@dataclass
class AccuracyMetrics:
    """Accuracy metrics"""
    total_routed: int
    correct_routed: int
    accuracy: float
    by_tier: Dict[str, float]
    by_intent: Dict[str, float]


@dataclass
class RouterAnalyticsReport:
    """Full analytics report"""
    period_start: datetime
    period_end: datetime
    total_queries: int
    accuracy_metrics: AccuracyMetrics
    tier_distribution: Dict[str, int]
    model_usage: Dict[str, int]
    avg_latency_ms: float
    avg_cost_per_query: float
    error_rate: float
    fallback_rate: float


class RouterAnalytics:
    """
    Tracks and analyzes router performance.
    Provides metrics for optimization and reporting.
    """
    
    # Metrics retention
    MAX_EVENTS = 10000
    AGGREGATION_INTERVALS = ['hour', 'day', 'week']
    
    def __init__(self):
        self._events: List[RoutingEvent] = []
        self._aggregated_metrics: Dict[str, Dict[str, Any]] = {}
        self._real_time_metrics: Dict[str, float] = {}
        self._initialized = True
    
    def record_routing(
        self,
        session_id: str,
        client_id: str,
        query: str,
        predicted_tier: str,
        actual_tier: str,
        model_used: str,
        latency_ms: float,
        cost: float,
        success: bool,
        user_satisfied: Optional[bool] = None,
        fallback_used: bool = False
    ) -> RoutingEvent:
        """
        Record a routing event.
        
        Args:
            session_id: Session identifier
            client_id: Client identifier
            query: User query
            predicted_tier: Predicted tier
            actual_tier: Actual correct tier
            model_used: Model that was used
            latency_ms: Query latency
            cost: Query cost
            success: Whether routing was successful
            user_satisfied: User satisfaction flag
            fallback_used: Whether fallback was used
            
        Returns:
            RoutingEvent
        """
        event = RoutingEvent(
            timestamp=datetime.now(),
            session_id=session_id,
            client_id=client_id,
            query=query,
            predicted_tier=predicted_tier,
            actual_tier=actual_tier,
            model_used=model_used,
            latency_ms=latency_ms,
            cost=cost,
            success=success,
            user_satisfied=user_satisfied,
            fallback_used=fallback_used
        )
        
        self._events.append(event)
        
        # Trim old events
        if len(self._events) > self.MAX_EVENTS:
            self._events = self._events[-self.MAX_EVENTS:]
        
        # Update real-time metrics
        self._update_real_time_metrics(event)
        
        logger.debug(f"Recorded routing event for session {session_id}")
        
        return event
    
    def _update_real_time_metrics(self, event: RoutingEvent) -> None:
        """Update real-time metrics."""
        n = len(self._events)
        
        # Running average latency
        current_avg = self._real_time_metrics.get('avg_latency', 0)
        self._real_time_metrics['avg_latency'] = (
            (current_avg * (n - 1) + event.latency_ms) / n
        )
        
        # Running average cost
        current_cost = self._real_time_metrics.get('avg_cost', 0)
        self._real_time_metrics['avg_cost'] = (
            (current_cost * (n - 1) + event.cost) / n
        )
        
        # Error rate
        errors = sum(1 for e in self._events if not e.success)
        self._real_time_metrics['error_rate'] = errors / n
    
    def track_routing_accuracy(
        self,
        events: Optional[List[RoutingEvent]] = None
    ) -> AccuracyMetrics:
        """
        Track routing accuracy.
        
        Args:
            events: Events to analyze (uses all if not provided)
            
        Returns:
            AccuracyMetrics
        """
        events = events or self._events
        
        if not events:
            return AccuracyMetrics(
                total_routed=0,
                correct_routed=0,
                accuracy=0,
                by_tier={},
                by_intent={}
            )
        
        total = len(events)
        correct = sum(1 for e in events if e.predicted_tier == e.actual_tier)
        
        # Accuracy by tier
        by_tier: Dict[str, List[bool]] = {}
        for event in events:
            if event.actual_tier not in by_tier:
                by_tier[event.actual_tier] = []
            by_tier[event.actual_tier].append(
                event.predicted_tier == event.actual_tier
            )
        
        tier_accuracy = {
            tier: sum(correct) / len(correct)
            for tier, correct in by_tier.items()
        }
        
        return AccuracyMetrics(
            total_routed=total,
            correct_routed=correct,
            accuracy=correct / total,
            by_tier=tier_accuracy,
            by_intent={}  # Would need intent data
        )
    
    def analyze_tier_distribution(
        self,
        events: Optional[List[RoutingEvent]] = None
    ) -> Dict[str, int]:
        """
        Analyze tier distribution.
        
        Args:
            events: Events to analyze
            
        Returns:
            Dict of tier to count
        """
        events = events or self._events
        
        distribution: Dict[str, int] = {}
        for event in events:
            distribution[event.predicted_tier] = (
                distribution.get(event.predicted_tier, 0) + 1
            )
        
        return distribution
    
    def track_model_usage(
        self,
        events: Optional[List[RoutingEvent]] = None
    ) -> Dict[str, int]:
        """
        Track model usage statistics.
        
        Args:
            events: Events to analyze
            
        Returns:
            Dict of model to usage count
        """
        events = events or self._events
        
        usage: Dict[str, int] = {}
        for event in events:
            usage[event.model_used] = usage.get(event.model_used, 0) + 1
        
        return usage
    
    def calculate_cost_per_query(
        self,
        events: Optional[List[RoutingEvent]] = None
    ) -> float:
        """
        Calculate average cost per query.
        
        Args:
            events: Events to analyze
            
        Returns:
            Average cost
        """
        events = events or self._events
        
        if not events:
            return 0
        
        return sum(e.cost for e in events) / len(events)
    
    def get_latency_distribution(
        self,
        events: Optional[List[RoutingEvent]] = None
    ) -> Dict[str, float]:
        """
        Get latency distribution statistics.
        
        Args:
            events: Events to analyze
            
        Returns:
            Dict with p50, p95, p99, avg, min, max
        """
        events = events or self._events
        
        if not events:
            return {}
        
        latencies = sorted(e.latency_ms for e in events)
        n = len(latencies)
        
        return {
            'p50': latencies[int(n * 0.5)],
            'p95': latencies[int(n * 0.95)],
            'p99': latencies[int(n * 0.99)],
            'avg': statistics.mean(latencies),
            'min': min(latencies),
            'max': max(latencies),
        }
    
    def log_routing_decision(
        self,
        session_id: str,
        decision: Dict[str, Any]
    ) -> None:
        """Log routing decision for debugging."""
        logger.debug(f"Routing decision for {session_id}: {decision}")
    
    def get_report(
        self,
        period_hours: int = 24
    ) -> RouterAnalyticsReport:
        """
        Get comprehensive analytics report.
        
        Args:
            period_hours: Hours to include in report
            
        Returns:
            RouterAnalyticsReport
        """
        cutoff = datetime.now() - timedelta(hours=period_hours)
        events = [e for e in self._events if e.timestamp >= cutoff]
        
        accuracy = self.track_routing_accuracy(events)
        tier_dist = self.analyze_tier_distribution(events)
        model_usage = self.track_model_usage(events)
        latency_dist = self.get_latency_distribution(events)
        
        error_rate = sum(1 for e in events if not e.success) / len(events) if events else 0
        fallback_rate = sum(1 for e in events if e.fallback_used) / len(events) if events else 0
        
        return RouterAnalyticsReport(
            period_start=cutoff,
            period_end=datetime.now(),
            total_queries=len(events),
            accuracy_metrics=accuracy,
            tier_distribution=tier_dist,
            model_usage=model_usage,
            avg_latency_ms=latency_dist.get('avg', 0),
            avg_cost_per_query=self.calculate_cost_per_query(events),
            error_rate=error_rate,
            fallback_rate=fallback_rate
        )
    
    def get_real_time_metrics(self) -> Dict[str, float]:
        """Get real-time metrics."""
        return self._real_time_metrics.copy()
    
    def aggregate_metrics(
        self,
        interval: str = 'hour'
    ) -> Dict[str, Any]:
        """
        Aggregate metrics by interval.
        
        Args:
            interval: Aggregation interval
            
        Returns:
            Aggregated metrics
        """
        key = datetime.now().strftime('%Y-%m-%d-%H' if interval == 'hour' else '%Y-%m-%d')
        
        if key in self._aggregated_metrics:
            return self._aggregated_metrics[key]
        
        events = self._events
        if not events:
            return {}
        
        aggregated = {
            'total': len(events),
            'accuracy': self.track_routing_accuracy(events).accuracy,
            'avg_latency': statistics.mean([e.latency_ms for e in events]),
            'avg_cost': statistics.mean([e.cost for e in events]),
        }
        
        self._aggregated_metrics[key] = aggregated
        
        return aggregated
    
    def is_initialized(self) -> bool:
        """Check if analytics is initialized."""
        return self._initialized
    
    def get_stats(self) -> Dict[str, Any]:
        """Get analytics statistics."""
        return {
            'total_events': len(self._events),
            'aggregated_periods': len(self._aggregated_metrics),
            'real_time_metrics': self._real_time_metrics,
        }
