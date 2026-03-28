"""
Base ERP Integration Class
Enterprise Integration Hub - Week 43 Builder 2
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class ERPEntityType(str, Enum):
    """Types of ERP entities"""
    CUSTOMER = "customer"
    ORDER = "order"
    INVOICE = "invoice"
    PRODUCT = "product"
    SUPPLIER = "supplier"
    EMPLOYEE = "employee"


class SyncMode(str, Enum):
    """ERP synchronization modes"""
    FULL = "full"
    INCREMENTAL = "incremental"
    DELTA = "delta"


@dataclass
class ERPConfig:
    """Configuration for ERP connection"""
    name: str
    system_type: str  # SAP, Oracle, Microsoft Dynamics, etc.
    api_url: str
    auth_type: str
    credentials: Dict[str, Any]
    company_code: Optional[str] = None
    sync_mode: SyncMode = SyncMode.INCREMENTAL
    batch_size: int = 100
    timeout_seconds: int = 60
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "system_type": self.system_type,
            "api_url": self.api_url,
            "auth_type": self.auth_type,
            "company_code": self.company_code,
            "sync_mode": self.sync_mode.value,
            "batch_size": self.batch_size,
            "timeout_seconds": self.timeout_seconds
        }


@dataclass
class ERPEntity:
    """Base ERP entity representation"""
    id: str
    entity_type: ERPEntityType
    data: Dict[str, Any]
    last_modified: datetime
    version: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "entity_type": self.entity_type.value,
            "data": self.data,
            "last_modified": self.last_modified.isoformat(),
            "version": self.version,
            "created_at": self.created_at.isoformat()
        }


@dataclass
class ERPSyncResult:
    """Result of an ERP sync operation"""
    entity_type: ERPEntityType
    mode: SyncMode
    status: str
    records_processed: int
    records_succeeded: int
    records_failed: int
    errors: List[str] = field(default_factory=list)
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity_type": self.entity_type.value,
            "mode": self.mode.value,
            "status": self.status,
            "records_processed": self.records_processed,
            "records_succeeded": self.records_succeeded,
            "records_failed": self.records_failed,
            "errors": self.errors,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None
        }


class BaseERPConnector(ABC):
    """Abstract base class for ERP integrations"""
    
    def __init__(self, config: ERPConfig):
        self.config = config
        self._authenticated = False
        self._last_sync: Dict[ERPEntityType, datetime] = {}
        self._sync_history: List[ERPSyncResult] = []
    
    @abstractmethod
    async def authenticate(self) -> bool:
        """Authenticate with the ERP system"""
        pass
    
    @abstractmethod
    async def test_connection(self) -> bool:
        """Test the connection to the ERP system"""
        pass
    
    @abstractmethod
    async def fetch_customers(
        self,
        modified_since: Optional[datetime] = None,
        limit: int = 100
    ) -> List[ERPEntity]:
        """Fetch customers from ERP"""
        pass
    
    @abstractmethod
    async def fetch_orders(
        self,
        modified_since: Optional[datetime] = None,
        limit: int = 100
    ) -> List[ERPEntity]:
        """Fetch orders from ERP"""
        pass
    
    @abstractmethod
    async def fetch_invoices(
        self,
        modified_since: Optional[datetime] = None,
        limit: int = 100
    ) -> List[ERPEntity]:
        """Fetch invoices from ERP"""
        pass
    
    @abstractmethod
    async def push_customer(self, customer_data: Dict[str, Any]) -> ERPEntity:
        """Push a customer to ERP"""
        pass
    
    @abstractmethod
    async def push_order(self, order_data: Dict[str, Any]) -> ERPEntity:
        """Push an order to ERP"""
        pass
    
    async def sync_customers(
        self,
        mode: SyncMode = SyncMode.INCREMENTAL
    ) -> ERPSyncResult:
        """Synchronize customers with ERP"""
        result = ERPSyncResult(
            entity_type=ERPEntityType.CUSTOMER,
            mode=mode,
            status="in_progress",
            records_processed=0,
            records_succeeded=0,
            records_failed=0
        )
        
        try:
            modified_since = None
            if mode == SyncMode.INCREMENTAL:
                modified_since = self._last_sync.get(ERPEntityType.CUSTOMER)
            
            customers = await self.fetch_customers(modified_since)
            result.records_processed = len(customers)
            
            for customer in customers:
                try:
                    logger.info(f"Processing customer: {customer.id}")
                    result.records_succeeded += 1
                except Exception as e:
                    result.records_failed += 1
                    result.errors.append(f"Customer {customer.id}: {str(e)}")
            
            result.status = "completed"
            result.completed_at = datetime.utcnow()
            self._last_sync[ERPEntityType.CUSTOMER] = datetime.utcnow()
            
        except Exception as e:
            result.status = "failed"
            result.errors.append(str(e))
            result.completed_at = datetime.utcnow()
        
        self._sync_history.append(result)
        return result
    
    async def sync_orders(
        self,
        mode: SyncMode = SyncMode.INCREMENTAL
    ) -> ERPSyncResult:
        """Synchronize orders with ERP"""
        result = ERPSyncResult(
            entity_type=ERPEntityType.ORDER,
            mode=mode,
            status="in_progress",
            records_processed=0,
            records_succeeded=0,
            records_failed=0
        )
        
        try:
            modified_since = None
            if mode == SyncMode.INCREMENTAL:
                modified_since = self._last_sync.get(ERPEntityType.ORDER)
            
            orders = await self.fetch_orders(modified_since)
            result.records_processed = len(orders)
            
            for order in orders:
                try:
                    logger.info(f"Processing order: {order.id}")
                    result.records_succeeded += 1
                except Exception as e:
                    result.records_failed += 1
                    result.errors.append(f"Order {order.id}: {str(e)}")
            
            result.status = "completed"
            result.completed_at = datetime.utcnow()
            self._last_sync[ERPEntityType.ORDER] = datetime.utcnow()
            
        except Exception as e:
            result.status = "failed"
            result.errors.append(str(e))
            result.completed_at = datetime.utcnow()
        
        self._sync_history.append(result)
        return result
    
    def get_last_sync(self, entity_type: ERPEntityType) -> Optional[datetime]:
        """Get the timestamp of the last successful sync for an entity type"""
        return self._last_sync.get(entity_type)
    
    def get_sync_history(self, limit: int = 10) -> List[ERPSyncResult]:
        """Get the sync history"""
        return self._sync_history[-limit:]
    
    def is_authenticated(self) -> bool:
        """Check if the connector is authenticated"""
        return self._authenticated
