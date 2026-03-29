"""
Unit Tests for Audit Export Module.

Tests for audit log export functionality including:
- CSV export with all required fields
- Date range filtering
- Field validation
"""

import pytest
import csv
import io
from datetime import datetime, timezone, timedelta

from backend.compliance.audit_export import (
    AuditExporter,
    AuditLogEntry,
    AuditExportConfig,
    get_audit_exporter
)


class TestAuditLogEntry:
    """Tests for AuditLogEntry model."""
    
    def test_entry_creation(self):
        """Test creating an audit log entry."""
        entry = AuditLogEntry(
            entry_id="audit-123",
            tenant_id="tenant-456",
            user_id="user-789",
            action="login",
            resource_type="session",
            resource_id="session-123",
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0",
            status="success",
            timestamp=datetime.now(timezone.utc)
        )
        
        assert entry.entry_id == "audit-123"
        assert entry.action == "login"
        assert entry.status == "success"
    
    def test_to_csv_row(self):
        """Test converting entry to CSV row."""
        timestamp = datetime(2026, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        entry = AuditLogEntry(
            entry_id="audit-123",
            tenant_id="tenant-456",
            user_id="user-789",
            action="login",
            resource_type="session",
            resource_id="session-123",
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0",
            status="success",
            timestamp=timestamp,
            details={"key": "value"}
        )
        
        row = entry.to_csv_row()
        
        assert row["entry_id"] == "audit-123"
        assert row["tenant_id"] == "tenant-456"
        assert row["user_id"] == "user-789"
        assert row["action"] == "login"
        assert row["ip_address"] == "192.168.1.1"
        assert row["status"] == "success"


class TestAuditExporter:
    """Tests for AuditExporter class."""
    
    def test_export_to_csv_all_fields(self):
        """Test CSV export with all required fields - CRITICAL TEST."""
        exporter = AuditExporter()
        
        # Add some entries
        entries = [
            AuditLogEntry(
                entry_id="audit-1",
                tenant_id="tenant-123",
                user_id="user-1",
                action="login",
                resource_type="session",
                resource_id="session-1",
                ip_address="192.168.1.1",
                user_agent="Mozilla/5.0",
                status="success",
                timestamp=datetime.now(timezone.utc)
            ),
            AuditLogEntry(
                entry_id="audit-2",
                tenant_id="tenant-123",
                user_id="user-2",
                action="api_call",
                resource_type="api",
                resource_id="/api/v1/tickets",
                ip_address="192.168.1.2",
                user_agent="curl/7.68.0",
                status="success",
                timestamp=datetime.now(timezone.utc)
            )
        ]
        
        for entry in entries:
            exporter.add_entry(entry)
        
        # Export to CSV
        csv_content = exporter.export_to_csv(tenant_id="tenant-123")
        
        # Parse CSV and verify all required fields
        reader = csv.DictReader(io.StringIO(csv_content))
        rows = list(reader)
        
        assert len(rows) == 2
        
        # Verify all required fields are present
        required_fields = [
            "entry_id", "tenant_id", "user_id", "action",
            "resource_type", "resource_id", "ip_address",
            "user_agent", "status", "timestamp", "details"
        ]
        
        for field in required_fields:
            assert field in rows[0], f"Missing required field: {field}"
    
    def test_export_with_date_filter(self):
        """Test CSV export with date filtering."""
        exporter = AuditExporter()
        
        now = datetime.now(timezone.utc)
        
        # Add entries with different dates
        entries = [
            AuditLogEntry(
                entry_id="audit-old",
                tenant_id="tenant-123",
                user_id="user-1",
                action="login",
                resource_type="session",
                resource_id="session-1",
                ip_address="192.168.1.1",
                user_agent="Mozilla/5.0",
                status="success",
                timestamp=now - timedelta(days=30)
            ),
            AuditLogEntry(
                entry_id="audit-new",
                tenant_id="tenant-123",
                user_id="user-1",
                action="login",
                resource_type="session",
                resource_id="session-2",
                ip_address="192.168.1.1",
                user_agent="Mozilla/5.0",
                status="success",
                timestamp=now - timedelta(days=1)
            )
        ]
        
        for entry in entries:
            exporter.add_entry(entry)
        
        # Export with date filter (last 7 days)
        start_date = now - timedelta(days=7)
        end_date = now
        
        csv_content = exporter.export_to_csv(
            tenant_id="tenant-123",
            start_date=start_date,
            end_date=end_date
        )
        
        reader = csv.DictReader(io.StringIO(csv_content))
        rows = list(reader)
        
        # Only the recent entry should be included
        assert len(rows) == 1
        assert rows[0]["entry_id"] == "audit-new"
    
    def test_export_with_action_filter(self):
        """Test CSV export with action filter."""
        exporter = AuditExporter()
        
        now = datetime.now(timezone.utc)
        
        # Add different action types
        entries = [
            AuditLogEntry(
                entry_id="audit-1",
                tenant_id="tenant-123",
                user_id="user-1",
                action="login",
                resource_type="session",
                resource_id="session-1",
                ip_address="192.168.1.1",
                user_agent="Mozilla/5.0",
                status="success",
                timestamp=now
            ),
            AuditLogEntry(
                entry_id="audit-2",
                tenant_id="tenant-123",
                user_id="user-1",
                action="api_call",
                resource_type="api",
                resource_id="/api/v1/tickets",
                ip_address="192.168.1.1",
                user_agent="curl/7.68.0",
                status="success",
                timestamp=now
            )
        ]
        
        for entry in entries:
            exporter.add_entry(entry)
        
        # Export only login actions
        csv_content = exporter.export_to_csv(
            tenant_id="tenant-123",
            actions=["login"]
        )
        
        reader = csv.DictReader(io.StringIO(csv_content))
        rows = list(reader)
        
        assert len(rows) == 1
        assert rows[0]["action"] == "login"
    
    def test_csv_format_valid(self):
        """Test that exported CSV is valid."""
        exporter = AuditExporter()
        
        entry = AuditLogEntry(
            entry_id="audit-1",
            tenant_id="tenant-123",
            user_id="user-1",
            action="login",
            resource_type="session",
            resource_id="session-1",
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0",
            status="success",
            timestamp=datetime.now(timezone.utc)
        )
        
        exporter.add_entry(entry)
        
        csv_content = exporter.export_to_csv(tenant_id="tenant-123")
        
        # Should parse without error
        reader = csv.DictReader(io.StringIO(csv_content))
        rows = list(reader)
        
        assert len(rows) == 1
    
    def test_get_audit_exporter(self):
        """Test factory function."""
        exporter = get_audit_exporter()
        
        assert exporter is not None
        assert isinstance(exporter, AuditExporter)


class TestAuditExportConfig:
    """Tests for audit export configuration."""
    
    def test_default_config(self):
        """Test default export configuration."""
        config = AuditExportConfig()
        
        assert config.include_ip_address is True
        assert config.include_user_agent is True
        assert config.date_format == "iso8601"
    
    def test_custom_config(self):
        """Test custom export configuration."""
        config = AuditExportConfig(
            include_ip_address=False,
            include_user_agent=False,
            date_format="unix"
        )
        
        assert config.include_ip_address is False
        assert config.include_user_agent is False
        assert config.date_format == "unix"
