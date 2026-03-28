"""
Enterprise Security Hardening - Anomaly Detector
Advanced anomaly detection system with baseline learning and statistical analysis
"""
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import uuid
import threading
from collections import defaultdict
import math


class AnomalyType(str, Enum):
    """Types of anomalies"""
    BEHAVIORAL = "behavioral"
    TRAFFIC = "traffic"
    ACCESS = "access"
    PERFORMANCE = "performance"
    NETWORK = "network"
    AUTHENTICATION = "authentication"
    DATA_ACCESS = "data_access"
    API_USAGE = "api_usage"
    RESOURCE_UTILIZATION = "resource_utilization"
    TIME_BASED = "time_based"


class AnomalySeverity(str, Enum):
    """Anomaly severity levels"""
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AnomalyStatus(str, Enum):
    """Anomaly status"""
    DETECTED = "detected"
    CONFIRMED = "confirmed"
    INVESTIGATING = "investigating"
    RESOLVED = "resolved"
    FALSE_POSITIVE = "false_positive"
    IGNORED = "ignored"


@dataclass
class Baseline:
    """Statistical baseline for anomaly detection"""
    baseline_id: str = field(default_factory=lambda: f"baseline_{uuid.uuid4().hex[:8]}")
    metric_name: str = ""
    mean: float = 0.0
    std_dev: float = 0.0
    min_value: float = 0.0
    max_value: float = 0.0
    percentiles: Dict[int, float] = field(default_factory=dict)
    sample_count: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    learning_period_days: int = 7
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_within_normal(self, value: float, std_deviations: float = 2.0) -> bool:
        """Check if value is within normal range"""
        if self.std_dev == 0:
            return value == self.mean
        z_score = abs(value - self.mean) / self.std_dev
        return z_score <= std_deviations

    def get_z_score(self, value: float) -> float:
        """Calculate z-score for a value"""
        if self.std_dev == 0:
            return 0.0
        return (value - self.mean) / self.std_dev

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "baseline_id": self.baseline_id,
            "metric_name": self.metric_name,
            "mean": self.mean,
            "std_dev": self.std_dev,
            "min_value": self.min_value,
            "max_value": self.max_value,
            "percentiles": self.percentiles,
            "sample_count": self.sample_count,
            "learning_period_days": self.learning_period_days
        }


@dataclass
class Anomaly:
    """Detected anomaly data"""
    anomaly_id: str = field(default_factory=lambda: f"anomaly_{uuid.uuid4().hex[:12]}")
    anomaly_type: AnomalyType = AnomalyType.BEHAVIORAL
    severity: AnomalySeverity = AnomalySeverity.MEDIUM
    status: AnomalyStatus = AnomalyStatus.DETECTED
    score: float = 0.0
    threshold: float = 0.0
    metric_name: str = ""
    observed_value: float = 0.0
    expected_value: float = 0.0
    deviation: float = 0.0
    source: str = ""
    source_ip: Optional[str] = None
    user_id: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None
    baseline_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "anomaly_id": self.anomaly_id,
            "anomaly_type": self.anomaly_type.value,
            "severity": self.severity.value,
            "status": self.status.value,
            "score": self.score,
            "threshold": self.threshold,
            "metric_name": self.metric_name,
            "observed_value": self.observed_value,
            "expected_value": self.expected_value,
            "deviation": self.deviation,
            "source": self.source,
            "source_ip": self.source_ip,
            "user_id": self.user_id,
            "timestamp": self.timestamp.isoformat(),
            "baseline_id": self.baseline_id
        }


class AnomalyDetector:
    """
    Advanced anomaly detection system with baseline learning,
    statistical analysis, and real-time monitoring capabilities.
    """

    DEFAULT_THRESHOLDS = {
        "traffic_spike": 3.0,  # standard deviations
        "access_anomaly": 2.5,
        "performance_degradation": 2.0,
        "behavioral_deviation": 2.5,
        "api_usage_spike": 3.0,
        "authentication_failure": 2.0
    }

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.anomalies: Dict[str, Anomaly] = {}
        self.baselines: Dict[str, Baseline] = {}
        self._samples: Dict[str, List[float]] = defaultdict(list)
        self._lock = threading.RLock()
        self._detection_stats = defaultdict(int)
        self._thresholds = {**self.DEFAULT_THRESHOLDS, **self.config.get("thresholds", {})}
        self._learning_mode = self.config.get("learning_mode", True)
        self._max_samples = self.config.get("max_samples", 10000)
        
        # Initialize default baselines
        self._init_default_baselines()

    def _init_default_baselines(self) -> None:
        """Initialize default baseline metrics"""
        default_metrics = [
            "requests_per_minute",
            "avg_response_time_ms",
            "error_rate",
            "auth_failures_per_hour",
            "data_transfer_mb_per_hour",
            "api_calls_per_minute"
        ]
        
        for metric in default_metrics:
            self.baselines[metric] = Baseline(metric_name=metric)

    def learn_baseline(
        self,
        metric_name: str,
        values: List[float],
        learning_period_days: int = 7
    ) -> Baseline:
        """
        Learn baseline statistics from historical values.
        Calculates mean, std_dev, percentiles, etc.
        """
        if not values:
            return self.baselines.get(metric_name, Baseline(metric_name=metric_name))
        
        n = len(values)
        mean = sum(values) / n
        
        # Calculate standard deviation
        variance = sum((x - mean) ** 2 for x in values) / n
        std_dev = math.sqrt(variance) if variance > 0 else 0
        
        # Calculate percentiles
        sorted_values = sorted(values)
        percentiles = {
            25: self._percentile(sorted_values, 25),
            50: self._percentile(sorted_values, 50),
            75: self._percentile(sorted_values, 75),
            90: self._percentile(sorted_values, 90),
            95: self._percentile(sorted_values, 95),
            99: self._percentile(sorted_values, 99)
        }
        
        baseline = Baseline(
            metric_name=metric_name,
            mean=mean,
            std_dev=std_dev,
            min_value=min(values),
            max_value=max(values),
            percentiles=percentiles,
            sample_count=n,
            learning_period_days=learning_period_days
        )
        
        with self._lock:
            self.baselines[metric_name] = baseline
        
        return baseline

    def _percentile(self, sorted_values: List[float], p: int) -> float:
        """Calculate percentile from sorted values"""
        if not sorted_values:
            return 0.0
        k = (len(sorted_values) - 1) * p / 100
        f = math.floor(k)
        c = math.ceil(k)
        if f == c:
            return sorted_values[int(k)]
        return sorted_values[int(f)] * (c - k) + sorted_values[int(c)] * (k - f)

    def update_baseline(self, metric_name: str, value: float) -> Baseline:
        """Update baseline with new sample value"""
        with self._lock:
            self._samples[metric_name].append(value)
            
            # Limit sample size
            if len(self._samples[metric_name]) > self._max_samples:
                self._samples[metric_name] = self._samples[metric_name][-self._max_samples:]
            
            # Recalculate baseline if in learning mode
            if self._learning_mode and len(self._samples[metric_name]) >= 30:
                return self.learn_baseline(metric_name, self._samples[metric_name])
            
            return self.baselines.get(metric_name, Baseline(metric_name=metric_name))

    def detect_anomalies(
        self,
        metric_name: str,
        value: float,
        source: str = "",
        source_ip: Optional[str] = None,
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[Anomaly]:
        """
        Detect anomalies by comparing value against baseline.
        Returns Anomaly if deviation exceeds threshold.
        """
        baseline = self.baselines.get(metric_name)
        if not baseline:
            baseline = Baseline(metric_name=metric_name)
            with self._lock:
                self.baselines[metric_name] = baseline
        
        # Update baseline with new sample
        self.update_baseline(metric_name, value)
        
        # Check for anomaly
        threshold = self._thresholds.get(metric_name, 2.5)
        
        if baseline.std_dev > 0:
            z_score = baseline.get_z_score(value)
            
            if abs(z_score) > threshold:
                # Determine anomaly type based on metric
                anomaly_type = self._determine_anomaly_type(metric_name)
                
                # Determine severity based on z-score
                severity = self._determine_severity(abs(z_score))
                
                anomaly = Anomaly(
                    anomaly_type=anomaly_type,
                    severity=severity,
                    score=abs(z_score),
                    threshold=threshold,
                    metric_name=metric_name,
                    observed_value=value,
                    expected_value=baseline.mean,
                    deviation=value - baseline.mean,
                    source=source,
                    source_ip=source_ip,
                    user_id=user_id,
                    baseline_id=baseline.baseline_id,
                    details={
                        "z_score": z_score,
                        "percentile": self._find_percentile(value, baseline)
                    },
                    metadata=metadata or {}
                )
                
                with self._lock:
                    self.anomalies[anomaly.anomaly_id] = anomaly
                    self._detection_stats[anomaly_type.value] += 1
                
                return anomaly
        
        return None

    def _determine_anomaly_type(self, metric_name: str) -> AnomalyType:
        """Determine anomaly type based on metric name"""
        type_mapping = {
            "requests": AnomalyType.TRAFFIC,
            "traffic": AnomalyType.TRAFFIC,
            "response_time": AnomalyType.PERFORMANCE,
            "error": AnomalyType.PERFORMANCE,
            "auth": AnomalyType.AUTHENTICATION,
            "login": AnomalyType.AUTHENTICATION,
            "api": AnomalyType.API_USAGE,
            "data": AnomalyType.DATA_ACCESS,
            "access": AnomalyType.ACCESS,
            "cpu": AnomalyType.RESOURCE_UTILIZATION,
            "memory": AnomalyType.RESOURCE_UTILIZATION
        }
        
        for key, atype in type_mapping.items():
            if key in metric_name.lower():
                return atype
        
        return AnomalyType.BEHAVIORAL

    def _determine_severity(self, z_score: float) -> AnomalySeverity:
        """Determine severity based on z-score deviation"""
        if z_score >= 5.0:
            return AnomalySeverity.CRITICAL
        elif z_score >= 4.0:
            return AnomalySeverity.HIGH
        elif z_score >= 3.0:
            return AnomalySeverity.MEDIUM
        elif z_score >= 2.0:
            return AnomalySeverity.LOW
        return AnomalySeverity.INFO

    def _find_percentile(self, value: float, baseline: Baseline) -> float:
        """Find approximate percentile of value"""
        for p in sorted(baseline.percentiles.keys(), reverse=True):
            if value >= baseline.percentiles[p]:
                return p
        return 0

    def detect_traffic_anomaly(
        self,
        requests_per_minute: float,
        source_ip: Optional[str] = None
    ) -> Optional[Anomaly]:
        """Detect traffic anomalies"""
        return self.detect_anomalies(
            metric_name="requests_per_minute",
            value=requests_per_minute,
            source="traffic_monitor",
            source_ip=source_ip
        )

    def detect_performance_anomaly(
        self,
        response_time_ms: float,
        endpoint: str = ""
    ) -> Optional[Anomaly]:
        """Detect performance anomalies"""
        return self.detect_anomalies(
            metric_name="avg_response_time_ms",
            value=response_time_ms,
            source="performance_monitor",
            metadata={"endpoint": endpoint}
        )

    def detect_access_anomaly(
        self,
        user_id: str,
        access_count: int,
        resource_type: str = ""
    ) -> Optional[Anomaly]:
        """Detect access pattern anomalies"""
        return self.detect_anomalies(
            metric_name="access_count_per_hour",
            value=float(access_count),
            source="access_monitor",
            user_id=user_id,
            metadata={"resource_type": resource_type}
        )

    def detect_api_usage_anomaly(
        self,
        api_calls_per_minute: float,
        api_endpoint: str = "",
        source_ip: Optional[str] = None
    ) -> Optional[Anomaly]:
        """Detect API usage anomalies"""
        return self.detect_anomalies(
            metric_name="api_calls_per_minute",
            value=api_calls_per_minute,
            source="api_monitor",
            source_ip=source_ip,
            metadata={"api_endpoint": api_endpoint}
        )

    def detect_authentication_anomaly(
        self,
        auth_failures: int,
        user_id: Optional[str] = None,
        source_ip: Optional[str] = None
    ) -> Optional[Anomaly]:
        """Detect authentication anomalies"""
        return self.detect_anomalies(
            metric_name="auth_failures_per_hour",
            value=float(auth_failures),
            source="auth_monitor",
            user_id=user_id,
            source_ip=source_ip
        )

    def detect_behavioral_anomaly(
        self,
        user_id: str,
        behavior_score: float,
        activity_type: str = ""
    ) -> Optional[Anomaly]:
        """Detect behavioral anomalies"""
        return self.detect_anomalies(
            metric_name="behavior_score",
            value=behavior_score,
            source="behavior_analyzer",
            user_id=user_id,
            metadata={"activity_type": activity_type}
        )

    def get_anomaly(self, anomaly_id: str) -> Optional[Anomaly]:
        """Get an anomaly by ID"""
        return self.anomalies.get(anomaly_id)

    def get_anomalies(
        self,
        anomaly_type: Optional[AnomalyType] = None,
        severity: Optional[AnomalySeverity] = None,
        status: Optional[AnomalyStatus] = None,
        user_id: Optional[str] = None,
        source_ip: Optional[str] = None,
        limit: int = 100
    ) -> List[Anomaly]:
        """Get anomalies with optional filters"""
        results = list(self.anomalies.values())
        
        if anomaly_type:
            results = [a for a in results if a.anomaly_type == anomaly_type]
        if severity:
            results = [a for a in results if a.severity == severity]
        if status:
            results = [a for a in results if a.status == status]
        if user_id:
            results = [a for a in results if a.user_id == user_id]
        if source_ip:
            results = [a for a in results if a.source_ip == source_ip]
        
        return sorted(results, key=lambda a: a.timestamp, reverse=True)[:limit]

    def resolve_anomaly(self, anomaly_id: str, status: AnomalyStatus = AnomalyStatus.RESOLVED) -> bool:
        """Mark an anomaly as resolved"""
        with self._lock:
            if anomaly_id in self.anomalies:
                self.anomalies[anomaly_id].status = status
                self.anomalies[anomaly_id].resolved_at = datetime.utcnow()
                return True
        return False

    def get_baseline(self, metric_name: str) -> Optional[Baseline]:
        """Get baseline for a metric"""
        return self.baselines.get(metric_name)

    def get_all_baselines(self) -> Dict[str, Baseline]:
        """Get all baselines"""
        return dict(self.baselines)

    def set_threshold(self, metric_name: str, threshold: float) -> None:
        """Set custom threshold for a metric"""
        with self._lock:
            self._thresholds[metric_name] = threshold

    def get_threshold(self, metric_name: str) -> float:
        """Get threshold for a metric"""
        return self._thresholds.get(metric_name, 2.5)

    def enable_learning_mode(self) -> None:
        """Enable baseline learning mode"""
        self._learning_mode = True

    def disable_learning_mode(self) -> None:
        """Disable baseline learning mode"""
        self._learning_mode = False

    def get_statistics(self) -> Dict[str, Any]:
        """Get detection statistics"""
        return {
            "total_anomalies": len(self.anomalies),
            "by_type": dict(self._detection_stats),
            "by_severity": {
                "critical": len([a for a in self.anomalies.values() if a.severity == AnomalySeverity.CRITICAL]),
                "high": len([a for a in self.anomalies.values() if a.severity == AnomalySeverity.HIGH]),
                "medium": len([a for a in self.anomalies.values() if a.severity == AnomalySeverity.MEDIUM]),
                "low": len([a for a in self.anomalies.values() if a.severity == AnomalySeverity.LOW]),
                "info": len([a for a in self.anomalies.values() if a.severity == AnomalySeverity.INFO])
            },
            "by_status": {
                "detected": len([a for a in self.anomalies.values() if a.status == AnomalyStatus.DETECTED]),
                "confirmed": len([a for a in self.anomalies.values() if a.status == AnomalyStatus.CONFIRMED]),
                "investigating": len([a for a in self.anomalies.values() if a.status == AnomalyStatus.INVESTIGATING]),
                "resolved": len([a for a in self.anomalies.values() if a.status == AnomalyStatus.RESOLVED]),
                "false_positive": len([a for a in self.anomalies.values() if a.status == AnomalyStatus.FALSE_POSITIVE])
            },
            "baselines_count": len(self.baselines),
            "learning_mode": self._learning_mode
        }

    def clear_old_anomalies(self, days: int = 30) -> int:
        """Clear anomalies older than specified days"""
        cutoff = datetime.utcnow() - timedelta(days=days)
        removed = 0
        
        with self._lock:
            to_remove = [
                aid for aid, a in self.anomalies.items()
                if a.timestamp < cutoff and a.status in [AnomalyStatus.RESOLVED, AnomalyStatus.FALSE_POSITIVE]
            ]
            for aid in to_remove:
                del self.anomalies[aid]
                removed += 1
        
        return removed

    def export_anomalies(self, format: str = "dict") -> Any:
        """Export anomalies for reporting"""
        if format == "dict":
            return [a.to_dict() for a in self.anomalies.values()]
        return list(self.anomalies.values())

    def analyze_correlation(self, anomalies: List[Anomaly]) -> Dict[str, Any]:
        """Analyze correlation between anomalies"""
        if len(anomalies) < 2:
            return {"correlation": "insufficient_data"}
        
        # Group by source IP
        ip_groups: Dict[str, List[Anomaly]] = defaultdict(list)
        for a in anomalies:
            if a.source_ip:
                ip_groups[a.source_ip].append(a)
        
        # Group by user
        user_groups: Dict[str, List[Anomaly]] = defaultdict(list)
        for a in anomalies:
            if a.user_id:
                user_groups[a.user_id].append(a)
        
        # Group by time window (1 hour)
        time_groups: Dict[str, List[Anomaly]] = defaultdict(list)
        for a in anomalies:
            hour_key = a.timestamp.strftime("%Y-%m-%d %H:00")
            time_groups[hour_key].append(a)
        
        return {
            "total_anomalies": len(anomalies),
            "unique_ips": len(ip_groups),
            "unique_users": len(user_groups),
            "time_windows": len(time_groups),
            "ip_correlation": {ip: len(anoms) for ip, anoms in ip_groups.items()},
            "user_correlation": {user: len(anoms) for user, anoms in user_groups.items()},
            "time_distribution": {t: len(anoms) for t, anoms in time_groups.items()}
        }
