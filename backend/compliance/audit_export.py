"""
Audit Export Module for Enterprise Compliance.

This module provides audit log export functionality including
CSV export with all required fields for compliance reporting.
"""

import csv
import io
import json
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from enum import Enum

from pydantic import BaseModel, Field


class AuditLogEntry(BaseModel):
    """Audit log entry model."""
    
    entry_id: str
    tenant_id: str
    user_id: str
    action: str
    resource_type: str
    resource_id: str
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    status: str  # success, failure, denied
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    details: Dict[str, Any] = Field(default_factory=dict)
    
    def to_csv_row(self) -> Dict[str, str]:
        """Convert to CSV row dictionary."""
        return {
            "entry_id": self.entry_id,
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "action": self.action,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "ip_address": self.ip_address or "",
            "user_agent": self.user_agent or "",
            "status": self.status,
            "timestamp": self.timestamp.isoformat(),
            "details": json.dumps(self.details) if self.details else ""
        }


class AuditExportConfig(BaseModel):
    """Configuration for audit export."""
    
    include_ip_address: bool = True
    include_user_agent: bool = True
    include_details: bool = True
    date_format: str = "iso8601"  # iso8601, unix, custom
    custom_date_format: str = "%Y-%m-%d %H:%M:%S"


class AuditExporter:
    """
    Audit log exporter for compliance reporting.
    
    Provides CSV export functionality with all required fields
    for SOC 2, GDPR, and other compliance frameworks.
    """
    
    # Required fields for compliance
    REQUIRED_FIELDS = [
        "entry_id",
        "tenant_id",
        "user_id",
        "action",
        "resource_type",
        "resource_id",
        "ip_address",
        "user_agent",
        "status",
        "timestamp",
        "details"
    ]
    
    def __init__(self, config: Optional[AuditExportConfig] = None):
        """
        Initialize audit exporter.
        
        Args:
            config: Export configuration
        """
        self.config = config or AuditExportConfig()
        self._entries: Dict[str, List[AuditLogEntry]] = {}
    
    def add_entry(self, entry: AuditLogEntry) -> None:
        """
        Add an audit log entry.
        
        Args:
            entry: Audit log entry to add
        """
        if entry.tenant_id not in self._entries:
            self._entries[entry.tenant_id] = []
        self._entries[entry.tenant_id].append(entry)
    
    def log_event(
        self,
        tenant_id: str,
        user_id: str,
        action: str,
        resource_type: str,
        resource_id: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        status: str = "success",
        details: Optional[Dict[str, Any]] = None
    ) -> AuditLogEntry:
        """
        Log an audit event.
        
        Args:
            tenant_id: Tenant identifier
            user_id: User identifier
            action: Action performed
            resource_type: Type of resource
            resource_id: Resource identifier
            ip_address: IP address
            user_agent: User agent
            status: Event status
            details: Additional details
            
        Returns:
            Created AuditLogEntry
        """
        import uuid
        
        entry = AuditLogEntry(
            entry_id=f"audit_{uuid.uuid4().hex[:12]}",
            tenant_id=tenant_id,
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            ip_address=ip_address,
            user_agent=user_agent,
            status=status,
            details=details or {}
        )
        
        self.add_entry(entry)
        return entry
    
    def export_to_csv(
        self,
        tenant_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        actions: Optional[List[str]] = None,
        users: Optional[List[str]] = None
    ) -> str:
        """
        Export audit logs to CSV format.
        
        Args:
            tenant_id: Tenant identifier
            start_date: Start date filter
            end_date: End date filter
            actions: Filter by actions
            users: Filter by user IDs
            
        Returns:
            CSV content as string
        """
        entries = self._entries.get(tenant_id, [])
        
        # Apply filters
        filtered = []
        for entry in entries:
            # Date filter
            if start_date and entry.timestamp < start_date:
                continue
            if end_date and entry.timestamp > end_date:
                continue
            
            # Action filter
            if actions and entry.action not in actions:
                continue
            
            # User filter
            if users and entry.user_id not in users:
                continue
            
            filtered.append(entry)
        
        # Sort by timestamp
        filtered.sort(key=lambda e: e.timestamp)
        
        # Generate CSV
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=self.REQUIRED_FIELDS)
        writer.writeheader()
        
        for entry in filtered:
            row = entry.to_csv_row()
            
            # Apply config
            if not self.config.include_ip_address:
                row["ip_address"] = ""
            if not self.config.include_user_agent:
                row["user_agent"] = ""
            if not self.config.include_details:
                row["details"] = ""
            
            writer.writerow(row)
        
        return output.getvalue()
    
    def get_entries(
        self,
        tenant_id: str,
        limit: int = 100,
        offset: int = 0
    ) -> List[AuditLogEntry]:
        """
        Get audit log entries for a tenant.
        
        Args:
            tenant_id: Tenant identifier
            limit: Maximum number of entries
            offset: Offset for pagination
            
        Returns:
            List of audit log entries
        """
        entries = self._entries.get(tenant_id, [])
        entries.sort(key=lambda e: e.timestamp, reverse=True)
        return entries[offset:offset + limit]
    
    def get_entry_count(self, tenant_id: str) -> int:
        """Get count of entries for a tenant."""
        return len(self._entries.get(tenant_id, []))
    
    def get_actions_summary(
        self,
        tenant_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, int]:
        """
        Get summary of actions performed.
        
        Args:
            tenant_id: Tenant identifier
            start_date: Start date filter
            end_date: End date filter
            
        Returns:
            Dictionary of action counts
        """
        entries = self._entries.get(tenant_id, [])
        summary = {}
        
        for entry in entries:
            if start_date and entry.timestamp < start_date:
                continue
            if end_date and entry.timestamp > end_date:
                continue
            
            action = entry.action
            summary[action] = summary.get(action, 0) + 1
        
        return summary
    
    def cleanup_old_entries(
        self,
        tenant_id: str,
        days_to_keep: int = 90
    ) -> int:
        """
        Clean up old audit entries.
        
        Args:
            tenant_id: Tenant identifier
            days_to_keep: Number of days to keep
            
        Returns:
            Number of entries removed
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=days_to_keep)
        entries = self._entries.get(tenant_id, [])
        
        original_count = len(entries)
        self._entries[tenant_id] = [e for e in entries if e.timestamp >= cutoff]
        
        return original_count - len(self._entries[tenant_id])


# Global exporter instance
_audit_exporter: Optional[AuditExporter] = None


def get_audit_exporter() -> AuditExporter:
    """Get the global audit exporter instance."""
    global _audit_exporter
    if _audit_exporter is None:
        _audit_exporter = AuditExporter()
    return _audit_exporter
