"""
GDPR Export Handler for Data Residency.

Handles GDPR data export requests:
- Export all client data from assigned region
- Only data from client's region
- Portable format (JSON)
- Right to erasure support
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum
import json
import logging

logger = logging.getLogger(__name__)


class Region(str, Enum):
    """Available regions."""
    EU = "eu-west-1"
    US = "us-east-1"
    APAC = "ap-southeast-1"


class ExportStatus(str, Enum):
    """Status of export request."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ExportRequest:
    """GDPR export request."""
    request_id: str
    client_id: str
    region: Region
    requested_at: datetime = field(default_factory=datetime.now)
    status: ExportStatus = ExportStatus.PENDING
    completed_at: Optional[datetime] = None
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "request_id": self.request_id,
            "client_id": self.client_id,
            "region": self.region.value,
            "requested_at": self.requested_at.isoformat(),
            "status": self.status.value,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error": self.error
        }


@dataclass
class DataInventory:
    """Inventory of data stored for a client."""
    client_id: str
    region: Region
    data_types: List[str]
    total_records: int
    size_bytes: int
    last_updated: datetime

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "client_id": self.client_id,
            "region": self.region.value,
            "data_types": self.data_types,
            "total_records": self.total_records,
            "size_bytes": self.size_bytes,
            "last_updated": self.last_updated.isoformat()
        }


class GDPrexport:
    """
    Handles GDPR data export requests.

    Features:
    - Export all client data from assigned region
    - Only data from client's region
    - Portable format (JSON)
    - Complete data inventory
    - Right to erasure support
    """

    def __init__(
        self,
        client_region_mapping: Optional[Dict[str, Region]] = None,
        data_fetcher: Optional[callable] = None
    ):
        """
        Initialize the GDPR export handler.

        Args:
            client_region_mapping: Mapping of client IDs to regions
            data_fetcher: Function to fetch data from region
        """
        self._client_regions: Dict[str, Region] = client_region_mapping or {}
        self._data_fetcher = data_fetcher or self._default_data_fetcher
        self._export_requests: List[ExportRequest] = []
        self._inventories: Dict[str, DataInventory] = {}

    def _default_data_fetcher(
        self,
        client_id: str,
        region: Region
    ) -> Dict[str, Any]:
        """Default data fetcher (mock implementation)."""
        return {
            "client_id": client_id,
            "region": region.value,
            "exported_at": datetime.now().isoformat(),
            "data": {
                "profile": {
                    "id": client_id,
                    "created_at": "2024-01-01T00:00:00",
                    "settings": {"language": "en", "timezone": "UTC"}
                },
                "tickets": [
                    {"id": "T001", "subject": "Test ticket", "status": "resolved"},
                    {"id": "T002", "subject": "Another ticket", "status": "open"}
                ],
                "interactions": [
                    {"type": "chat", "timestamp": "2024-01-15T10:00:00"},
                    {"type": "email", "timestamp": "2024-01-16T14:30:00"}
                ]
            }
        }

    def register_client(self, client_id: str, region: Region) -> None:
        """Register a client with their assigned region."""
        self._client_regions[client_id] = region
        logger.info(f"Registered client {client_id} to region {region.value}")

    def get_client_region(self, client_id: str) -> Optional[Region]:
        """Get the assigned region for a client."""
        return self._client_regions.get(client_id)

    def request_export(self, client_id: str) -> ExportRequest:
        """
        Request a GDPR data export for a client.

        Args:
            client_id: Client identifier

        Returns:
            ExportRequest with request details
        """
        region = self.get_client_region(client_id)

        if not region:
            raise ValueError(f"Client {client_id} not registered to any region")

        request_id = f"export-{client_id}-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        request = ExportRequest(
            request_id=request_id,
            client_id=client_id,
            region=region
        )

        self._export_requests.append(request)
        logger.info(f"Export request {request_id} created for client {client_id}")

        return request

    def process_export(self, request_id: str) -> ExportRequest:
        """
        Process an export request.

        Args:
            request_id: Export request ID

        Returns:
            Updated ExportRequest with data
        """
        request = self._get_request(request_id)

        if not request:
            raise ValueError(f"Export request {request_id} not found")

        if request.status == ExportStatus.COMPLETED:
            return request

        request.status = ExportStatus.IN_PROGRESS

        try:
            # Fetch data from the assigned region ONLY
            data = self._data_fetcher(request.client_id, request.region)

            # Verify data is from correct region
            if data.get("region") != request.region.value:
                raise ValueError(
                    f"Data fetched from wrong region: expected {request.region.value}, "
                    f"got {data.get('region')}"
                )

            request.data = data
            request.status = ExportStatus.COMPLETED
            request.completed_at = datetime.now()

            logger.info(f"Export {request_id} completed for client {request.client_id}")

        except Exception as e:
            request.status = ExportStatus.FAILED
            request.error = str(e)
            logger.error(f"Export {request_id} failed: {e}")

        return request

    def get_export_data(self, request_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the exported data for a request.

        Args:
            request_id: Export request ID

        Returns:
            Exported data or None
        """
        request = self._get_request(request_id)

        if request and request.status == ExportStatus.COMPLETED:
            return request.data

        return None

    def get_export_json(self, request_id: str) -> Optional[str]:
        """
        Get the exported data as JSON string.

        Args:
            request_id: Export request ID

        Returns:
            JSON string of exported data
        """
        data = self.get_export_data(request_id)

        if data:
            return json.dumps(data, indent=2, default=str)

        return None

    def _get_request(self, request_id: str) -> Optional[ExportRequest]:
        """Get an export request by ID."""
        for request in self._export_requests:
            if request.request_id == request_id:
                return request
        return None

    def create_inventory(
        self,
        client_id: str,
        data_types: List[str],
        total_records: int,
        size_bytes: int
    ) -> DataInventory:
        """
        Create a data inventory for a client.

        Args:
            client_id: Client identifier
            data_types: Types of data stored
            total_records: Total number of records
            size_bytes: Total size in bytes

        Returns:
            DataInventory record
        """
        region = self.get_client_region(client_id)

        if not region:
            raise ValueError(f"Client {client_id} not registered")

        inventory = DataInventory(
            client_id=client_id,
            region=region,
            data_types=data_types,
            total_records=total_records,
            size_bytes=size_bytes,
            last_updated=datetime.now()
        )

        self._inventories[client_id] = inventory
        return inventory

    def get_inventory(self, client_id: str) -> Optional[DataInventory]:
        """Get the data inventory for a client."""
        return self._inventories.get(client_id)

    def get_client_requests(self, client_id: str) -> List[ExportRequest]:
        """Get all export requests for a client."""
        return [r for r in self._export_requests if r.client_id == client_id]

    def get_stats(self) -> Dict[str, Any]:
        """Get export handler statistics."""
        total = len(self._export_requests)
        completed = len([r for r in self._export_requests if r.status == ExportStatus.COMPLETED])
        failed = len([r for r in self._export_requests if r.status == ExportStatus.FAILED])
        pending = len([r for r in self._export_requests if r.status == ExportStatus.PENDING])

        return {
            "total_requests": total,
            "completed": completed,
            "failed": failed,
            "pending": pending,
            "total_inventories": len(self._inventories),
            "registered_clients": len(self._client_regions)
        }


def get_gdpr_export() -> GDPrexport:
    """Factory function to create a GDPR export handler."""
    return GDPrexport()
