"""
Data Aggregator
Enterprise Analytics & Reporting - Week 44 Builder 4
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Callable
import asyncio
import logging

logger = logging.getLogger(__name__)


class AggregationType(str, Enum):
    """Aggregation types"""
    SUM = "sum"
    AVG = "avg"
    COUNT = "count"
    MIN = "min"
    MAX = "max"
    MEDIAN = "median"
    PERCENTILE = "percentile"


class AggregationPeriod(str, Enum):
    """Aggregation periods"""
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


@dataclass
class AggregationJob:
    """Aggregation job definition"""
    id: str
    name: str
    source: str
    aggregation_type: AggregationType
    period: AggregationPeriod
    metrics: List[str]
    group_by: List[str] = field(default_factory=list)
    filters: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "source": self.source,
            "aggregation_type": self.aggregation_type.value,
            "period": self.period.value,
            "metrics": self.metrics,
            "group_by": self.group_by,
            "filters": self.filters,
            "enabled": self.enabled,
            "last_run": self.last_run.isoformat() if self.last_run else None
        }


@dataclass
class AggregationResult:
    """Result of aggregation"""
    job_id: str
    period_start: datetime
    period_end: datetime
    data: Dict[str, Any]
    records_processed: int
    executed_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "data": self.data,
            "records_processed": self.records_processed,
            "executed_at": self.executed_at.isoformat()
        }


class DataAggregator:
    """Aggregates data from multiple sources"""
    
    def __init__(self):
        self._jobs: Dict[str, AggregationJob] = {}
        self._results: Dict[str, List[AggregationResult]] = {}
        self._sources: Dict[str, Any] = {}
    
    def register_source(self, name: str, source: Any) -> None:
        """Register a data source"""
        self._sources[name] = source
    
    def create_job(
        self,
        name: str,
        source: str,
        aggregation_type: AggregationType,
        period: AggregationPeriod,
        metrics: List[str],
        group_by: Optional[List[str]] = None
    ) -> AggregationJob:
        """Create an aggregation job"""
        import uuid
        
        job = AggregationJob(
            id=str(uuid.uuid4()),
            name=name,
            source=source,
            aggregation_type=aggregation_type,
            period=period,
            metrics=metrics,
            group_by=group_by or []
        )
        
        self._jobs[job.id] = job
        return job
    
    def get_job(self, job_id: str) -> Optional[AggregationJob]:
        """Get aggregation job by ID"""
        return self._jobs.get(job_id)
    
    def list_jobs(self, enabled_only: bool = False) -> List[AggregationJob]:
        """List aggregation jobs"""
        jobs = list(self._jobs.values())
        if enabled_only:
            jobs = [j for j in jobs if j.enabled]
        return jobs
    
    async def run_job(self, job_id: str) -> Optional[AggregationResult]:
        """Run an aggregation job"""
        job = self._jobs.get(job_id)
        if not job:
            return None
        
        # Calculate period bounds
        now = datetime.utcnow()
        period_start, period_end = self._calculate_period(now, job.period)
        
        # Mock aggregation - in real impl would query source
        result = AggregationResult(
            job_id=job_id,
            period_start=period_start,
            period_end=period_end,
            data={metric: 0 for metric in job.metrics},
            records_processed=0
        )
        
        # Store result
        if job_id not in self._results:
            self._results[job_id] = []
        self._results[job_id].append(result)
        
        job.last_run = now
        return result
    
    def _calculate_period(
        self,
        now: datetime,
        period: AggregationPeriod
    ) -> tuple:
        """Calculate period start and end"""
        if period == AggregationPeriod.HOURLY:
            start = now.replace(minute=0, second=0, microsecond=0)
            end = start + timedelta(hours=1)
        elif period == AggregationPeriod.DAILY:
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=1)
        elif period == AggregationPeriod.WEEKLY:
            start = now - timedelta(days=now.weekday())
            start = start.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(weeks=1)
        else:  # MONTHLY
            start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            end = (start + timedelta(days=32)).replace(day=1)
        
        return start, end
    
    def get_results(
        self,
        job_id: str,
        limit: int = 10
    ) -> List[AggregationResult]:
        """Get aggregation results"""
        results = self._results.get(job_id, [])
        return results[-limit:]
    
    async def aggregate(
        self,
        data: List[Dict[str, Any]],
        aggregation_type: AggregationType,
        field: str,
        group_by: Optional[str] = None
    ) -> Dict[str, Any]:
        """Aggregate data"""
        if not data:
            return {}
        
        if group_by:
            # Group data first
            groups = {}
            for item in data:
                key = item.get(group_by, "unknown")
                if key not in groups:
                    groups[key] = []
                groups[key].append(item.get(field, 0))
            
            # Aggregate each group
            return {
                key: self._aggregate_values(values, aggregation_type)
                for key, values in groups.items()
            }
        else:
            values = [item.get(field, 0) for item in data]
            return {"value": self._aggregate_values(values, aggregation_type)}
    
    def _aggregate_values(
        self,
        values: List[float],
        aggregation_type: AggregationType
    ) -> float:
        """Aggregate a list of values"""
        if not values:
            return 0.0
        
        if aggregation_type == AggregationType.SUM:
            return sum(values)
        elif aggregation_type == AggregationType.AVG:
            return sum(values) / len(values)
        elif aggregation_type == AggregationType.COUNT:
            return len(values)
        elif aggregation_type == AggregationType.MIN:
            return min(values)
        elif aggregation_type == AggregationType.MAX:
            return max(values)
        elif aggregation_type == AggregationType.MEDIAN:
            sorted_values = sorted(values)
            n = len(sorted_values)
            if n % 2 == 0:
                return (sorted_values[n//2-1] + sorted_values[n//2]) / 2
            return sorted_values[n//2]
        
        return 0.0


class MetricStore:
    """Stores and retrieves aggregated metrics"""
    
    def __init__(self):
        self._metrics: Dict[str, List[Dict[str, Any]]] = {}
    
    def store(
        self,
        metric_name: str,
        value: float,
        timestamp: Optional[datetime] = None,
        tags: Optional[Dict[str, str]] = None
    ) -> None:
        """Store a metric value"""
        timestamp = timestamp or datetime.utcnow()
        
        if metric_name not in self._metrics:
            self._metrics[metric_name] = []
        
        self._metrics[metric_name].append({
            "value": value,
            "timestamp": timestamp.isoformat(),
            "tags": tags or {}
        })
    
    def get(
        self,
        metric_name: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        tags: Optional[Dict[str, str]] = None
    ) -> List[Dict[str, Any]]:
        """Get metric values"""
        values = self._metrics.get(metric_name, [])
        
        if start:
            values = [v for v in values if datetime.fromisoformat(v["timestamp"]) >= start]
        if end:
            values = [v for v in values if datetime.fromisoformat(v["timestamp"]) <= end]
        if tags:
            values = [v for v in values if all(v["tags"].get(k) == val for k, val in tags.items())]
        
        return values
    
    def get_latest(self, metric_name: str) -> Optional[Dict[str, Any]]:
        """Get latest metric value"""
        values = self._metrics.get(metric_name, [])
        return values[-1] if values else None
    
    def aggregate(
        self,
        metric_name: str,
        aggregation_type: AggregationType,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None
    ) -> float:
        """Aggregate metric values"""
        values = self.get(metric_name, start, end)
        if not values:
            return 0.0
        
        vals = [v["value"] for v in values]
        
        if aggregation_type == AggregationType.SUM:
            return sum(vals)
        elif aggregation_type == AggregationType.AVG:
            return sum(vals) / len(vals)
        elif aggregation_type == AggregationType.MIN:
            return min(vals)
        elif aggregation_type == AggregationType.MAX:
            return max(vals)
        
        return 0.0
