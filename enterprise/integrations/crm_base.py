"""
Base CRM Integration Class
Enterprise Integration Hub - Week 43 Builder 1
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class SyncDirection(str, Enum):
    """Direction of data synchronization"""
    INBOUND = "inbound"
    OUTBOUND = "outbound"
    BIDIRECTIONAL = "bidirectional"


class SyncStatus(str, Enum):
    """Status of synchronization operation"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"


@dataclass
class CRMRecord:
    """Base CRM record representation"""
    id: str
    crm_type: str
    data: Dict[str, Any]
    last_modified: datetime
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "crm_type": self.crm_type,
            "data": self.data,
            "last_modified": self.last_modified.isoformat(),
            "created_at": self.created_at.isoformat()
        }


@dataclass
class SyncResult:
    """Result of a synchronization operation"""
    status: SyncStatus
    records_processed: int
    records_succeeded: int
    records_failed: int
    errors: List[str] = field(default_factory=list)
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "records_processed": self.records_processed,
            "records_succeeded": self.records_succeeded,
            "records_failed": self.records_failed,
            "errors": self.errors,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None
        }


@dataclass
class CRMConfig:
    """Configuration for CRM connection"""
    name: str
    api_url: str
    auth_type: str
    credentials: Dict[str, Any]
    sync_direction: SyncDirection = SyncDirection.BIDIRECTIONAL
    sync_interval_minutes: int = 15
    batch_size: int = 100
    timeout_seconds: int = 30
    retry_count: int = 3
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "api_url": self.api_url,
            "auth_type": self.auth_type,
            "sync_direction": self.sync_direction.value,
            "sync_interval_minutes": self.sync_interval_minutes,
            "batch_size": self.batch_size,
            "timeout_seconds": self.timeout_seconds,
            "retry_count": self.retry_count
        }


class BaseCRMConnector(ABC):
    """Abstract base class for CRM integrations"""
    
    def __init__(self, config: CRMConfig):
        self.config = config
        self._authenticated = False
        self._last_sync: Optional[datetime] = None
        self._sync_history: List[SyncResult] = []
    
    @abstractmethod
    async def authenticate(self) -> bool:
        """Authenticate with the CRM system"""
        pass
    
    @abstractmethod
    async def test_connection(self) -> bool:
        """Test the connection to the CRM system"""
        pass
    
    @abstractmethod
    async def fetch_contacts(
        self,
        modified_since: Optional[datetime] = None,
        limit: int = 100
    ) -> List[CRMRecord]:
        """Fetch contacts from CRM"""
        pass
    
    @abstractmethod
    async def fetch_accounts(
        self,
        modified_since: Optional[datetime] = None,
        limit: int = 100
    ) -> List[CRMRecord]:
        """Fetch accounts from CRM"""
        pass
    
    @abstractmethod
    async def fetch_cases(
        self,
        modified_since: Optional[datetime] = None,
        limit: int = 100
    ) -> List[CRMRecord]:
        """Fetch support cases from CRM"""
        pass
    
    @abstractmethod
    async def create_case(self, case_data: Dict[str, Any]) -> CRMRecord:
        """Create a new case in CRM"""
        pass
    
    @abstractmethod
    async def update_case(
        self,
        case_id: str,
        case_data: Dict[str, Any]
    ) -> CRMRecord:
        """Update an existing case in CRM"""
        pass
    
    @abstractmethod
    async def push_contact(self, contact_data: Dict[str, Any]) -> CRMRecord:
        """Push a contact to CRM"""
        pass
    
    @abstractmethod
    async def push_account(self, account_data: Dict[str, Any]) -> CRMRecord:
        """Push an account to CRM"""
        pass
    
    async def sync_contacts(
        self,
        modified_since: Optional[datetime] = None
    ) -> SyncResult:
        """Synchronize contacts bidirectionally"""
        result = SyncResult(
            status=SyncStatus.IN_PROGRESS,
            records_processed=0,
            records_succeeded=0,
            records_failed=0
        )
        
        try:
            # Fetch from CRM
            contacts = await self.fetch_contacts(modified_since)
            result.records_processed = len(contacts)
            
            for contact in contacts:
                try:
                    # Process each contact
                    logger.info(f"Processing contact: {contact.id}")
                    result.records_succeeded += 1
                except Exception as e:
                    result.records_failed += 1
                    result.errors.append(f"Contact {contact.id}: {str(e)}")
            
            result.status = SyncStatus.COMPLETED
            result.completed_at = datetime.utcnow()
            self._last_sync = datetime.utcnow()
            
        except Exception as e:
            result.status = SyncStatus.FAILED
            result.errors.append(str(e))
            result.completed_at = datetime.utcnow()
        
        self._sync_history.append(result)
        return result
    
    async def sync_cases(
        self,
        modified_since: Optional[datetime] = None
    ) -> SyncResult:
        """Synchronize support cases bidirectionally"""
        result = SyncResult(
            status=SyncStatus.IN_PROGRESS,
            records_processed=0,
            records_succeeded=0,
            records_failed=0
        )
        
        try:
            cases = await self.fetch_cases(modified_since)
            result.records_processed = len(cases)
            
            for case in cases:
                try:
                    logger.info(f"Processing case: {case.id}")
                    result.records_succeeded += 1
                except Exception as e:
                    result.records_failed += 1
                    result.errors.append(f"Case {case.id}: {str(e)}")
            
            result.status = SyncStatus.COMPLETED
            result.completed_at = datetime.utcnow()
            self._last_sync = datetime.utcnow()
            
        except Exception as e:
            result.status = SyncStatus.FAILED
            result.errors.append(str(e))
            result.completed_at = datetime.utcnow()
        
        self._sync_history.append(result)
        return result
    
    def get_last_sync(self) -> Optional[datetime]:
        """Get the timestamp of the last successful sync"""
        return self._last_sync
    
    def get_sync_history(self, limit: int = 10) -> List[SyncResult]:
        """Get the sync history"""
        return self._sync_history[-limit:]
    
    def is_authenticated(self) -> bool:
        """Check if the connector is authenticated"""
        return self._authenticated
