"""
Latency Manager for Smart Router
Latency tracking, SLA enforcement, and prediction
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import statistics
import logging

logger = logging.getLogger(__name__)


class LatencyStatus(Enum):
    """Latency status levels"""
    FAST = "fast"
    NORMAL = "normal"
    SLOW = "slow"
    CRITICAL = "critical"


@dataclass
class LatencyRecord:
    """Single latency record"""
    timestamp: datetime
    model: str
    latency_ms: float
    client_id: str
    session_id: str
    success: bool = True


@dataclass
class LatencyStats:
    """Latency statistics"""
    model: str
    avg_ms: float
    p50_ms: float
    p95_ms: float
    p99_ms: float
    min_ms: float
    max_ms: float
    sample_count: int


class LatencyManager:
    """
    Manages latency tracking and SLA enforcement.
    Supports latency-based routing and auto-scaling triggers.
    """
    
    # SLA targets
    DEFAULT_SLA_MS = 500  # P95 target
    CRITICAL_LATENCY_MS = 1000
    
    # Latency thresholds
    FAST_THRESHOLD = 100
    NORMAL_THRESHOLD = 300
    SLOW_THRESHOLD = 500
    
    def __init__(self, sla_target_ms: float = None):
        self.sla_target = sla_target_ms or self.DEFAULT_SLA_MS
        self._records: List[LatencyRecord] = []
        self._model_latencies: Dict[str, List[float]] = {}
        self._client_sla: Dict[str, float] = {}
        self._slow_model_threshold: Dict[str, float] = {}
        self._initialized = True
    
    def record_latency(
        self,
        model: str,
        latency_ms: float,
        client_id: str,
        session_id: str,
        success: bool = True
    ) -> LatencyStatus:
        """
        Record latency for a query.
        
        Args:
            model: Model name
            latency_ms: Latency in milliseconds
            client_id: Client identifier
            session_id: Session identifier
            success: Whether query succeeded
            
        Returns:
            LatencyStatus
        """
        record = LatencyRecord(
            timestamp=datetime.now(),
            model=model,
            latency_ms=latency_ms,
            client_id=client_id,
            session_id=session_id,
            success=success
        )
        
        self._records.append(record)
        
        # Track per-model latencies
        if model not in self._model_latencies:
            self._model_latencies[model] = []
        self._model_latencies[model].append(latency_ms)
        
        # Keep last 1000 records per model
        if len(self._model_latencies[model]) > 1000:
            self._model_latencies[model] = self._model_latencies[model][-1000:]
        
        # Determine status
        status = self._get_status(latency_ms)
        
        # Check for slow model
        self._check_slow_model(model)
        
        logger.debug(f"Recorded latency: {latency_ms:.1f}ms for {model} ({status.value})")
        
        return status
    
    def _get_status(self, latency_ms: float) -> LatencyStatus:
        """Determine latency status."""
        if latency_ms <= self.FAST_THRESHOLD:
            return LatencyStatus.FAST
        elif latency_ms <= self.NORMAL_THRESHOLD:
            return LatencyStatus.NORMAL
        elif latency_ms <= self.SLOW_THRESHOLD:
            return LatencyStatus.SLOW
        else:
            return LatencyStatus.CRITICAL
    
    def _check_slow_model(self, model: str) -> None:
        """Check if model is consistently slow."""
        latencies = self._model_latencies.get(model, [])
        
        if len(latencies) < 10:
            return
        
        # Check recent average
        recent = latencies[-10:]
        avg = statistics.mean(recent)
        
        # Update threshold
        self._slow_model_threshold[model] = avg
        
        if avg > self.sla_target:
            logger.warning(f"Model {model} is slow: avg {avg:.1f}ms")
    
    def get_stats(self, model: str) -> Optional[LatencyStats]:
        """
        Get latency statistics for a model.
        
        Args:
            model: Model name
            
        Returns:
            LatencyStats or None
        """
        latencies = self._model_latencies.get(model, [])
        
        if not latencies:
            return None
        
        sorted_latencies = sorted(latencies)
        n = len(sorted_latencies)
        
        return LatencyStats(
            model=model,
            avg_ms=statistics.mean(latencies),
            p50_ms=sorted_latencies[int(n * 0.5)],
            p95_ms=sorted_latencies[int(n * 0.95)],
            p99_ms=sorted_latencies[int(n * 0.99)],
            min_ms=min(latencies),
            max_ms=max(latencies),
            sample_count=n
        )
    
    def get_fastest_models(
        self,
        models: List[str],
        max_latency_ms: Optional[float] = None
    ) -> List[str]:
        """
        Get models sorted by latency.
        
        Args:
            models: List of model names
            max_latency_ms: Maximum acceptable latency
            
        Returns:
            Sorted list of models
        """
        model_latencies = []
        
        for model in models:
            latencies = self._model_latencies.get(model, [])
            
            if latencies:
                avg = statistics.mean(latencies[-100:])  # Recent average
            else:
                # No data, use default
                avg = 200
            
            if max_latency_ms is None or avg <= max_latency_ms:
                model_latencies.append((model, avg))
        
        # Sort by latency
        model_latencies.sort(key=lambda x: x[1])
        
        return [m for m, _ in model_latencies]
    
    def predict_latency(
        self,
        model: str,
        query_length: int = 50
    ) -> float:
        """
        Predict latency for a query.
        
        Args:
            model: Model name
            query_length: Query word count
            
        Returns:
            Predicted latency in ms
        """
        latencies = self._model_latencies.get(model, [])
        
        if not latencies:
            # Default prediction
            return 200 + query_length * 2
        
        # Base latency from history
        base = statistics.median(latencies[-50:]) if len(latencies) >= 10 else statistics.mean(latencies)
        
        # Adjust for query length
        # Longer queries take more time
        length_factor = 1 + (query_length - 20) * 0.01  # 1% per word over 20
        
        return base * max(0.8, length_factor)
    
    def check_sla(
        self,
        client_id: str,
        latency_ms: float
    ) -> tuple[bool, float]:
        """
        Check if latency meets SLA.
        
        Args:
            client_id: Client identifier
            latency_ms: Latency in milliseconds
            
        Returns:
            Tuple of (met_sla, target_ms)
        """
        target = self._client_sla.get(client_id, self.sla_target)
        
        return latency_ms <= target, target
    
    def set_client_sla(
        self,
        client_id: str,
        sla_ms: float
    ) -> None:
        """Set SLA target for a client."""
        self._client_sla[client_id] = sla_ms
        logger.info(f"Set SLA for {client_id}: {sla_ms}ms")
    
    def get_slow_models(self) -> List[str]:
        """Get list of slow models."""
        slow = []
        
        for model, threshold in self._slow_model_threshold.items():
            if threshold > self.sla_target:
                slow.append(model)
        
        return slow
    
    def get_latency_based_model(
        self,
        models: List[str],
        sla_ms: Optional[float] = None
    ) -> str:
        """
        Select model based on latency requirements.
        
        Args:
            models: Candidate models
            sla_ms: Maximum latency
            
        Returns:
            Selected model
        """
        if not models:
            return 'junior'
        
        sla = sla_ms or self.sla_target
        
        # Get models under SLA
        fastest = self.get_fastest_models(models, max_latency_ms=sla)
        
        if fastest:
            return fastest[0]
        
        # No model under SLA, return fastest
        all_fastest = self.get_fastest_models(models)
        return all_fastest[0] if all_fastest else models[0]
    
    def get_sla_report(
        self,
        hours: int = 24
    ) -> Dict[str, Any]:
        """
        Get SLA compliance report.
        
        Args:
            hours: Hours to include
            
        Returns:
            SLA report dict
        """
        cutoff = datetime.now() - timedelta(hours=hours)
        
        records = [r for r in self._records if r.timestamp >= cutoff]
        
        if not records:
            return {'compliance_rate': 1.0, 'total_queries': 0}
        
        # Calculate compliance
        compliant = sum(1 for r in records if r.latency_ms <= self.sla_target)
        total = len(records)
        
        return {
            'compliance_rate': compliant / total,
            'total_queries': total,
            'compliant_queries': compliant,
            'p95_latency': sorted(r.latency_ms for r in records)[int(total * 0.95)] if total > 0 else 0,
            'avg_latency': statistics.mean(r.latency_ms for r in records),
        }
    
    def is_initialized(self) -> bool:
        """Check if manager is initialized."""
        return self._initialized
    
    def get_stats_summary(self) -> Dict[str, Any]:
        """Get manager statistics."""
        return {
            'total_records': len(self._records),
            'models_tracked': len(self._model_latencies),
            'sla_target': self.sla_target,
            'slow_models': len(self.get_slow_models()),
        }
