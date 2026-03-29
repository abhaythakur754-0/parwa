"""
Integration Hub - Central Orchestration
Enterprise Integration Hub - Week 43 Builder 5
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Type
import logging
import asyncio

logger = logging.getLogger(__name__)


class IntegrationType(str, Enum):
    """Types of integrations"""
    CRM = "crm"
    ERP = "erp"
    WAREHOUSE = "warehouse"
    WEBHOOK = "webhook"
    EMAIL = "email"
    MESSAGING = "messaging"


class IntegrationStatus(str, Enum):
    """Integration status"""
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    SYNCING = "syncing"
    PAUSED = "paused"


@dataclass
class IntegrationInstance:
    """Registered integration instance"""
    id: str
    name: str
    type: IntegrationType
    connector: Any  # The actual connector instance
    config: Dict[str, Any]
    status: IntegrationStatus = IntegrationStatus.DISCONNECTED
    last_sync: Optional[datetime] = None
    last_error: Optional[str] = None
    sync_count: int = 0
    error_count: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type.value,
            "status": self.status.value,
            "last_sync": self.last_sync.isoformat() if self.last_sync else None,
            "last_error": self.last_error,
            "sync_count": self.sync_count,
            "error_count": self.error_count,
            "created_at": self.created_at.isoformat()
        }


@dataclass
class SyncJob:
    """Synchronization job definition"""
    id: str
    name: str
    source_integration: str
    target_integration: str
    entity_type: str
    schedule: str  # Cron expression
    enabled: bool = True
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    run_count: int = 0
    error_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "source_integration": self.source_integration,
            "target_integration": self.target_integration,
            "entity_type": self.entity_type,
            "schedule": self.schedule,
            "enabled": self.enabled,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "next_run": self.next_run.isoformat() if self.next_run else None,
            "run_count": self.run_count,
            "error_count": self.error_count
        }


@dataclass
class SyncResult:
    """Result of a synchronization operation"""
    job_id: str
    status: str
    records_processed: int
    records_succeeded: int
    records_failed: int
    errors: List[str] = field(default_factory=list)
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "status": self.status,
            "records_processed": self.records_processed,
            "records_succeeded": self.records_succeeded,
            "records_failed": self.records_failed,
            "errors": self.errors,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None
        }


class IntegrationHub:
    """Central hub for managing all integrations"""
    
    def __init__(self):
        self._integrations: Dict[str, IntegrationInstance] = {}
        self._sync_jobs: Dict[str, SyncJob] = {}
        self._sync_history: List[SyncResult] = []
        self._running = False
    
    def register_integration(
        self,
        name: str,
        integration_type: IntegrationType,
        connector: Any,
        config: Dict[str, Any]
    ) -> IntegrationInstance:
        """
        Register a new integration.
        
        Args:
            name: Human-readable name
            integration_type: Type of integration
            connector: Connector instance
            config: Integration configuration
            
        Returns:
            Registered IntegrationInstance
        """
        import uuid
        integration_id = str(uuid.uuid4())
        
        instance = IntegrationInstance(
            id=integration_id,
            name=name,
            type=integration_type,
            connector=connector,
            config=config
        )
        
        self._integrations[integration_id] = instance
        logger.info(f"Registered integration: {name} ({integration_type.value})")
        
        return instance
    
    def unregister_integration(self, integration_id: str) -> bool:
        """Unregister an integration"""
        if integration_id in self._integrations:
            del self._integrations[integration_id]
            logger.info(f"Unregistered integration: {integration_id}")
            return True
        return False
    
    def get_integration(self, integration_id: str) -> Optional[IntegrationInstance]:
        """Get an integration by ID"""
        return self._integrations.get(integration_id)
    
    def list_integrations(
        self,
        type_filter: Optional[IntegrationType] = None,
        status_filter: Optional[IntegrationStatus] = None
    ) -> List[IntegrationInstance]:
        """List integrations with optional filtering"""
        integrations = list(self._integrations.values())
        
        if type_filter:
            integrations = [i for i in integrations if i.type == type_filter]
        
        if status_filter:
            integrations = [i for i in integrations if i.status == status_filter]
        
        return integrations
    
    async def connect_integration(self, integration_id: str) -> bool:
        """Connect to an integration"""
        instance = self._integrations.get(integration_id)
        if not instance:
            return False
        
        try:
            if hasattr(instance.connector, 'connect'):
                result = await instance.connector.connect()
            elif hasattr(instance.connector, 'authenticate'):
                result = await instance.connector.authenticate()
            else:
                result = True
            
            if result:
                instance.status = IntegrationStatus.CONNECTED
                instance.last_error = None
                logger.info(f"Connected to integration: {instance.name}")
            else:
                instance.status = IntegrationStatus.ERROR
                instance.last_error = "Connection failed"
            
            return result
            
        except Exception as e:
            instance.status = IntegrationStatus.ERROR
            instance.last_error = str(e)
            instance.error_count += 1
            logger.error(f"Integration connection error: {e}")
            return False
    
    async def disconnect_integration(self, integration_id: str) -> bool:
        """Disconnect from an integration"""
        instance = self._integrations.get(integration_id)
        if not instance:
            return False
        
        try:
            if hasattr(instance.connector, 'disconnect'):
                await instance.connector.disconnect()
            
            instance.status = IntegrationStatus.DISCONNECTED
            logger.info(f"Disconnected from integration: {instance.name}")
            return True
            
        except Exception as e:
            instance.last_error = str(e)
            logger.error(f"Integration disconnection error: {e}")
            return False
    
    async def test_integration(self, integration_id: str) -> bool:
        """Test an integration connection"""
        instance = self._integrations.get(integration_id)
        if not instance:
            return False
        
        try:
            if hasattr(instance.connector, 'test_connection'):
                return await instance.connector.test_connection()
            return instance.status == IntegrationStatus.CONNECTED
        except Exception as e:
            logger.error(f"Integration test error: {e}")
            return False
    
    def create_sync_job(
        self,
        name: str,
        source_integration: str,
        target_integration: str,
        entity_type: str,
        schedule: str = "0 * * * *"  # Hourly default
    ) -> SyncJob:
        """Create a synchronization job"""
        import uuid
        job_id = str(uuid.uuid4())
        
        job = SyncJob(
            id=job_id,
            name=name,
            source_integration=source_integration,
            target_integration=target_integration,
            entity_type=entity_type,
            schedule=schedule
        )
        
        self._sync_jobs[job_id] = job
        logger.info(f"Created sync job: {name}")
        
        return job
    
    def get_sync_job(self, job_id: str) -> Optional[SyncJob]:
        """Get a sync job by ID"""
        return self._sync_jobs.get(job_id)
    
    def list_sync_jobs(self, enabled_only: bool = False) -> List[SyncJob]:
        """List sync jobs"""
        jobs = list(self._sync_jobs.values())
        
        if enabled_only:
            jobs = [j for j in jobs if j.enabled]
        
        return jobs
    
    async def run_sync_job(self, job_id: str) -> SyncResult:
        """Execute a synchronization job"""
        import uuid
        
        job = self._sync_jobs.get(job_id)
        if not job:
            return SyncResult(
                job_id=job_id,
                status="failed",
                records_processed=0,
                records_succeeded=0,
                records_failed=0,
                errors=["Job not found"]
            )
        
        result = SyncResult(
            job_id=job_id,
            status="running",
            records_processed=0,
            records_succeeded=0,
            records_failed=0
        )
        
        try:
            source = self._integrations.get(job.source_integration)
            target = self._integrations.get(job.target_integration)
            
            if not source or not target:
                result.status = "failed"
                result.errors.append("Source or target integration not found")
                result.completed_at = datetime.utcnow()
                self._sync_history.append(result)
                return result
            
            # Update job status
            job.last_run = datetime.utcnow()
            job.run_count += 1
            
            # Perform sync based on entity type
            records = await self._fetch_from_source(source, job.entity_type)
            result.records_processed = len(records)
            
            sync_result = await self._push_to_target(target, job.entity_type, records)
            result.records_succeeded = sync_result.get("succeeded", 0)
            result.records_failed = sync_result.get("failed", 0)
            
            result.status = "completed"
            result.completed_at = datetime.utcnow()
            
            source.last_sync = datetime.utcnow()
            source.sync_count += 1
            
        except Exception as e:
            result.status = "failed"
            result.errors.append(str(e))
            result.completed_at = datetime.utcnow()
            
            job.error_count += 1
        
        self._sync_history.append(result)
        return result
    
    async def _fetch_from_source(
        self,
        source: IntegrationInstance,
        entity_type: str
    ) -> List[Dict[str, Any]]:
        """Fetch entities from source integration"""
        try:
            connector = source.connector
            
            if source.type == IntegrationType.CRM:
                if entity_type == "contacts" and hasattr(connector, 'fetch_contacts'):
                    records = await connector.fetch_contacts()
                    return [r.to_dict() for r in records]
                elif entity_type == "cases" and hasattr(connector, 'fetch_cases'):
                    records = await connector.fetch_cases()
                    return [r.to_dict() for r in records]
            
            elif source.type == IntegrationType.ERP:
                if entity_type == "customers" and hasattr(connector, 'fetch_customers'):
                    records = await connector.fetch_customers()
                    return [r.to_dict() for r in records]
                elif entity_type == "orders" and hasattr(connector, 'fetch_orders'):
                    records = await connector.fetch_orders()
                    return [r.to_dict() for r in records]
            
            elif source.type == IntegrationType.WAREHOUSE:
                if hasattr(connector, 'execute_query'):
                    result = await connector.execute_query(f"SELECT * FROM {entity_type}")
                    return result.rows
            
            return []
            
        except Exception as e:
            logger.error(f"Fetch error: {e}")
            return []
    
    async def _push_to_target(
        self,
        target: IntegrationInstance,
        entity_type: str,
        records: List[Dict[str, Any]]
    ) -> Dict[str, int]:
        """Push entities to target integration"""
        succeeded = 0
        failed = 0
        
        try:
            connector = target.connector
            
            for record in records:
                try:
                    if target.type == IntegrationType.CRM:
                        if entity_type == "contacts" and hasattr(connector, 'push_contact'):
                            await connector.push_contact(record)
                            succeeded += 1
                        elif entity_type == "cases" and hasattr(connector, 'create_case'):
                            await connector.create_case(record)
                            succeeded += 1
                        else:
                            failed += 1
                    
                    elif target.type == IntegrationType.ERP:
                        if entity_type == "customers" and hasattr(connector, 'push_customer'):
                            await connector.push_customer(record)
                            succeeded += 1
                        elif entity_type == "orders" and hasattr(connector, 'push_order'):
                            await connector.push_order(record)
                            succeeded += 1
                        else:
                            failed += 1
                    
                    elif target.type == IntegrationType.WAREHOUSE:
                        if hasattr(connector, 'insert_data'):
                            count = await connector.insert_data(entity_type, [record])
                            succeeded += count
                        else:
                            failed += 1
                    
                    else:
                        failed += 1
                        
                except Exception as e:
                    logger.error(f"Push record error: {e}")
                    failed += 1
            
        except Exception as e:
            logger.error(f"Push error: {e}")
        
        return {"succeeded": succeeded, "failed": failed}
    
    def get_sync_history(
        self,
        job_id: Optional[str] = None,
        limit: int = 100
    ) -> List[SyncResult]:
        """Get synchronization history"""
        history = self._sync_history
        
        if job_id:
            history = [h for h in history if h.job_id == job_id]
        
        return history[-limit:]
    
    async def connect_all(self) -> Dict[str, bool]:
        """Connect to all registered integrations"""
        results = {}
        
        for integration_id in self._integrations:
            results[integration_id] = await self.connect_integration(integration_id)
        
        return results
    
    async def sync_all(self) -> Dict[str, SyncResult]:
        """Run all enabled sync jobs"""
        results = {}
        
        for job_id, job in self._sync_jobs.items():
            if job.enabled:
                results[job_id] = await self.run_sync_job(job_id)
        
        return results
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get overall integration health status"""
        total = len(self._integrations)
        connected = sum(1 for i in self._integrations.values() if i.status == IntegrationStatus.CONNECTED)
        error = sum(1 for i in self._integrations.values() if i.status == IntegrationStatus.ERROR)
        
        jobs_total = len(self._sync_jobs)
        jobs_enabled = sum(1 for j in self._sync_jobs.values() if j.enabled)
        
        return {
            "integrations": {
                "total": total,
                "connected": connected,
                "error": error,
                "health_percentage": (connected / total * 100) if total > 0 else 100
            },
            "sync_jobs": {
                "total": jobs_total,
                "enabled": jobs_enabled
            },
            "recent_syncs": len([h for h in self._sync_history if h.status == "completed"])
        }
