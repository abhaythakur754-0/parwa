"""
Supply Chain Intelligence.
Week 33, Logistics Module: Supply chain analytics and risk assessment.
"""

import logging
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
from uuid import uuid4

logger = logging.getLogger(__name__)


class RiskLevel(Enum):
    """Supply chain risk levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class EventType(Enum):
    """Supply chain event types."""
    SHIPMENT_CREATED = "shipment_created"
    SHIPMENT_DELAYED = "shipment_delayed"
    SHIPMENT_DELIVERED = "shipment_delivered"
    PORT_CONGESTION = "port_congestion"
    WEATHER_DISRUPTION = "weather_disruption"
    CUSTOMS_HOLD = "customs_hold"
    CARRIER_ISSUE = "carrier_issue"
    SUPPLIER_DELAY = "supplier_delay"
    INVENTORY_LOW = "inventory_low"
    DEMAND_SPIKE = "demand_spike"
    QUALITY_ISSUE = "quality_issue"


@dataclass
class SupplyChainEvent:
    """Supply chain event record."""
    event_id: str
    event_type: EventType
    timestamp: datetime
    severity: RiskLevel
    title: str
    description: str
    location: Optional[str] = None
    affected_shipments: List[str] = field(default_factory=list)
    affected_routes: List[str] = field(default_factory=list)
    estimated_impact: Optional[Dict[str, Any]] = None
    resolution_status: str = "open"
    resolution_actions: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'event_id': self.event_id,
            'event_type': self.event_type.value,
            'timestamp': self.timestamp.isoformat(),
            'severity': self.severity.value,
            'title': self.title,
            'description': self.description,
            'location': self.location,
            'affected_shipments': self.affected_shipments,
            'affected_routes': self.affected_routes,
            'estimated_impact': self.estimated_impact,
            'resolution_status': self.resolution_status,
            'resolution_actions': self.resolution_actions,
            'metadata': self.metadata,
        }


@dataclass
class RiskAssessment:
    """Supply chain risk assessment."""
    assessment_id: str
    overall_risk: RiskLevel
    risk_score: float  # 0-100
    categories: Dict[str, Dict[str, Any]]
    recommendations: List[str]
    created_at: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'assessment_id': self.assessment_id,
            'overall_risk': self.overall_risk.value,
            'risk_score': self.risk_score,
            'categories': self.categories,
            'recommendations': self.recommendations,
            'created_at': self.created_at.isoformat(),
            'metadata': self.metadata,
        }


@dataclass
class InventoryAlert:
    """Inventory alert."""
    alert_id: str
    sku: str
    product_name: str
    current_stock: int
    reorder_point: int
    days_of_stock: int
    severity: RiskLevel
    action_required: str
    created_at: datetime

    def to_dict(self) -> Dict[str, Any]:
        return {
            'alert_id': self.alert_id,
            'sku': self.sku,
            'product_name': self.product_name,
            'current_stock': self.current_stock,
            'reorder_point': self.reorder_point,
            'days_of_stock': self.days_of_stock,
            'severity': self.severity.value,
            'action_required': self.action_required,
            'created_at': self.created_at.isoformat(),
        }


class SupplyChainIntelligence:
    """
    Supply Chain Intelligence Engine.

    Provides analytics, risk assessment, and insights for supply chain
    operations including inventory management and disruption detection.
    """

    # Risk thresholds
    RISK_THRESHOLDS = {
        RiskLevel.LOW: 25,
        RiskLevel.MEDIUM: 50,
        RiskLevel.HIGH: 75,
        RiskLevel.CRITICAL: 100,
    }

    # Days of stock thresholds
    STOCK_THRESHOLDS = {
        "critical": 3,
        "low": 7,
        "healthy": 14,
    }

    def __init__(
        self,
        client_id: str,
        enable_predictive: bool = True,
    ):
        """
        Initialize Supply Chain Intelligence.

        Args:
            client_id: Client identifier
            enable_predictive: Enable predictive analytics
        """
        self.client_id = client_id
        self.enable_predictive = enable_predictive

        # Storage
        self._events: Dict[str, SupplyChainEvent] = {}
        self._assessments: Dict[str, RiskAssessment] = {}
        self._inventory_alerts: Dict[str, InventoryAlert] = {}

        # Metrics
        self._events_processed = 0
        self._alerts_generated = 0

        logger.info({
            "event": "supply_chain_intel_initialized",
            "client_id": client_id,
        })

    def record_event(
        self,
        event_type: EventType,
        title: str,
        description: str,
        severity: RiskLevel = RiskLevel.MEDIUM,
        location: Optional[str] = None,
        affected_shipments: Optional[List[str]] = None,
        affected_routes: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SupplyChainEvent:
        """
        Record a supply chain event.

        Args:
            event_type: Type of event
            title: Event title
            description: Event description
            severity: Severity level
            location: Location of event
            affected_shipments: List of affected shipment IDs
            affected_routes: List of affected route IDs
            metadata: Additional metadata

        Returns:
            Created event
        """
        event_id = f"SCE-{uuid4().hex[:8].upper()}"

        event = SupplyChainEvent(
            event_id=event_id,
            event_type=event_type,
            timestamp=datetime.utcnow(),
            severity=severity,
            title=title,
            description=description,
            location=location,
            affected_shipments=affected_shipments or [],
            affected_routes=affected_routes or [],
            metadata=metadata or {},
        )

        self._events[event_id] = event
        self._events_processed += 1

        # Generate alerts if high severity
        if severity in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
            self._generate_alert(event)

        logger.info({
            "event": "supply_chain_event_recorded",
            "event_id": event_id,
            "event_type": event_type.value,
            "severity": severity.value,
        })

        return event

    def assess_risk(self) -> RiskAssessment:
        """
        Perform comprehensive risk assessment.

        Returns:
            Risk assessment result
        """
        # Analyze each risk category
        categories = {
            "disruption": self._assess_disruption_risk(),
            "inventory": self._assess_inventory_risk(),
            "carrier": self._assess_carrier_risk(),
            "demand": self._assess_demand_risk(),
            "supplier": self._assess_supplier_risk(),
        }

        # Calculate overall risk score
        risk_scores = [cat.get("score", 0) for cat in categories.values()]
        overall_score = sum(risk_scores) / len(risk_scores) if risk_scores else 0

        # Determine overall risk level
        overall_risk = RiskLevel.LOW
        for level, threshold in self.RISK_THRESHOLDS.items():
            if overall_score >= threshold - 25:
                overall_risk = level

        # Generate recommendations
        recommendations = self._generate_recommendations(categories, overall_risk)

        assessment = RiskAssessment(
            assessment_id=f"RA-{uuid4().hex[:8].upper()}",
            overall_risk=overall_risk,
            risk_score=round(overall_score, 1),
            categories=categories,
            recommendations=recommendations,
            created_at=datetime.utcnow(),
        )

        self._assessments[assessment.assessment_id] = assessment

        logger.info({
            "event": "risk_assessment_completed",
            "assessment_id": assessment.assessment_id,
            "overall_risk": overall_risk.value,
            "risk_score": overall_score,
        })

        return assessment

    def check_inventory(
        self,
        sku: str,
        product_name: str,
        current_stock: int,
        daily_usage: float,
        reorder_point: int,
    ) -> Optional[InventoryAlert]:
        """
        Check inventory levels and generate alerts.

        Args:
            sku: Product SKU
            product_name: Product name
            current_stock: Current stock level
            daily_usage: Average daily usage
            reorder_point: Reorder point

        Returns:
            Inventory alert if needed
        """
        if daily_usage <= 0:
            return None

        days_of_stock = int(current_stock / daily_usage)

        severity = None
        action = None

        if days_of_stock <= self.STOCK_THRESHOLDS["critical"]:
            severity = RiskLevel.CRITICAL
            action = "Urgent reorder required - stock critically low"
        elif days_of_stock <= self.STOCK_THRESHOLDS["low"]:
            severity = RiskLevel.HIGH
            action = "Reorder recommended - stock running low"
        elif current_stock <= reorder_point:
            severity = RiskLevel.MEDIUM
            action = "Below reorder point - consider reordering"

        if not severity:
            return None

        alert = InventoryAlert(
            alert_id=f"INV-{uuid4().hex[:8].upper()}",
            sku=sku,
            product_name=product_name,
            current_stock=current_stock,
            reorder_point=reorder_point,
            days_of_stock=days_of_stock,
            severity=severity,
            action_required=action,
            created_at=datetime.utcnow(),
        )

        self._inventory_alerts[alert.alert_id] = alert
        self._alerts_generated += 1

        logger.info({
            "event": "inventory_alert_generated",
            "alert_id": alert.alert_id,
            "sku": sku,
            "days_of_stock": days_of_stock,
            "severity": severity.value,
        })

        return alert

    def get_active_events(
        self,
        severity: Optional[RiskLevel] = None,
    ) -> List[SupplyChainEvent]:
        """
        Get active supply chain events.

        Args:
            severity: Optional severity filter

        Returns:
            List of active events
        """
        events = [e for e in self._events.values() if e.resolution_status == "open"]

        if severity:
            events = [e for e in events if e.severity == severity]

        return sorted(events, key=lambda e: e.timestamp, reverse=True)

    def resolve_event(
        self,
        event_id: str,
        actions: List[str],
    ) -> Optional[SupplyChainEvent]:
        """
        Mark an event as resolved.

        Args:
            event_id: Event identifier
            actions: Resolution actions taken

        Returns:
            Updated event
        """
        event = self._events.get(event_id)
        if not event:
            return None

        event.resolution_status = "resolved"
        event.resolution_actions = actions

        logger.info({
            "event": "supply_chain_event_resolved",
            "event_id": event_id,
            "actions": actions,
        })

        return event

    def get_inventory_alerts(
        self,
        severity: Optional[RiskLevel] = None,
    ) -> List[InventoryAlert]:
        """Get inventory alerts."""
        alerts = list(self._inventory_alerts.values())

        if severity:
            alerts = [a for a in alerts if a.severity == severity]

        return sorted(alerts, key=lambda a: a.created_at, reverse=True)

    def predict_delays(
        self,
        route_id: str,
    ) -> Dict[str, Any]:
        """
        Predict potential delays for a route.

        Args:
            route_id: Route identifier

        Returns:
            Delay prediction
        """
        if not self.enable_predictive:
            return {"enabled": False}

        # Mock prediction based on historical patterns
        prediction = {
            "route_id": route_id,
            "prediction_date": datetime.utcnow().isoformat(),
            "delay_probability": 0.15,
            "expected_delay_hours": 0,
            "risk_factors": [],
            "recommendations": [],
        }

        # Check for active events affecting this route
        route_events = [
            e for e in self._events.values()
            if route_id in e.affected_routes and e.resolution_status == "open"
        ]

        if route_events:
            prediction["delay_probability"] = 0.45
            prediction["expected_delay_hours"] = 6
            prediction["risk_factors"] = [
                {"factor": e.event_type.value, "severity": e.severity.value}
                for e in route_events[:3]
            ]
            prediction["recommendations"] = [
                "Consider alternative routing",
                "Notify customers of potential delay",
            ]

        return prediction

    def _assess_disruption_risk(self) -> Dict[str, Any]:
        """Assess disruption risk."""
        critical_events = len([
            e for e in self._events.values()
            if e.severity in [RiskLevel.HIGH, RiskLevel.CRITICAL]
            and e.resolution_status == "open"
        ])

        score = min(100, critical_events * 20)

        return {
            "score": score,
            "level": self._get_risk_level(score),
            "active_disruptions": critical_events,
            "factors": {
                "weather_events": len([e for e in self._events.values() if e.event_type == EventType.WEATHER_DISRUPTION]),
                "port_congestion": len([e for e in self._events.values() if e.event_type == EventType.PORT_CONGESTION]),
                "carrier_issues": len([e for e in self._events.values() if e.event_type == EventType.CARRIER_ISSUE]),
            },
        }

    def _assess_inventory_risk(self) -> Dict[str, Any]:
        """Assess inventory risk."""
        critical_alerts = len([
            a for a in self._inventory_alerts.values()
            if a.severity in [RiskLevel.HIGH, RiskLevel.CRITICAL]
        ])

        score = min(100, critical_alerts * 25)

        return {
            "score": score,
            "level": self._get_risk_level(score),
            "low_stock_items": critical_alerts,
            "factors": {
                "critical_stock": len([a for a in self._inventory_alerts.values() if a.severity == RiskLevel.CRITICAL]),
                "below_reorder": len(self._inventory_alerts),
            },
        }

    def _assess_carrier_risk(self) -> Dict[str, Any]:
        """Assess carrier performance risk."""
        # Mock carrier assessment
        return {
            "score": 15,
            "level": "low",
            "on_time_rate": 94.5,
            "average_delay_hours": 2.3,
        }

    def _assess_demand_risk(self) -> Dict[str, Any]:
        """Assess demand variability risk."""
        demand_events = len([
            e for e in self._events.values()
            if e.event_type == EventType.DEMAND_SPIKE
        ])

        score = min(100, demand_events * 30)

        return {
            "score": score,
            "level": self._get_risk_level(score),
            "demand_spikes": demand_events,
        }

    def _assess_supplier_risk(self) -> Dict[str, Any]:
        """Assess supplier reliability risk."""
        supplier_events = len([
            e for e in self._events.values()
            if e.event_type == EventType.SUPPLIER_DELAY
        ])

        score = min(100, supplier_events * 25)

        return {
            "score": score,
            "level": self._get_risk_level(score),
            "supplier_delays": supplier_events,
        }

    def _get_risk_level(self, score: float) -> str:
        """Get risk level from score."""
        if score >= 75:
            return RiskLevel.CRITICAL.value
        elif score >= 50:
            return RiskLevel.HIGH.value
        elif score >= 25:
            return RiskLevel.MEDIUM.value
        return RiskLevel.LOW.value

    def _generate_recommendations(
        self,
        categories: Dict[str, Dict[str, Any]],
        overall_risk: RiskLevel,
    ) -> List[str]:
        """Generate recommendations based on assessment."""
        recommendations = []

        if categories["disruption"]["score"] >= 50:
            recommendations.append("Activate contingency plans for active disruptions")

        if categories["inventory"]["score"] >= 50:
            recommendations.append("Prioritize reorders for critical stock items")

        if categories["carrier"]["score"] >= 30:
            recommendations.append("Review carrier performance and consider alternatives")

        if overall_risk in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
            recommendations.append("Schedule executive briefing on supply chain status")

        if not recommendations:
            recommendations.append("Continue monitoring supply chain metrics")

        return recommendations

    def _generate_alert(self, event: SupplyChainEvent):
        """Generate alerts for high-severity events."""
        logger.warning({
            "event": "supply_chain_alert_generated",
            "event_id": event.event_id,
            "severity": event.severity.value,
            "title": event.title,
        })

    def get_stats(self) -> Dict[str, Any]:
        """Get intelligence statistics."""
        return {
            "client_id": self.client_id,
            "events_processed": self._events_processed,
            "alerts_generated": self._alerts_generated,
            "active_events": len(self.get_active_events()),
            "inventory_alerts": len(self._inventory_alerts),
            "assessments_performed": len(self._assessments),
            "predictive_enabled": self.enable_predictive,
        }
