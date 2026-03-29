# Trace Manager - Week 50 Builder 2
# Distributed tracing

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from enum import Enum
import uuid


class SpanStatus(Enum):
    STARTED = "started"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Span:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    trace_id: str = ""
    parent_id: Optional[str] = None
    operation: str = ""
    status: SpanStatus = SpanStatus.STARTED
    start_time: datetime = field(default_factory=datetime.utcnow)
    end_time: Optional[datetime] = None
    duration_ms: float = 0.0
    tags: Dict[str, str] = field(default_factory=dict)
    logs: List[Dict[str, Any]] = field(default_factory=list)


class TraceManager:
    """Manages distributed traces"""

    def __init__(self):
        self._spans: Dict[str, Span] = {}
        self._traces: Dict[str, List[str]] = {}
        self._active: Dict[str, str] = {}
        self._metrics = {"total_spans": 0, "total_traces": 0, "avg_duration_ms": 0.0}

    def start_trace(self, operation: str, tags: Optional[Dict[str, str]] = None) -> Span:
        """Start a new trace"""
        trace_id = str(uuid.uuid4())
        span = Span(
            trace_id=trace_id,
            operation=operation,
            tags=tags or {}
        )
        self._spans[span.id] = span
        self._traces[trace_id] = [span.id]
        self._active[trace_id] = span.id
        self._metrics["total_traces"] += 1
        self._metrics["total_spans"] += 1
        return span

    def start_span(
        self,
        trace_id: str,
        parent_id: str,
        operation: str
    ) -> Optional[Span]:
        """Start a child span"""
        if trace_id not in self._traces:
            return None

        span = Span(
            trace_id=trace_id,
            parent_id=parent_id,
            operation=operation
        )
        self._spans[span.id] = span
        self._traces[trace_id].append(span.id)
        self._metrics["total_spans"] += 1
        return span

    def end_span(self, span_id: str, status: SpanStatus = SpanStatus.COMPLETED) -> bool:
        """End a span"""
        span = self._spans.get(span_id)
        if not span:
            return False

        span.end_time = datetime.utcnow()
        span.duration_ms = (span.end_time - span.start_time).total_seconds() * 1000
        span.status = status
        return True

    def log_to_span(self, span_id: str, message: str) -> bool:
        """Add log to span"""
        span = self._spans.get(span_id)
        if not span:
            return False
        span.logs.append({
            "timestamp": datetime.utcnow().isoformat(),
            "message": message
        })
        return True

    def get_trace(self, trace_id: str) -> List[Span]:
        """Get all spans for a trace"""
        span_ids = self._traces.get(trace_id, [])
        return [self._spans[sid] for sid in span_ids if sid in self._spans]

    def get_span(self, span_id: str) -> Optional[Span]:
        """Get a span by ID"""
        return self._spans.get(span_id)

    def get_slow_traces(self, threshold_ms: float) -> List[str]:
        """Get traces exceeding duration threshold"""
        slow = []
        for trace_id, span_ids in self._traces.items():
            for sid in span_ids:
                span = self._spans.get(sid)
                if span and span.duration_ms > threshold_ms:
                    slow.append(trace_id)
                    break
        return slow

    def get_metrics(self) -> Dict[str, Any]:
        return self._metrics.copy()

    def cleanup_old(self, hours: int = 24) -> int:
        """Remove old traces"""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        to_remove = [
            sid for sid, span in self._spans.items()
            if span.start_time < cutoff
        ]
        for sid in to_remove:
            span = self._spans.pop(sid)
            if span.trace_id in self._traces:
                self._traces[span.trace_id] = [
                    s for s in self._traces[span.trace_id] if s != sid
                ]
                if not self._traces[span.trace_id]:
                    del self._traces[span.trace_id]
        return len(to_remove)
