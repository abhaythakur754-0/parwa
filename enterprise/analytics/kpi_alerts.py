"""
KPI Alerts
Enterprise Analytics & Reporting - Week 44 Builder 2
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Callable
import logging

logger = logging.getLogger(__name__)


class AlertSeverity(str, Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertStatus(str, Enum):
    """Alert status"""
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    SNOOZED = "snoozed"


class AlertCondition(str, Enum):
    """Alert trigger conditions"""
    GREATER_THAN = "greater_than"
    LESS_THAN = "less_than"
    EQUALS = "equals"
    CHANGES_BY = "changes_by"
    TREND_UP = "trend_up"
    TREND_DOWN = "trend_down"
    NO_DATA = "no_data"


@dataclass
class AlertRule:
    """Alert rule configuration"""
    id: str
    name: str
    kpi_id: str
    condition: AlertCondition
    threshold: float
    severity: AlertSeverity
    enabled: bool = True
    cooldown_minutes: int = 60
    notification_channels: List[str] = field(default_factory=list)
    message_template: str = "KPI {kpi_name} is {condition} threshold of {threshold}"
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "kpi_id": self.kpi_id,
            "condition": self.condition.value,
            "threshold": self.threshold,
            "severity": self.severity.value,
            "enabled": self.enabled,
            "cooldown_minutes": self.cooldown_minutes,
            "notification_channels": self.notification_channels,
            "message_template": self.message_template,
            "created_at": self.created_at.isoformat()
        }


@dataclass
class Alert:
    """An active alert"""
    id: str
    rule_id: str
    kpi_id: str
    severity: AlertSeverity
    message: str
    value: float
    threshold: float
    status: AlertStatus = AlertStatus.ACTIVE
    triggered_at: datetime = field(default_factory=datetime.utcnow)
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None
    snoozed_until: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "rule_id": self.rule_id,
            "kpi_id": self.kpi_id,
            "severity": self.severity.value,
            "message": self.message,
            "value": self.value,
            "threshold": self.threshold,
            "status": self.status.value,
            "triggered_at": self.triggered_at.isoformat(),
            "acknowledged_at": self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "acknowledged_by": self.acknowledged_by,
            "snoozed_until": self.snoozed_until.isoformat() if self.snoozed_until else None,
            "metadata": self.metadata
        }


class KPIAlertManager:
    """Manages KPI alerts"""
    
    def __init__(self, kpi_engine: Any):
        self.kpi_engine = kpi_engine
        self._rules: Dict[str, AlertRule] = {}
        self._alerts: List[Alert] = []
        self._last_triggered: Dict[str, datetime] = {}
        self._notification_handlers: Dict[str, Callable] = {}
    
    def create_rule(
        self,
        name: str,
        kpi_id: str,
        condition: AlertCondition,
        threshold: float,
        severity: AlertSeverity,
        notification_channels: Optional[List[str]] = None,
        cooldown_minutes: int = 60
    ) -> AlertRule:
        """Create a new alert rule"""
        import uuid
        
        rule = AlertRule(
            id=str(uuid.uuid4()),
            name=name,
            kpi_id=kpi_id,
            condition=condition,
            threshold=threshold,
            severity=severity,
            notification_channels=notification_channels or [],
            cooldown_minutes=cooldown_minutes
        )
        
        self._rules[rule.id] = rule
        logger.info(f"Created alert rule: {name}")
        
        return rule
    
    def get_rule(self, rule_id: str) -> Optional[AlertRule]:
        """Get alert rule by ID"""
        return self._rules.get(rule_id)
    
    def list_rules(
        self,
        kpi_id: Optional[str] = None,
        enabled_only: bool = False
    ) -> List[AlertRule]:
        """List alert rules"""
        rules = list(self._rules.values())
        
        if kpi_id:
            rules = [r for r in rules if r.kpi_id == kpi_id]
        
        if enabled_only:
            rules = [r for r in rules if r.enabled]
        
        return rules
    
    def update_rule(self, rule_id: str, **kwargs) -> Optional[AlertRule]:
        """Update alert rule"""
        rule = self._rules.get(rule_id)
        if not rule:
            return None
        
        for key, value in kwargs.items():
            if hasattr(rule, key):
                setattr(rule, key, value)
        
        return rule
    
    def delete_rule(self, rule_id: str) -> bool:
        """Delete alert rule"""
        if rule_id in self._rules:
            del self._rules[rule_id]
            return True
        return False
    
    async def evaluate(self, kpi_id: str, value: float) -> List[Alert]:
        """Evaluate KPI value against all rules"""
        triggered_alerts = []
        
        for rule in self._rules.values():
            if not rule.enabled or rule.kpi_id != kpi_id:
                continue
            
            # Check cooldown
            if self._is_in_cooldown(rule):
                continue
            
            # Check condition
            if self._check_condition(rule, value):
                alert = await self._trigger_alert(rule, value)
                if alert:
                    triggered_alerts.append(alert)
        
        return triggered_alerts
    
    def _is_in_cooldown(self, rule: AlertRule) -> bool:
        """Check if rule is in cooldown period"""
        last_triggered = self._last_triggered.get(rule.id)
        if not last_triggered:
            return False
        
        cooldown_end = last_triggered + timedelta(minutes=rule.cooldown_minutes)
        return datetime.utcnow() < cooldown_end
    
    def _check_condition(self, rule: AlertRule, value: float) -> bool:
        """Check if alert condition is met"""
        if rule.condition == AlertCondition.GREATER_THAN:
            return value > rule.threshold
        elif rule.condition == AlertCondition.LESS_THAN:
            return value < rule.threshold
        elif rule.condition == AlertCondition.EQUALS:
            return abs(value - rule.threshold) < 0.01
        else:
            return False
    
    async def _trigger_alert(self, rule: AlertRule, value: float) -> Optional[Alert]:
        """Trigger an alert"""
        import uuid
        
        # Get KPI definition
        definition = self.kpi_engine.get_kpi_definition(rule.kpi_id)
        kpi_name = definition.name if definition else rule.kpi_id
        
        # Create message
        message = rule.message_template.format(
            kpi_name=kpi_name,
            condition=rule.condition.value.replace("_", " "),
            threshold=rule.threshold,
            value=value
        )
        
        alert = Alert(
            id=str(uuid.uuid4()),
            rule_id=rule.id,
            kpi_id=rule.kpi_id,
            severity=rule.severity,
            message=message,
            value=value,
            threshold=rule.threshold
        )
        
        self._alerts.append(alert)
        self._last_triggered[rule.id] = datetime.utcnow()
        
        # Send notifications
        await self._send_notifications(alert, rule)
        
        logger.warning(f"Alert triggered: {message}")
        
        return alert
    
    async def _send_notifications(self, alert: Alert, rule: AlertRule) -> None:
        """Send alert notifications"""
        for channel in rule.notification_channels:
            handler = self._notification_handlers.get(channel)
            if handler:
                try:
                    await handler(alert)
                except Exception as e:
                    logger.error(f"Notification error ({channel}): {e}")
    
    def register_notification_handler(
        self,
        channel: str,
        handler: Callable
    ) -> None:
        """Register a notification handler"""
        self._notification_handlers[channel] = handler
    
    def get_alert(self, alert_id: str) -> Optional[Alert]:
        """Get alert by ID"""
        for alert in self._alerts:
            if alert.id == alert_id:
                return alert
        return None
    
    def list_alerts(
        self,
        status: Optional[AlertStatus] = None,
        severity: Optional[AlertSeverity] = None,
        kpi_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Alert]:
        """List alerts with optional filtering"""
        alerts = self._alerts
        
        if status:
            alerts = [a for a in alerts if a.status == status]
        
        if severity:
            alerts = [a for a in alerts if a.severity == severity]
        
        if kpi_id:
            alerts = [a for a in alerts if a.kpi_id == kpi_id]
        
        return alerts[-limit:]
    
    def acknowledge_alert(self, alert_id: str, acknowledged_by: str) -> Optional[Alert]:
        """Acknowledge an alert"""
        alert = self.get_alert(alert_id)
        if not alert:
            return None
        
        alert.status = AlertStatus.ACKNOWLEDGED
        alert.acknowledged_at = datetime.utcnow()
        alert.acknowledged_by = acknowledged_by
        
        return alert
    
    def resolve_alert(self, alert_id: str) -> Optional[Alert]:
        """Resolve an alert"""
        alert = self.get_alert(alert_id)
        if not alert:
            return None
        
        alert.status = AlertStatus.RESOLVED
        alert.resolved_at = datetime.utcnow()
        
        return alert
    
    def snooze_alert(
        self,
        alert_id: str,
        duration_minutes: int
    ) -> Optional[Alert]:
        """Snooze an alert"""
        alert = self.get_alert(alert_id)
        if not alert:
            return None
        
        alert.status = AlertStatus.SNOOZED
        alert.snoozed_until = datetime.utcnow() + timedelta(minutes=duration_minutes)
        
        return alert
    
    def get_active_alerts_count(self) -> Dict[str, int]:
        """Get count of active alerts by severity"""
        counts = {s.value: 0 for s in AlertSeverity}
        
        for alert in self._alerts:
            if alert.status == AlertStatus.ACTIVE:
                counts[alert.severity.value] += 1
        
        return counts
    
    def cleanup_resolved(self, days: int = 30) -> int:
        """Remove old resolved alerts"""
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        initial_count = len(self._alerts)
        self._alerts = [
            a for a in self._alerts
            if a.status != AlertStatus.RESOLVED or a.resolved_at >= cutoff
        ]
        
        removed = initial_count - len(self._alerts)
        if removed > 0:
            logger.info(f"Cleaned up {removed} old alerts")
        
        return removed
