"""
Base Data Warehouse Connector
Enterprise Integration Hub - Week 43 Builder 3
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Iterator
import logging

logger = logging.getLogger(__name__)


class WarehouseType(str, Enum):
    """Supported data warehouse types"""
    SNOWFLAKE = "snowflake"
    BIGQUERY = "bigquery"
    REDSHIFT = "redshift"
    DATABRICKS = "databricks"


class ExportFormat(str, Enum):
    """Data export formats"""
    CSV = "csv"
    JSON = "json"
    PARQUET = "parquet"
    AVRO = "avro"


@dataclass
class WarehouseConfig:
    """Configuration for data warehouse connection"""
    name: str
    warehouse_type: WarehouseType
    connection_params: Dict[str, Any]
    default_schema: str = "public"
    default_database: Optional[str] = None
    query_timeout: int = 300
    max_rows_per_fetch: int = 10000
    enable_cache: bool = True
    cache_ttl_seconds: int = 3600
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "warehouse_type": self.warehouse_type.value,
            "default_schema": self.default_schema,
            "default_database": self.default_database,
            "query_timeout": self.query_timeout,
            "max_rows_per_fetch": self.max_rows_per_fetch,
            "enable_cache": self.enable_cache,
            "cache_ttl_seconds": self.cache_ttl_seconds
        }


@dataclass
class QueryResult:
    """Result of a warehouse query"""
    query: str
    columns: List[str]
    rows: List[Dict[str, Any]]
    row_count: int
    execution_time_ms: float
    warehouse: str
    schema: Optional[str] = None
    error: Optional[str] = None
    executed_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "columns": self.columns,
            "row_count": self.row_count,
            "execution_time_ms": self.execution_time_ms,
            "warehouse": self.warehouse,
            "schema": self.schema,
            "error": self.error,
            "executed_at": self.executed_at.isoformat()
        }
    
    def to_dataframe_dict(self) -> List[Dict[str, Any]]:
        """Return rows as list of dictionaries"""
        return self.rows


@dataclass
class ExportJob:
    """Data warehouse export job"""
    job_id: str
    table_name: str
    query: str
    format: ExportFormat
    destination: str
    status: str = "pending"
    rows_exported: int = 0
    bytes_exported: int = 0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "table_name": self.table_name,
            "query": self.query,
            "format": self.format.value,
            "destination": self.destination,
            "status": self.status,
            "rows_exported": self.rows_exported,
            "bytes_exported": self.bytes_exported,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error": self.error
        }


class BaseWarehouseConnector(ABC):
    """Abstract base class for data warehouse connectors"""
    
    def __init__(self, config: WarehouseConfig):
        self.config = config
        self._connected = False
        self._query_history: List[QueryResult] = []
    
    @abstractmethod
    async def connect(self) -> bool:
        """Establish connection to the data warehouse"""
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from the data warehouse"""
        pass
    
    @abstractmethod
    async def test_connection(self) -> bool:
        """Test the connection to the warehouse"""
        pass
    
    @abstractmethod
    async def execute_query(
        self,
        query: str,
        params: Optional[Dict[str, Any]] = None
    ) -> QueryResult:
        """Execute a SQL query"""
        pass
    
    @abstractmethod
    async def execute_query_iter(
        self,
        query: str,
        params: Optional[Dict[str, Any]] = None,
        batch_size: int = 1000
    ) -> Iterator[List[Dict[str, Any]]]:
        """Execute a query and iterate over results"""
        pass
    
    @abstractmethod
    async def get_tables(
        self,
        schema: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get list of tables in the warehouse"""
        pass
    
    @abstractmethod
    async def get_table_schema(
        self,
        table_name: str,
        schema: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get schema of a specific table"""
        pass
    
    @abstractmethod
    async def create_table(
        self,
        table_name: str,
        columns: List[Dict[str, str]],
        schema: Optional[str] = None
    ) -> bool:
        """Create a new table"""
        pass
    
    @abstractmethod
    async def insert_data(
        self,
        table_name: str,
        data: List[Dict[str, Any]],
        schema: Optional[str] = None
    ) -> int:
        """Insert data into a table"""
        pass
    
    @abstractmethod
    async def export_data(
        self,
        query: str,
        destination: str,
        format: ExportFormat = ExportFormat.CSV
    ) -> ExportJob:
        """Export query results to a file"""
        pass
    
    def is_connected(self) -> bool:
        """Check if connected to warehouse"""
        return self._connected
    
    def get_query_history(self, limit: int = 10) -> List[QueryResult]:
        """Get recent query history"""
        return self._query_history[-limit:]
    
    def _add_to_history(self, result: QueryResult) -> None:
        """Add query result to history"""
        self._query_history.append(result)
        # Keep only last 100 queries
        if len(self._query_history) > 100:
            self._query_history = self._query_history[-100:]
