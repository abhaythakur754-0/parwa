"""
Integration Health Monitoring
Enterprise Integration Hub - Week 43 Builder 5
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class HealthStatus(str, Enum):
    """Health status levels"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class AlertSeverity(str, Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class HealthCheck:
    """Result of a health check"""
    integration_id: str
    status: HealthStatus
    latency_ms: float
    message: str
    checked_at: datetime = field(default_factory=datetime.utcnow)
    details: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "integration_id": self.integration_id,
            "status": self.status.value,
            "latency_ms": self.latency_ms,
            "message": self.message,
            "checked_at": self.checked_at.isoformat(),
            "details": self.details
        }


@dataclass
class HealthAlert:
    """Health alert"""
    id: str
    integration_id: str
    severity: AlertSeverity
    message: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    acknowledged: bool = False
    acknowledged_at: Optional[datetime] = None
    resolved: bool = False
    resolved_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "integration_id": self.integration_id,
            "severity": self.severity.value,
            "message": self.message,
            "created_at": self.created_at.isoformat(),
            "acknowledged": self.acknowledged,
            "acknowledged_at": self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            "resolved": self.resolved,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None
        }


@dataclass
class HealthMetric:
    """Health metric data point"""
    integration_id: str
    metric_name: str
    value: float
    timestamp: datetime = field(default_factory=datetime.utcnow)
    tags: Dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "integration_id": self.integration_id,
            "metric_name": self.metric_name,
            "value": self.value,
            "timestamp": self.timestamp.isoformat(),
            "tags": self.tags
        }


class IntegrationHealthMonitor:
    """Monitors health of all integrations"""
    
    def __init__(
        self,
        hub: Any,
        check_interval_seconds: int = 60,
        latency_threshold_ms: float = 1000.0,
        error_rate_threshold: float = 0.1
    ):
        self.hub = hub
        self.check_interval = check_interval_seconds
        self.latency_threshold = latency_threshold_ms
        self.error_rate_threshold = error_rate_threshold
        
        self._health_checks: Dict[str, List[HealthCheck]] = {}
        self._alerts: List[HealthAlert] = []
        self._metrics: List[HealthMetric] = []
        self._running = False
    
    async def start(self) -> None:
        """Start the health monitor"""
        self._running = True
        logger.info("Health monitor started")
        
        while self._running:
            try:
                await self._check_all()
                await asyncio.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"Health check error: {e}")
    
    def stop(self) -> None:
        """Stop the health monitor"""
        self._running = False
        logger.info("Health monitor stopped")
    
    async def _check_all(self) -> Dict[str, HealthCheck]:
        """Check health of all integrations"""
        results = {}
        
        integrations = self.hub.list_integrations()
        
        for integration in integrations:
            check = await self._check_integration(integration)
            results[integration.id] = check
            
            # Store result
            if integration.id not in self._health_checks:
                self._health_checks[integration.id] = []
            self._health_checks[integration.id].append(check)
            
            # Keep only last 100 checks
            if len(self._health_checks[integration.id]) > 100:
                self._health_checks[integration.id] = self._health_checks[integration.id][-100:]
            
            # Generate alerts if needed
            await self._check_for_alerts(integration.id, check)
        
        return results
    
    async def _check_integration(self, integration: Any) -> HealthCheck:
        """Check health of a single integration"""
        import time
        
        start_time = time.time()
        
        try:
            # Perform health check based on integration type
            if hasattr(integration.connector, 'test_connection'):
                is_healthy = await integration.connector.test_connection()
            else:
                is_healthy = integration.status.value == "connected"
            
            latency = (time.time() - start_time) * 1000
            
            if is_healthy:
                status = HealthStatus.HEALTHY if latency < self.latency_threshold else HealthStatus.DEGRADED
                message = "Connection successful"
            else:
                status = HealthStatus.UNHEALTHY
                message = "Connection failed"
            
            return HealthCheck(
                integration_id=integration.id,
                status=status,
                latency_ms=latency,
                message=message,
                details={
                    "integration_name": integration.name,
                    "integration_type": integration.type.value
                }
            )
            
        except Exception as e:
            latency = (time.time() - start_time) * 1000
            return HealthCheck(
                integration_id=integration.id,
                status=HealthStatus.UNHEALTHY,
                latency_ms=latency,
                message=str(e)
            )
    
    async def _check_for_alerts(self, integration_id: str, check: HealthCheck) -> None:
        """Check if alerts should be generated"""
        import uuid
        
        # Check for unhealthy status
        if check.status == HealthStatus.UNHEALTHY:
            # Check if there's already an unresolved alert
            existing = next(
                (a for a in self._alerts 
                 if a.integration_id == integration_id 
                 and not a.resolved 
                 and a.severity in [AlertSeverity.ERROR, AlertSeverity.CRITICAL]),
                None
            )
            
            if not existing:
                alert = HealthAlert(
                    id=str(uuid.uuid4()),
                    integration_id=integration_id,
                    severity=AlertSeverity.ERROR,
                    message=f"Integration unhealthy: {check.message}"
                )
                self._alerts.append(alert)
                logger.warning(f"Health alert: {alert.message}")
        
        # Check for degraded status
        elif check.status == HealthStatus.DEGRADED:
            if check.latency_ms > self.latency_threshold * 2:
                alert = HealthAlert(
                    id=str(uuid.uuid4()),
                    integration_id=integration_id,
                    severity=AlertSeverity.WARNING,
                    message=f"High latency detected: {check.latency_ms:.0f}ms"
                )
                self._alerts.append(alert)
        
        # Resolve existing alerts if healthy
        elif check.status == HealthStatus.HEALTHY:
            for alert in self._alerts:
                if alert.integration_id == integration_id and not alert.resolved:
                    alert.resolved = True
                    alert.resolved_at = datetime.utcnow()
    
    async def check_now(self, integration_id: str) -> HealthCheck:
        """Perform an immediate health check"""
        integration = self.hub.get_integration(integration_id)
        
        if not integration:
            return HealthCheck(
                integration_id=integration_id,
                status=HealthStatus.UNKNOWN,
                latency_ms=0,
                message="Integration not found"
            )
        
        return await self._check_integration(integration)
    
    def get_health(self, integration_id: str) -> Optional[HealthCheck]:
        """Get the latest health check for an integration"""
        checks = self._health_checks.get(integration_id, [])
        return checks[-1] if checks else None
    
    def get_health_history(
        self,
        integration_id: str,
        limit: int = 24
    ) -> List[HealthCheck]:
        """Get health check history"""
        checks = self._health_checks.get(integration_id, [])
        return checks[-limit:]
    
    def get_alerts(
        self,
        integration_id: Optional[str] = None,
        severity: Optional[AlertSeverity] = None,
        include_resolved: bool = False
    ) -> List[HealthAlert]:
        """Get alerts with optional filtering"""
        alerts = self._alerts
        
        if integration_id:
            alerts = [a for a in alerts if a.integration_id == integration_id]
        
        if severity:
            alerts = [a for a in alerts if a.severity == severity]
        
        if not include_resolved:
            alerts = [a for a in alerts if not a.resolved]
        
        return alerts
    
    def acknowledge_alert(self, alert_id: str) -> bool:
        """Acknowledge an alert"""
        for alert in self._alerts:
            if alert.id == alert_id:
                alert.acknowledged = True
                alert.acknowledged_at = datetime.utcnow()
                return True
        return False
    
    def resolve_alert(self, alert_id: str) -> bool:
        """Manually resolve an alert"""
        for alert in self._alerts:
            if alert.id == alert_id:
                alert.resolved = True
                alert.resolved_at = datetime.utcnow()
                return True
        return False
    
    def record_metric(
        self,
        integration_id: str,
        metric_name: str,
        value: float,
        tags: Optional[Dict[str, str]] = None
    ) -> None:
        """Record a health metric"""
        metric = HealthMetric(
            integration_id=integration_id,
            metric_name=metric_name,
            value=value,
            tags=tags or {}
        )
        self._metrics.append(metric)
        
        # Keep only last 10000 metrics
        if len(self._metrics) > 10000:
            self._metrics = self._metrics[-10000:]
    
    def get_metrics(
        self,
        integration_id: Optional[str] = None,
        metric_name: Optional[str] = None,
        since: Optional[datetime] = None,
        limit: int = 1000
    ) -> List[HealthMetric]:
        """Get metrics with optional filtering"""
        metrics = self._metrics
        
        if integration_id:
            metrics = [m for m in metrics if m.integration_id == integration_id]
        
        if metric_name:
            metrics = [m for m in metrics if m.metric_name == metric_name]
        
        if since:
            metrics = [m for m in metrics if m.timestamp >= since]
        
        return metrics[-limit:]
    
    def get_summary(self) -> Dict[str, Any]:
        """Get health summary for all integrations"""
        integrations = self.hub.list_integrations()
        
        summary = {
            "total_integrations": len(integrations),
            "healthy": 0,
            "degraded": 0,
            "unhealthy": 0,
            "unknown": 0,
            "open_alerts": len([a for a in self._alerts if not a.resolved]),
            "integrations": []
        }
        
        for integration in integrations:
            check = self.get_health(integration.id)
            
            if check:
                if check.status == HealthStatus.HEALTHY:
                    summary["healthy"] += 1
                elif check.status == HealthStatus.DEGRADED:
                    summary["degraded"] += 1
                elif check.status == HealthStatus.UNHEALTHY:
                    summary["unhealthy"] += 1
                else:
                    summary["unknown"] += 1
                
                summary["integrations"].append({
                    "id": integration.id,
                    "name": integration.name,
                    "type": integration.type.value,
                    "status": check.status.value,
                    "latency_ms": check.latency_ms,
                    "last_check": check.checked_at.isoformat()
                })
            else:
                summary["unknown"] += 1
        
        return summary
