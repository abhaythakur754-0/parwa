# Tests for Builder 5 - Global DNS
# Week 51: dns_manager.py, dns_failover.py, dns_monitor.py

import pytest
from datetime import datetime, timedelta

from enterprise.global_infra.dns_manager import (
    DNSManager, DNSRecord, DNSZone, RecordType, RecordStatus
)
from enterprise.global_infra.dns_failover import (
    DNSFailover, FailoverEndpoint, FailoverGroup, FailoverEvent,
    FailoverPolicy, FailoverStatus
)
from enterprise.global_infra.dns_monitor import (
    DNSMonitor, HealthCheck, HealthCheckResult, DNSAlert,
    MonitorStatus, CheckType
)


# =============================================================================
# DNS MANAGER TESTS
# =============================================================================

class TestDNSManager:
    """Tests for DNSManager class"""

    def test_init(self):
        """Test manager initialization"""
        manager = DNSManager()
        assert manager is not None
        metrics = manager.get_metrics()
        assert metrics["total_zones"] == 0

    def test_create_zone(self):
        """Test creating a zone"""
        manager = DNSManager()
        zone = manager.create_zone(
            name="main",
            domain="example.com",
            nameservers=["ns1.example.com", "ns2.example.com"]
        )
        assert zone.name == "main"
        assert zone.domain == "example.com"
        assert len(zone.nameservers) == 2

    def test_delete_zone(self):
        """Test deleting a zone"""
        manager = DNSManager()
        zone = manager.create_zone("main", "example.com")
        result = manager.delete_zone(zone.id)
        assert result is True
        assert manager.get_zone(zone.id) is None

    def test_create_record(self):
        """Test creating a DNS record"""
        manager = DNSManager()
        zone = manager.create_zone("main", "example.com")
        record = manager.create_record(
            zone_id=zone.id,
            name="www",
            record_type=RecordType.A,
            value="192.168.1.1",
            ttl=300
        )
        assert record.name == "www"
        assert record.record_type == RecordType.A
        assert record.value == "192.168.1.1"

    def test_create_mx_record(self):
        """Test creating an MX record with priority"""
        manager = DNSManager()
        zone = manager.create_zone("main", "example.com")
        record = manager.create_record(
            zone_id=zone.id,
            name="@",
            record_type=RecordType.MX,
            value="mail.example.com",
            priority=10
        )
        assert record.priority == 10

    def test_update_record(self):
        """Test updating a record"""
        manager = DNSManager()
        zone = manager.create_zone("main", "example.com")
        record = manager.create_record(zone.id, "www", RecordType.A, "192.168.1.1")
        result = manager.update_record(record.id, value="192.168.1.2")
        assert result is True
        assert record.value == "192.168.1.2"

    def test_delete_record(self):
        """Test deleting a record"""
        manager = DNSManager()
        zone = manager.create_zone("main", "example.com")
        record = manager.create_record(zone.id, "www", RecordType.A, "192.168.1.1")
        result = manager.delete_record(record.id)
        assert result is True
        assert manager.get_record(record.id) is None

    def test_get_zone_by_domain(self):
        """Test getting zone by domain"""
        manager = DNSManager()
        manager.create_zone("main", "example.com")
        zone = manager.get_zone_by_domain("example.com")
        assert zone is not None

    def test_get_records_by_zone(self):
        """Test getting records by zone"""
        manager = DNSManager()
        zone = manager.create_zone("main", "example.com")
        manager.create_record(zone.id, "www", RecordType.A, "192.168.1.1")
        manager.create_record(zone.id, "api", RecordType.A, "192.168.1.2")
        records = manager.get_records_by_zone(zone.id)
        assert len(records) == 2

    def test_get_records_by_type(self):
        """Test getting records by type"""
        manager = DNSManager()
        zone = manager.create_zone("main", "example.com")
        manager.create_record(zone.id, "www", RecordType.A, "192.168.1.1")
        manager.create_record(zone.id, "www", RecordType.AAAA, "::1")
        records = manager.get_records_by_type(zone.id, RecordType.A)
        assert len(records) == 1

    def test_resolve(self):
        """Test DNS resolution"""
        manager = DNSManager()
        zone = manager.create_zone("main", "example.com")
        manager.create_record(zone.id, "www", RecordType.A, "192.168.1.1")
        records = manager.resolve("example.com", "www", RecordType.A)
        assert len(records) == 1
        assert records[0].value == "192.168.1.1"

    def test_enable_health_check(self):
        """Test enabling health check"""
        manager = DNSManager()
        zone = manager.create_zone("main", "example.com")
        record = manager.create_record(zone.id, "www", RecordType.A, "192.168.1.1")
        result = manager.enable_health_check(record.id)
        assert result is True
        assert record.health_check_enabled is True

    def test_get_metrics(self):
        """Test getting metrics"""
        manager = DNSManager()
        zone = manager.create_zone("main", "example.com")
        manager.create_record(zone.id, "www", RecordType.A, "192.168.1.1")

        metrics = manager.get_metrics()
        assert metrics["total_zones"] == 1
        assert metrics["total_records"] == 1


# =============================================================================
# DNS FAILOVER TESTS
# =============================================================================

class TestDNSFailover:
    """Tests for DNSFailover class"""

    def test_init(self):
        """Test failover initialization"""
        failover = DNSFailover()
        assert failover is not None
        metrics = failover.get_metrics()
        assert metrics["total_groups"] == 0

    def test_create_group(self):
        """Test creating a failover group"""
        failover = DNSFailover()
        group = failover.create_group(
            name="main-site",
            domain="www.example.com",
            policy=FailoverPolicy.ACTIVE_PASSIVE
        )
        assert group.name == "main-site"
        assert group.policy == FailoverPolicy.ACTIVE_PASSIVE

    def test_delete_group(self):
        """Test deleting a group"""
        failover = DNSFailover()
        group = failover.create_group("main", "example.com")
        result = failover.delete_group(group.id)
        assert result is True
        assert failover.get_group(group.id) is None

    def test_add_endpoint(self):
        """Test adding an endpoint"""
        failover = DNSFailover()
        group = failover.create_group("main", "example.com")
        ep = failover.add_endpoint(
            group_id=group.id,
            name="primary",
            endpoint="192.168.1.1",
            is_primary=True
        )
        assert ep is not None
        assert ep.is_primary is True
        assert group.primary_endpoint_id == ep.id

    def test_remove_endpoint(self):
        """Test removing an endpoint"""
        failover = DNSFailover()
        group = failover.create_group("main", "example.com")
        ep = failover.add_endpoint(group.id, "primary", "192.168.1.1")
        result = failover.remove_endpoint(ep.id)
        assert result is True

    def test_update_endpoint_health_healthy(self):
        """Test updating endpoint health"""
        failover = DNSFailover()
        group = failover.create_group("main", "example.com")
        ep = failover.add_endpoint(group.id, "primary", "192.168.1.1", is_primary=True)

        result = failover.update_endpoint_health(ep.id, is_healthy=True)
        assert result is None  # No failover needed
        assert ep.is_healthy is True

    def test_update_endpoint_health_triggers_failover(self):
        """Test that health update triggers failover"""
        failover = DNSFailover()
        group = failover.create_group("main", "example.com", failover_threshold=2)
        ep1 = failover.add_endpoint(group.id, "primary", "192.168.1.1", is_primary=True)
        ep2 = failover.add_endpoint(group.id, "secondary", "192.168.1.2", priority=2)

        # Multiple failures to trigger failover
        failover.update_endpoint_health(ep1.id, is_healthy=False)
        failover_id = failover.update_endpoint_health(ep1.id, is_healthy=False)

        assert failover_id == ep2.id  # Failed over to secondary
        assert group.status == FailoverStatus.FAILOVER_ACTIVE

    def test_get_active_endpoint(self):
        """Test getting active endpoint"""
        failover = DNSFailover()
        group = failover.create_group("main", "example.com")
        ep = failover.add_endpoint(group.id, "primary", "192.168.1.1", is_primary=True)

        active = failover.get_active_endpoint(group.id)
        assert active.id == ep.id

    def test_get_endpoints_by_group(self):
        """Test getting endpoints by group"""
        failover = DNSFailover()
        group = failover.create_group("main", "example.com")
        failover.add_endpoint(group.id, "ep1", "192.168.1.1")
        failover.add_endpoint(group.id, "ep2", "192.168.1.2")

        endpoints = failover.get_endpoints_by_group(group.id)
        assert len(endpoints) == 2

    def test_get_failover_history(self):
        """Test getting failover history"""
        failover = DNSFailover()
        group = failover.create_group("main", "example.com", failover_threshold=1)
        ep1 = failover.add_endpoint(group.id, "primary", "192.168.1.1", is_primary=True)
        failover.add_endpoint(group.id, "secondary", "192.168.1.2")

        # Trigger failover
        failover.update_endpoint_health(ep1.id, is_healthy=False)

        history = failover.get_failover_history(group.id)
        assert len(history) == 1

    def test_get_metrics(self):
        """Test getting metrics"""
        failover = DNSFailover()
        failover.create_group("main", "example.com")

        metrics = failover.get_metrics()
        assert metrics["total_groups"] == 1


# =============================================================================
# DNS MONITOR TESTS
# =============================================================================

class TestDNSMonitor:
    """Tests for DNSMonitor class"""

    def test_init(self):
        """Test monitor initialization"""
        monitor = DNSMonitor()
        assert monitor is not None
        metrics = monitor.get_metrics()
        assert metrics["total_checks"] == 0

    def test_create_check(self):
        """Test creating a health check"""
        monitor = DNSMonitor()
        check = monitor.create_check(
            name="api-health",
            check_type=CheckType.HTTPS,
            target="https://api.example.com/health"
        )
        assert check.name == "api-health"
        assert check.check_type == CheckType.HTTPS

    def test_delete_check(self):
        """Test deleting a health check"""
        monitor = DNSMonitor()
        check = monitor.create_check("api", CheckType.HTTPS, "https://api.example.com")
        result = monitor.delete_check(check.id)
        assert result is True
        assert monitor.get_check(check.id) is None

    def test_execute_check_healthy(self):
        """Test executing a healthy check"""
        monitor = DNSMonitor()
        check = monitor.create_check("api", CheckType.HTTPS, "https://api.example.com")
        result = monitor.execute_check(
            check_id=check.id,
            status=MonitorStatus.HEALTHY,
            response_time_ms=50.0,
            status_code=200
        )
        assert result is not None
        assert check.last_status == MonitorStatus.HEALTHY
        assert check.consecutive_successes == 1

    def test_execute_check_unhealthy(self):
        """Test executing an unhealthy check"""
        monitor = DNSMonitor()
        check = monitor.create_check("api", CheckType.HTTPS, "https://api.example.com", threshold=1)
        result = monitor.execute_check(
            check_id=check.id,
            status=MonitorStatus.UNHEALTHY,
            response_time_ms=0,
            message="Connection refused"
        )
        assert result is not None
        assert check.consecutive_failures == 1

    def test_alert_raised_on_threshold(self):
        """Test that alert is raised when threshold exceeded"""
        monitor = DNSMonitor()
        check = monitor.create_check("api", CheckType.HTTPS, "https://api.example.com", threshold=2)

        monitor.execute_check(check.id, MonitorStatus.UNHEALTHY, message="Failed")
        monitor.execute_check(check.id, MonitorStatus.UNHEALTHY, message="Failed again")

        alerts = monitor.get_unacknowledged_alerts()
        assert len(alerts) == 1

    def test_acknowledge_alert(self):
        """Test acknowledging an alert"""
        monitor = DNSMonitor()
        check = monitor.create_check("api", CheckType.HTTPS, "https://api.example.com", threshold=1)
        monitor.execute_check(check.id, MonitorStatus.UNHEALTHY, message="Failed")

        alerts = monitor.get_unacknowledged_alerts()
        result = monitor.acknowledge_alert(alerts[0].id)
        assert result is True
        assert len(monitor.get_unacknowledged_alerts()) == 0

    def test_get_results(self):
        """Test getting check results"""
        monitor = DNSMonitor()
        check = monitor.create_check("api", CheckType.HTTPS, "https://api.example.com")
        monitor.execute_check(check.id, MonitorStatus.HEALTHY)
        monitor.execute_check(check.id, MonitorStatus.HEALTHY)

        results = monitor.get_results(check.id)
        assert len(results) == 2

    def test_enable_disable_check(self):
        """Test enabling and disabling checks"""
        monitor = DNSMonitor()
        check = monitor.create_check("api", CheckType.HTTPS, "https://api.example.com")
        monitor.disable_check(check.id)
        assert check.enabled is False

        monitor.enable_check(check.id)
        assert check.enabled is True

    def test_get_overall_health(self):
        """Test getting overall health"""
        monitor = DNSMonitor()
        c1 = monitor.create_check("api1", CheckType.HTTPS, "https://api1.example.com")
        c2 = monitor.create_check("api2", CheckType.HTTPS, "https://api2.example.com")

        monitor.execute_check(c1.id, MonitorStatus.HEALTHY)
        monitor.execute_check(c2.id, MonitorStatus.HEALTHY)

        health = monitor.get_overall_health()
        assert health == MonitorStatus.HEALTHY

    def test_get_availability(self):
        """Test calculating availability"""
        monitor = DNSMonitor()
        check = monitor.create_check("api", CheckType.HTTPS, "https://api.example.com")

        monitor.execute_check(check.id, MonitorStatus.HEALTHY)
        monitor.execute_check(check.id, MonitorStatus.HEALTHY)
        monitor.execute_check(check.id, MonitorStatus.UNHEALTHY)

        availability = monitor.get_availability(check.id, hours=24)
        assert availability == pytest.approx(66.67, rel=0.01)

    def test_get_avg_response_time(self):
        """Test getting average response time"""
        monitor = DNSMonitor()
        check = monitor.create_check("api", CheckType.HTTPS, "https://api.example.com")

        monitor.execute_check(check.id, MonitorStatus.HEALTHY, response_time_ms=50.0)
        monitor.execute_check(check.id, MonitorStatus.HEALTHY, response_time_ms=100.0)

        avg_time = monitor.get_avg_response_time(check.id)
        assert avg_time == 75.0

    def test_get_metrics(self):
        """Test getting metrics"""
        monitor = DNSMonitor()
        monitor.create_check("api", CheckType.HTTPS, "https://api.example.com")

        metrics = monitor.get_metrics()
        assert metrics["total_checks"] == 1
        assert metrics["active_checks"] == 1
