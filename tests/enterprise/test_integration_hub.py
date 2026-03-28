"""
Tests for Integration Orchestration
Enterprise Integration Hub - Week 43 Builder 5
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
import json

from enterprise.integrations.integration_hub import (
    IntegrationHub,
    IntegrationInstance,
    IntegrationType,
    IntegrationStatus,
    SyncJob,
    SyncResult
)
from enterprise.integrations.sync_coordinator import (
    SyncCoordinator,
    SyncTask,
    ConflictResolution
)
from enterprise.integrations.integration_health import (
    IntegrationHealthMonitor,
    HealthCheck,
    HealthStatus,
    HealthAlert,
    AlertSeverity,
    HealthMetric
)


# Test Fixtures
@pytest.fixture
def integration_hub():
    """Create a test integration hub"""
    return IntegrationHub()


@pytest.fixture
def mock_connector():
    """Create a mock connector"""
    connector = MagicMock()
    connector.connect = AsyncMock(return_value=True)
    connector.disconnect = AsyncMock(return_value=True)
    connector.test_connection = AsyncMock(return_value=True)
    return connector


@pytest.fixture
def sync_coordinator(integration_hub):
    """Create a test sync coordinator"""
    return SyncCoordinator(integration_hub)


@pytest.fixture
def health_monitor(integration_hub):
    """Create a test health monitor"""
    return IntegrationHealthMonitor(integration_hub)


# IntegrationHub Tests
class TestIntegrationHub:
    """Tests for IntegrationHub"""
    
    def test_hub_initialization(self, integration_hub):
        """Test hub initializes correctly"""
        assert integration_hub is not None
        assert len(integration_hub._integrations) == 0
    
    def test_register_integration(self, integration_hub, mock_connector):
        """Test integration registration"""
        instance = integration_hub.register_integration(
            name="test_salesforce",
            integration_type=IntegrationType.CRM,
            connector=mock_connector,
            config={"api_url": "https://test.salesforce.com"}
        )
        
        assert instance.id is not None
        assert instance.name == "test_salesforce"
        assert instance.type == IntegrationType.CRM
        assert instance.status == IntegrationStatus.DISCONNECTED
    
    def test_get_integration(self, integration_hub, mock_connector):
        """Test getting an integration by ID"""
        registered = integration_hub.register_integration(
            name="test",
            integration_type=IntegrationType.ERP,
            connector=mock_connector,
            config={}
        )
        
        retrieved = integration_hub.get_integration(registered.id)
        
        assert retrieved is not None
        assert retrieved.id == registered.id
    
    def test_get_nonexistent_integration(self, integration_hub):
        """Test getting a non-existent integration"""
        result = integration_hub.get_integration("nonexistent")
        assert result is None
    
    def test_unregister_integration(self, integration_hub, mock_connector):
        """Test unregistering an integration"""
        instance = integration_hub.register_integration(
            name="test",
            integration_type=IntegrationType.WAREHOUSE,
            connector=mock_connector,
            config={}
        )
        
        result = integration_hub.unregister_integration(instance.id)
        assert result is True
        
        retrieved = integration_hub.get_integration(instance.id)
        assert retrieved is None
    
    def test_list_integrations(self, integration_hub, mock_connector):
        """Test listing integrations"""
        integration_hub.register_integration(
            name="crm1",
            integration_type=IntegrationType.CRM,
            connector=mock_connector,
            config={}
        )
        integration_hub.register_integration(
            name="erp1",
            integration_type=IntegrationType.ERP,
            connector=mock_connector,
            config={}
        )
        
        integrations = integration_hub.list_integrations()
        assert len(integrations) == 2
    
    def test_list_integrations_by_type(self, integration_hub, mock_connector):
        """Test filtering integrations by type"""
        integration_hub.register_integration(
            name="crm1",
            integration_type=IntegrationType.CRM,
            connector=mock_connector,
            config={}
        )
        integration_hub.register_integration(
            name="erp1",
            integration_type=IntegrationType.ERP,
            connector=mock_connector,
            config={}
        )
        
        crm_integrations = integration_hub.list_integrations(type_filter=IntegrationType.CRM)
        assert len(crm_integrations) == 1
        assert crm_integrations[0].type == IntegrationType.CRM
    
    @pytest.mark.asyncio
    async def test_connect_integration(self, integration_hub, mock_connector):
        """Test connecting to an integration"""
        instance = integration_hub.register_integration(
            name="test",
            integration_type=IntegrationType.CRM,
            connector=mock_connector,
            config={}
        )
        
        result = await integration_hub.connect_integration(instance.id)
        
        assert result is True
        assert instance.status == IntegrationStatus.CONNECTED
    
    @pytest.mark.asyncio
    async def test_disconnect_integration(self, integration_hub, mock_connector):
        """Test disconnecting from an integration"""
        instance = integration_hub.register_integration(
            name="test",
            integration_type=IntegrationType.CRM,
            connector=mock_connector,
            config={}
        )
        
        await integration_hub.connect_integration(instance.id)
        result = await integration_hub.disconnect_integration(instance.id)
        
        assert result is True
        assert instance.status == IntegrationStatus.DISCONNECTED
    
    def test_create_sync_job(self, integration_hub):
        """Test creating a sync job"""
        job = integration_hub.create_sync_job(
            name="sync_contacts",
            source_integration="source_id",
            target_integration="target_id",
            entity_type="contacts"
        )
        
        assert job.id is not None
        assert job.name == "sync_contacts"
        assert job.enabled is True
    
    def test_get_sync_job(self, integration_hub):
        """Test getting a sync job"""
        created = integration_hub.create_sync_job(
            name="test_job",
            source_integration="source",
            target_integration="target",
            entity_type="data"
        )
        
        retrieved = integration_hub.get_sync_job(created.id)
        
        assert retrieved is not None
        assert retrieved.id == created.id
    
    def test_list_sync_jobs(self, integration_hub):
        """Test listing sync jobs"""
        integration_hub.create_sync_job(
            name="job1",
            source_integration="s1",
            target_integration="t1",
            entity_type="e1"
        )
        integration_hub.create_sync_job(
            name="job2",
            source_integration="s2",
            target_integration="t2",
            entity_type="e2",
            schedule="0 0 * * *"
        )
        
        jobs = integration_hub.list_sync_jobs()
        assert len(jobs) == 2
    
    def test_get_health_status(self, integration_hub, mock_connector):
        """Test getting health status"""
        integration_hub.register_integration(
            name="test",
            integration_type=IntegrationType.CRM,
            connector=mock_connector,
            config={}
        )
        
        health = integration_hub.get_health_status()
        
        assert "integrations" in health
        assert health["integrations"]["total"] == 1


# IntegrationInstance Tests
class TestIntegrationInstance:
    """Tests for IntegrationInstance"""
    
    def test_instance_creation(self):
        """Test instance can be created"""
        instance = IntegrationInstance(
            id="test-id",
            name="test",
            type=IntegrationType.CRM,
            connector=MagicMock(),
            config={}
        )
        
        assert instance.id == "test-id"
        assert instance.name == "test"
        assert instance.status == IntegrationStatus.DISCONNECTED
    
    def test_instance_to_dict(self):
        """Test instance serialization"""
        instance = IntegrationInstance(
            id="test-id",
            name="test",
            type=IntegrationType.ERP,
            connector=MagicMock(),
            config={}
        )
        
        data = instance.to_dict()
        
        assert data["id"] == "test-id"
        assert data["name"] == "test"
        assert data["type"] == "erp"


# SyncJob Tests
class TestSyncJob:
    """Tests for SyncJob"""
    
    def test_job_creation(self):
        """Test job can be created"""
        job = SyncJob(
            id="job-id",
            name="test_job",
            source_integration="source",
            target_integration="target",
            entity_type="contacts",
            schedule="0 * * * *"
        )
        
        assert job.id == "job-id"
        assert job.name == "test_job"
        assert job.enabled is True
    
    def test_job_to_dict(self):
        """Test job serialization"""
        job = SyncJob(
            id="job-id",
            name="test",
            source_integration="s",
            target_integration="t",
            entity_type="e",
            schedule="* * * * *"
        )
        
        data = job.to_dict()
        
        assert data["id"] == "job-id"
        assert data["schedule"] == "* * * * *"


# SyncResult Tests
class TestSyncResult:
    """Tests for SyncResult"""
    
    def test_result_creation(self):
        """Test result can be created"""
        result = SyncResult(
            job_id="job-1",
            status="completed",
            records_processed=100,
            records_succeeded=98,
            records_failed=2
        )
        
        assert result.job_id == "job-1"
        assert result.status == "completed"
        assert result.records_processed == 100


# SyncCoordinator Tests
class TestSyncCoordinator:
    """Tests for SyncCoordinator"""
    
    def test_coordinator_initialization(self, sync_coordinator):
        """Test coordinator initializes correctly"""
        assert sync_coordinator is not None
        assert sync_coordinator._running is False
    
    def test_set_concurrency(self, sync_coordinator):
        """Test setting concurrency limit"""
        sync_coordinator.set_concurrency(10)
        assert sync_coordinator._concurrency_limit == 10
        
        # Test bounds
        sync_coordinator.set_concurrency(0)
        assert sync_coordinator._concurrency_limit == 1
        
        sync_coordinator.set_concurrency(100)
        assert sync_coordinator._concurrency_limit == 20
    
    @pytest.mark.asyncio
    async def test_queue_sync(self, sync_coordinator):
        """Test queuing a sync task"""
        task = await sync_coordinator.queue_sync(
            name="test_sync",
            source_id="source",
            target_id="target",
            entity_type="contacts"
        )
        
        assert task.id is not None
        assert task.name == "test_sync"
        assert task.status == "pending"


# ConflictResolution Tests
class TestConflictResolution:
    """Tests for ConflictResolution"""
    
    def test_source_wins(self):
        """Test source wins strategy"""
        resolution = ConflictResolution(strategy="source_wins")
        
        source = {"id": "1", "name": "Source Name"}
        target = {"id": "1", "name": "Target Name"}
        
        result = resolution.resolve(source, target)
        assert result["name"] == "Source Name"
    
    def test_target_wins(self):
        """Test target wins strategy"""
        resolution = ConflictResolution(strategy="target_wins")
        
        source = {"id": "1", "name": "Source Name"}
        target = {"id": "1", "name": "Target Name"}
        
        result = resolution.resolve(source, target)
        assert result["name"] == "Target Name"
    
    def test_merge_strategy(self):
        """Test merge strategy"""
        resolution = ConflictResolution(
            strategy="merge",
            merge_rules={"name": "source", "value": "target"}
        )
        
        source = {"id": "1", "name": "Source", "value": "SV", "extra": "S"}
        target = {"id": "1", "name": "Target", "value": "TV", "existing": "T"}
        
        result = resolution.resolve(source, target)
        assert result["name"] == "Source"
        assert result["value"] == "TV"


# HealthCheck Tests
class TestHealthCheck:
    """Tests for HealthCheck"""
    
    def test_check_creation(self):
        """Test health check can be created"""
        check = HealthCheck(
            integration_id="test-id",
            status=HealthStatus.HEALTHY,
            latency_ms=150.5,
            message="Connection successful"
        )
        
        assert check.integration_id == "test-id"
        assert check.status == HealthStatus.HEALTHY
        assert check.latency_ms == 150.5
    
    def test_check_to_dict(self):
        """Test health check serialization"""
        check = HealthCheck(
            integration_id="test-id",
            status=HealthStatus.DEGRADED,
            latency_ms=500.0,
            message="High latency"
        )
        
        data = check.to_dict()
        
        assert data["integration_id"] == "test-id"
        assert data["status"] == "degraded"


# HealthAlert Tests
class TestHealthAlert:
    """Tests for HealthAlert"""
    
    def test_alert_creation(self):
        """Test alert can be created"""
        alert = HealthAlert(
            id="alert-1",
            integration_id="int-1",
            severity=AlertSeverity.ERROR,
            message="Connection failed"
        )
        
        assert alert.id == "alert-1"
        assert alert.severity == AlertSeverity.ERROR
        assert alert.acknowledged is False
        assert alert.resolved is False
    
    def test_alert_to_dict(self):
        """Test alert serialization"""
        alert = HealthAlert(
            id="alert-1",
            integration_id="int-1",
            severity=AlertSeverity.WARNING,
            message="High latency"
        )
        
        data = alert.to_dict()
        
        assert data["id"] == "alert-1"
        assert data["severity"] == "warning"


# HealthMetric Tests
class TestHealthMetric:
    """Tests for HealthMetric"""
    
    def test_metric_creation(self):
        """Test metric can be created"""
        metric = HealthMetric(
            integration_id="int-1",
            metric_name="latency",
            value=150.0
        )
        
        assert metric.integration_id == "int-1"
        assert metric.metric_name == "latency"
        assert metric.value == 150.0
    
    def test_metric_to_dict(self):
        """Test metric serialization"""
        metric = HealthMetric(
            integration_id="int-1",
            metric_name="error_rate",
            value=0.05,
            tags={"environment": "production"}
        )
        
        data = metric.to_dict()
        
        assert data["metric_name"] == "error_rate"
        assert data["tags"]["environment"] == "production"


# IntegrationHealthMonitor Tests
class TestIntegrationHealthMonitor:
    """Tests for IntegrationHealthMonitor"""
    
    def test_monitor_initialization(self, health_monitor):
        """Test monitor initializes correctly"""
        assert health_monitor is not None
        assert health_monitor._running is False
    
    def test_record_metric(self, health_monitor):
        """Test recording a metric"""
        health_monitor.record_metric(
            integration_id="int-1",
            metric_name="latency",
            value=100.0
        )
        
        metrics = health_monitor.get_metrics(integration_id="int-1")
        assert len(metrics) == 1
        assert metrics[0].value == 100.0
    
    def test_get_metrics_filtering(self, health_monitor):
        """Test metric filtering"""
        health_monitor.record_metric("int-1", "latency", 100.0)
        health_monitor.record_metric("int-1", "error_rate", 0.05)
        health_monitor.record_metric("int-2", "latency", 200.0)
        
        all_metrics = health_monitor.get_metrics()
        assert len(all_metrics) == 3
        
        int1_metrics = health_monitor.get_metrics(integration_id="int-1")
        assert len(int1_metrics) == 2
        
        latency_metrics = health_monitor.get_metrics(metric_name="latency")
        assert len(latency_metrics) == 2
    
    def test_acknowledge_alert(self, health_monitor):
        """Test acknowledging an alert"""
        alert = HealthAlert(
            id="alert-1",
            integration_id="int-1",
            severity=AlertSeverity.ERROR,
            message="Test"
        )
        health_monitor._alerts.append(alert)
        
        result = health_monitor.acknowledge_alert("alert-1")
        
        assert result is True
        assert alert.acknowledged is True
    
    def test_resolve_alert(self, health_monitor):
        """Test resolving an alert"""
        alert = HealthAlert(
            id="alert-1",
            integration_id="int-1",
            severity=AlertSeverity.WARNING,
            message="Test"
        )
        health_monitor._alerts.append(alert)
        
        result = health_monitor.resolve_alert("alert-1")
        
        assert result is True
        assert alert.resolved is True
    
    def test_get_alerts(self, health_monitor):
        """Test getting alerts"""
        health_monitor._alerts = [
            HealthAlert("a1", "i1", AlertSeverity.ERROR, "E1", resolved=False),
            HealthAlert("a2", "i1", AlertSeverity.WARNING, "W1", resolved=True),
            HealthAlert("a3", "i2", AlertSeverity.ERROR, "E2", resolved=False)
        ]
        
        # Get all unresolved
        alerts = health_monitor.get_alerts(include_resolved=False)
        assert len(alerts) == 2
        
        # Get by integration
        alerts = health_monitor.get_alerts(integration_id="i1", include_resolved=True)
        assert len(alerts) == 2
    
    def test_get_summary(self, health_monitor, integration_hub, mock_connector):
        """Test getting health summary"""
        integration_hub.register_integration(
            name="test",
            integration_type=IntegrationType.CRM,
            connector=mock_connector,
            config={}
        )
        
        summary = health_monitor.get_summary()
        
        assert "total_integrations" in summary
        assert summary["total_integrations"] == 1


# Integration Tests
class TestIntegrationOrchestration:
    """Integration tests for orchestration"""
    
    @pytest.mark.asyncio
    async def test_full_integration_flow(self, integration_hub, mock_connector):
        """Test full integration registration and connection flow"""
        # Register
        instance = integration_hub.register_integration(
            name="test_crm",
            integration_type=IntegrationType.CRM,
            connector=mock_connector,
            config={"url": "https://test.crm.com"}
        )
        
        assert instance is not None
        assert instance.status == IntegrationStatus.DISCONNECTED
        
        # Connect
        result = await integration_hub.connect_integration(instance.id)
        assert result is True
        assert instance.status == IntegrationStatus.CONNECTED
        
        # Disconnect
        result = await integration_hub.disconnect_integration(instance.id)
        assert result is True
        assert instance.status == IntegrationStatus.DISCONNECTED
    
    def test_enum_values(self):
        """Test enum values are correct"""
        assert IntegrationType.CRM.value == "crm"
        assert IntegrationType.ERP.value == "erp"
        assert IntegrationType.WAREHOUSE.value == "warehouse"
        
        assert IntegrationStatus.CONNECTED.value == "connected"
        assert IntegrationStatus.DISCONNECTED.value == "disconnected"
        
        assert HealthStatus.HEALTHY.value == "healthy"
        assert HealthStatus.UNHEALTHY.value == "unhealthy"
        
        assert AlertSeverity.INFO.value == "info"
        assert AlertSeverity.CRITICAL.value == "critical"
