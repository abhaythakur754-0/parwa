# DNS Manager - Week 51 Builder 5
# DNS management

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum
import uuid


class RecordType(Enum):
    A = "A"
    AAAA = "AAAA"
    CNAME = "CNAME"
    MX = "MX"
    TXT = "TXT"
    NS = "NS"
    SRV = "SRV"


class RecordStatus(Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"


@dataclass
class DNSRecord:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    record_type: RecordType = RecordType.A
    value: str = ""
    ttl: int = 300
    priority: Optional[int] = None
    status: RecordStatus = RecordStatus.ACTIVE
    region: str = ""
    health_check_enabled: bool = False
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None


@dataclass
class DNSZone:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    domain: str = ""
    records: List[str] = field(default_factory=list)
    nameservers: List[str] = field(default_factory=list)
    enabled: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)


class DNSManager:
    """Manages DNS records and zones"""

    def __init__(self):
        self._zones: Dict[str, DNSZone] = {}
        self._records: Dict[str, DNSRecord] = {}
        self._metrics = {
            "total_zones": 0,
            "total_records": 0,
            "by_type": {},
            "queries": 0
        }

    def create_zone(
        self,
        name: str,
        domain: str,
        nameservers: Optional[List[str]] = None
    ) -> DNSZone:
        """Create a DNS zone"""
        zone = DNSZone(
            name=name,
            domain=domain,
            nameservers=nameservers or []
        )
        self._zones[zone.id] = zone
        self._metrics["total_zones"] += 1
        return zone

    def delete_zone(self, zone_id: str) -> bool:
        """Delete a DNS zone"""
        if zone_id not in self._zones:
            return False

        zone = self._zones[zone_id]
        # Delete all records in zone
        for record_id in zone.records:
            if record_id in self._records:
                del self._records[record_id]

        del self._zones[zone_id]
        self._metrics["total_zones"] -= 1
        return True

    def create_record(
        self,
        zone_id: str,
        name: str,
        record_type: RecordType,
        value: str,
        ttl: int = 300,
        priority: Optional[int] = None,
        region: str = ""
    ) -> Optional[DNSRecord]:
        """Create a DNS record"""
        zone = self._zones.get(zone_id)
        if not zone:
            return None

        record = DNSRecord(
            name=name,
            record_type=record_type,
            value=value,
            ttl=ttl,
            priority=priority,
            region=region
        )

        self._records[record.id] = record
        zone.records.append(record.id)
        self._metrics["total_records"] += 1

        type_key = record_type.value
        self._metrics["by_type"][type_key] = \
            self._metrics["by_type"].get(type_key, 0) + 1

        return record

    def update_record(
        self,
        record_id: str,
        **kwargs
    ) -> bool:
        """Update a DNS record"""
        record = self._records.get(record_id)
        if not record:
            return False

        for key, value in kwargs.items():
            if hasattr(record, key):
                setattr(record, key, value)
        record.updated_at = datetime.utcnow()
        return True

    def delete_record(self, record_id: str) -> bool:
        """Delete a DNS record"""
        record = self._records.get(record_id)
        if not record:
            return False

        # Remove from zone
        for zone in self._zones.values():
            if record_id in zone.records:
                zone.records.remove(record_id)

        del self._records[record_id]
        self._metrics["total_records"] -= 1
        return True

    def get_zone(self, zone_id: str) -> Optional[DNSZone]:
        """Get zone by ID"""
        return self._zones.get(zone_id)

    def get_zone_by_domain(self, domain: str) -> Optional[DNSZone]:
        """Get zone by domain"""
        for zone in self._zones.values():
            if zone.domain == domain:
                return zone
        return None

    def get_record(self, record_id: str) -> Optional[DNSRecord]:
        """Get record by ID"""
        return self._records.get(record_id)

    def get_records_by_zone(self, zone_id: str) -> List[DNSRecord]:
        """Get all records in a zone"""
        zone = self._zones.get(zone_id)
        if not zone:
            return []
        return [self._records[r] for r in zone.records if r in self._records]

    def get_records_by_name(
        self,
        zone_id: str,
        name: str
    ) -> List[DNSRecord]:
        """Get records by name in a zone"""
        records = self.get_records_by_zone(zone_id)
        return [r for r in records if r.name == name]

    def get_records_by_type(
        self,
        zone_id: str,
        record_type: RecordType
    ) -> List[DNSRecord]:
        """Get records by type in a zone"""
        records = self.get_records_by_zone(zone_id)
        return [r for r in records if r.record_type == record_type]

    def resolve(
        self,
        domain: str,
        name: str,
        record_type: RecordType
    ) -> List[DNSRecord]:
        """Resolve DNS query"""
        self._metrics["queries"] += 1

        zone = self.get_zone_by_domain(domain)
        if not zone:
            return []

        records = self.get_records_by_name(zone.id, name)
        return [r for r in records if r.record_type == record_type and r.status == RecordStatus.ACTIVE]

    def enable_health_check(self, record_id: str) -> bool:
        """Enable health check for a record"""
        record = self._records.get(record_id)
        if not record:
            return False
        record.health_check_enabled = True
        return True

    def disable_health_check(self, record_id: str) -> bool:
        """Disable health check for a record"""
        record = self._records.get(record_id)
        if not record:
            return False
        record.health_check_enabled = False
        return True

    def get_records_with_health_checks(self) -> List[DNSRecord]:
        """Get all records with health checks enabled"""
        return [r for r in self._records.values() if r.health_check_enabled]

    def get_metrics(self) -> Dict[str, Any]:
        """Get DNS metrics"""
        return self._metrics.copy()
