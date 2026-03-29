"""
KPI Engine
Enterprise Analytics & Reporting - Week 44 Builder 2
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Callable
import math
import logging

logger = logging.getLogger(__name__)


class KPICategory(str, Enum):
    """KPI categories"""
    PERFORMANCE = "performance"
    QUALITY = "quality"
    CUSTOMER = "customer"
    OPERATIONAL = "operational"
    FINANCIAL = "financial"
    TEAM = "team"


class KPITrend(str, Enum):
    """KPI trend directions"""
    UP = "up"
    DOWN = "down"
    STABLE = "stable"
    UNKNOWN = "unknown"


class KPIStatus(str, Enum):
    """KPI status based on targets"""
    ON_TRACK = "on_track"
    AT_RISK = "at_risk"
    OFF_TRACK = "off_track"
    NO_DATA = "no_data"


@dataclass
class KPITarget:
    """KPI target configuration"""
    target_value: float
    warning_threshold: float = 0.9  # 90% of target
    critical_threshold: float = 0.7  # 70% of target
    comparison: str = "greater_than"  # greater_than, less_than, equals
    
    def evaluate(self, value: float) -> KPIStatus:
        """Evaluate value against target"""
        if self.comparison == "greater_than":
            if value >= self.target_value:
                return KPIStatus.ON_TRACK
            elif value >= self.target_value * self.warning_threshold:
                return KPIStatus.AT_RISK
            elif value >= self.target_value * self.critical_threshold:
                return KPIStatus.OFF_TRACK
            return KPIStatus.OFF_TRACK
        elif self.comparison == "less_than":
            if value <= self.target_value:
                return KPIStatus.ON_TRACK
            elif value <= self.target_value * (1 + (1 - self.warning_threshold)):
                return KPIStatus.AT_RISK
            return KPIStatus.OFF_TRACK
        else:  # equals
            if abs(value - self.target_value) < 0.01:
                return KPIStatus.ON_TRACK
            return KPIStatus.AT_RISK


@dataclass
class KPIDefinition:
    """Definition of a KPI"""
    id: str
    name: str
    description: str
    category: KPICategory
    unit: str
    calculation: str  # Formula or aggregation method
    target: Optional[KPITarget] = None
    tags: List[str] = field(default_factory=list)
    owner: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "category": self.category.value,
            "unit": self.unit,
            "calculation": self.calculation,
            "target": {
                "target_value": self.target.target_value,
                "warning_threshold": self.target.warning_threshold,
                "critical_threshold": self.target.critical_threshold,
                "comparison": self.target.comparison
            } if self.target else None,
            "tags": self.tags,
            "owner": self.owner,
            "created_at": self.created_at.isoformat()
        }


@dataclass
class KPIValue:
    """A KPI measurement value"""
    kpi_id: str
    value: float
    timestamp: datetime
    previous_value: Optional[float] = None
    target_value: Optional[float] = None
    status: KPIStatus = KPIStatus.NO_DATA
    trend: KPITrend = KPITrend.UNKNOWN
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "kpi_id": self.kpi_id,
            "value": self.value,
            "timestamp": self.timestamp.isoformat(),
            "previous_value": self.previous_value,
            "target_value": self.target_value,
            "status": self.status.value,
            "trend": self.trend.value,
            "metadata": self.metadata
        }
    
    def calculate_change(self) -> Optional[float]:
        """Calculate change from previous value"""
        if self.previous_value is None or self.previous_value == 0:
            return None
        return ((self.value - self.previous_value) / self.previous_value) * 100


class KPIEngine:
    """Engine for KPI calculations and tracking"""
    
    def __init__(self):
        self._definitions: Dict[str, KPIDefinition] = {}
        self._values: Dict[str, List[KPIValue]] = {}
        self._calculators: Dict[str, Callable] = {}
        self._register_default_kpis()
    
    def _register_default_kpis(self) -> None:
        """Register default KPIs"""
        default_kpis = [
            KPIDefinition(
                id="ticket_resolution_time",
                name="Avg Ticket Resolution Time",
                description="Average time to resolve support tickets",
                category=KPICategory.PERFORMANCE,
                unit="minutes",
                calculation="avg(resolution_time)",
                target=KPITarget(target_value=30.0, comparison="less_than"),
                tags=["support", "efficiency"]
            ),
            KPIDefinition(
                id="first_response_time",
                name="First Response Time",
                description="Average time to first response",
                category=KPICategory.PERFORMANCE,
                unit="minutes",
                calculation="avg(first_response_time)",
                target=KPITarget(target_value=15.0, comparison="less_than"),
                tags=["support", "responsiveness"]
            ),
            KPIDefinition(
                id="customer_satisfaction",
                name="Customer Satisfaction Score",
                description="Average customer satisfaction rating",
                category=KPICategory.CUSTOMER,
                unit="score",
                calculation="avg(satisfaction_score)",
                target=KPITarget(target_value=4.5, comparison="greater_than"),
                tags=["customer", "quality"]
            ),
            KPIDefinition(
                id="ticket_volume",
                name="Ticket Volume",
                description="Total number of tickets",
                category=KPICategory.OPERATIONAL,
                unit="tickets",
                calculation="count(tickets)",
                tags=["volume", "workload"]
            ),
            KPIDefinition(
                id="resolution_rate",
                name="Resolution Rate",
                description="Percentage of tickets resolved",
                category=KPICategory.QUALITY,
                unit="percent",
                calculation="(resolved / total) * 100",
                target=KPITarget(target_value=95.0, comparison="greater_than"),
                tags=["quality", "efficiency"]
            ),
            KPIDefinition(
                id="escalation_rate",
                name="Escalation Rate",
                description="Percentage of escalated tickets",
                category=KPICategory.OPERATIONAL,
                unit="percent",
                calculation="(escalated / total) * 100",
                target=KPITarget(target_value=5.0, comparison="less_than"),
                tags=["escalation", "quality"]
            )
        ]
        
        for kpi in default_kpis:
            self._definitions[kpi.id] = kpi
    
    def register_kpi(self, definition: KPIDefinition) -> None:
        """Register a new KPI definition"""
        self._definitions[definition.id] = definition
        logger.info(f"Registered KPI: {definition.name}")
    
    def get_kpi_definition(self, kpi_id: str) -> Optional[KPIDefinition]:
        """Get KPI definition by ID"""
        return self._definitions.get(kpi_id)
    
    def list_kpis(
        self,
        category: Optional[KPICategory] = None,
        tags: Optional[List[str]] = None
    ) -> List[KPIDefinition]:
        """List KPI definitions with optional filtering"""
        kpis = list(self._definitions.values())
        
        if category:
            kpis = [k for k in kpis if k.category == category]
        
        if tags:
            kpis = [k for k in kpis if any(t in k.tags for t in tags)]
        
        return kpis
    
    def record_value(
        self,
        kpi_id: str,
        value: float,
        timestamp: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[KPIValue]:
        """Record a KPI value"""
        definition = self._definitions.get(kpi_id)
        if not definition:
            logger.error(f"Unknown KPI: {kpi_id}")
            return None
        
        timestamp = timestamp or datetime.utcnow()
        
        # Get previous value for trend calculation
        previous_value = None
        if kpi_id in self._values and self._values[kpi_id]:
            previous_value = self._values[kpi_id][-1].value
        
        # Evaluate status against target
        status = KPIStatus.NO_DATA
        if definition.target:
            status = definition.target.evaluate(value)
        
        # Calculate trend
        trend = self._calculate_trend(value, previous_value)
        
        kpi_value = KPIValue(
            kpi_id=kpi_id,
            value=value,
            timestamp=timestamp,
            previous_value=previous_value,
            target_value=definition.target.target_value if definition.target else None,
            status=status,
            trend=trend,
            metadata=metadata or {}
        )
        
        # Store value
        if kpi_id not in self._values:
            self._values[kpi_id] = []
        self._values[kpi_id].append(kpi_value)
        
        return kpi_value
    
    def _calculate_trend(self, value: float, previous: Optional[float]) -> KPITrend:
        """Calculate trend direction"""
        if previous is None:
            return KPITrend.UNKNOWN
        
        change_pct = ((value - previous) / previous) * 100 if previous != 0 else 0
        
        if change_pct > 1:
            return KPITrend.UP
        elif change_pct < -1:
            return KPITrend.DOWN
        else:
            return KPITrend.STABLE
    
    def get_current_value(self, kpi_id: str) -> Optional[KPIValue]:
        """Get the most recent KPI value"""
        values = self._values.get(kpi_id, [])
        return values[-1] if values else None
    
    def get_history(
        self,
        kpi_id: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        limit: int = 100
    ) -> List[KPIValue]:
        """Get KPI value history"""
        values = self._values.get(kpi_id, [])
        
        if start:
            values = [v for v in values if v.timestamp >= start]
        
        if end:
            values = [v for v in values if v.timestamp <= end]
        
        return values[-limit:]
    
    def calculate_statistics(
        self,
        kpi_id: str,
        period_days: int = 30
    ) -> Dict[str, Any]:
        """Calculate statistics for a KPI over a period"""
        values = self._values.get(kpi_id, [])
        
        if not values:
            return {"error": "No data available"}
        
        # Filter by period
        cutoff = datetime.utcnow() - timedelta(days=period_days)
        recent_values = [v.value for v in values if v.timestamp >= cutoff]
        
        if not recent_values:
            return {"error": "No data in period"}
        
        return {
            "kpi_id": kpi_id,
            "period_days": period_days,
            "count": len(recent_values),
            "min": min(recent_values),
            "max": max(recent_values),
            "avg": sum(recent_values) / len(recent_values),
            "latest": recent_values[-1],
            "trend": self._calculate_overall_trend(recent_values)
        }
    
    def _calculate_overall_trend(self, values: List[float]) -> str:
        """Calculate overall trend from a series of values"""
        if len(values) < 2:
            return "insufficient_data"
        
        # Simple linear regression
        n = len(values)
        x = list(range(n))
        y = values
        
        sum_x = sum(x)
        sum_y = sum(y)
        sum_xy = sum(xi * yi for xi, yi in zip(x, y))
        sum_x2 = sum(xi ** 2 for xi in x)
        
        slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x ** 2)
        
        if slope > 0.01:
            return "improving"
        elif slope < -0.01:
            return "declining"
        else:
            return "stable"
    
    def get_summary(self) -> Dict[str, Any]:
        """Get KPI summary across all KPIs"""
        summary = {
            "total_kpis": len(self._definitions),
            "kpis_with_data": len(self._values),
            "by_status": {},
            "by_category": {},
            "kpis": []
        }
        
        # Count by status
        for kpi_id, definition in self._definitions.items():
            current = self.get_current_value(kpi_id)
            status = current.status.value if current else "no_data"
            
            summary["by_status"][status] = summary["by_status"].get(status, 0) + 1
            
            # Count by category
            cat = definition.category.value
            summary["by_category"][cat] = summary["by_category"].get(cat, 0) + 1
            
            summary["kpis"].append({
                "id": kpi_id,
                "name": definition.name,
                "category": cat,
                "status": status,
                "current_value": current.value if current else None
            })
        
        return summary
    
    def register_calculator(
        self,
        kpi_id: str,
        calculator: Callable
    ) -> None:
        """Register a custom calculator function"""
        self._calculators[kpi_id] = calculator
    
    async def calculate_kpi(
        self,
        kpi_id: str,
        data: Dict[str, Any]
    ) -> Optional[float]:
        """Calculate KPI value from data"""
        calculator = self._calculators.get(kpi_id)
        
        if calculator:
            return calculator(data)
        
        # Default calculation based on definition
        definition = self._definitions.get(kpi_id)
        if not definition:
            return None
        
        # Simple aggregations
        calc = definition.calculation.lower()
        
        if calc.startswith("avg("):
            field = calc[4:-1]
            values = data.get(field, [])
            return sum(values) / len(values) if values else 0
        elif calc.startswith("count("):
            field = calc[6:-1]
            values = data.get(field, [])
            return len(values)
        elif calc.startswith("sum("):
            field = calc[4:-1]
            values = data.get(field, [])
            return sum(values)
        
        return None


class KPICalculator:
    """Utility class for common KPI calculations"""
    
    @staticmethod
    def average(values: List[float]) -> float:
        """Calculate average"""
        if not values:
            return 0.0
        return sum(values) / len(values)
    
    @staticmethod
    def percentage(part: float, total: float) -> float:
        """Calculate percentage"""
        if total == 0:
            return 0.0
        return (part / total) * 100
    
    @staticmethod
    def rate(change: float, base: float) -> float:
        """Calculate rate of change"""
        if base == 0:
            return 0.0
        return (change / base) * 100
    
    @staticmethod
    def percentile(values: List[float], p: float) -> float:
        """Calculate percentile"""
        if not values:
            return 0.0
        sorted_values = sorted(values)
        k = (len(sorted_values) - 1) * p / 100
        f = math.floor(k)
        c = math.ceil(k)
        if f == c:
            return sorted_values[int(k)]
        return sorted_values[int(f)] * (c - k) + sorted_values[int(c)] * (k - f)
    
    @staticmethod
    def moving_average(values: List[float], window: int) -> List[float]:
        """Calculate moving average"""
        if len(values) < window:
            return []
        
        result = []
        for i in range(window - 1, len(values)):
            window_values = values[i - window + 1:i + 1]
            result.append(sum(window_values) / window)
        
        return result
    
    @staticmethod
    def growth_rate(values: List[float]) -> List[float]:
        """Calculate period-over-period growth rate"""
        if len(values) < 2:
            return []
        
        result = []
        for i in range(1, len(values)):
            if values[i - 1] == 0:
                result.append(0.0)
            else:
                result.append(((values[i] - values[i - 1]) / values[i - 1]) * 100)
        
        return result
