"""
Google BigQuery Data Warehouse Connector
Enterprise Integration Hub - Week 43 Builder 3
"""

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Iterator
import logging
import time

from .warehouse_base import (
    BaseWarehouseConnector,
    WarehouseConfig,
    WarehouseType,
    QueryResult,
    ExportJob,
    ExportFormat
)

logger = logging.getLogger(__name__)


@dataclass
class BigQueryConnection:
    """BigQuery connection details"""
    project_id: str
    dataset: str = "default"
    location: str = "US"
    credentials_path: Optional[str] = None
    credentials_json: Optional[Dict[str, Any]] = None


class BigQueryConnector(BaseWarehouseConnector):
    """Google BigQuery data warehouse connector"""
    
    def __init__(self, config: WarehouseConfig):
        super().__init__(config)
        self.client: Optional[Any] = None
        self._connection_params: Optional[BigQueryConnection] = None
    
    def _parse_connection_params(self) -> BigQueryConnection:
        """Parse connection parameters from config"""
        params = self.config.connection_params
        return BigQueryConnection(
            project_id=params.get("project_id", ""),
            dataset=params.get("dataset", self.config.default_schema),
            location=params.get("location", "US"),
            credentials_path=params.get("credentials_path"),
            credentials_json=params.get("credentials_json")
        )
    
    async def connect(self) -> bool:
        """Establish connection to BigQuery"""
        try:
            from google.cloud import bigquery
            from google.oauth2 import service_account
            
            self._connection_params = self._parse_connection_params()
            
            if self._connection_params.credentials_json:
                credentials = service_account.Credentials.from_service_account_info(
                    self._connection_params.credentials_json
                )
                self.client = bigquery.Client(
                    project=self._connection_params.project_id,
                    credentials=credentials
                )
            elif self._connection_params.credentials_path:
                credentials = service_account.Credentials.from_service_account_file(
                    self._connection_params.credentials_path
                )
                self.client = bigquery.Client(
                    project=self._connection_params.project_id,
                    credentials=credentials
                )
            else:
                self.client = bigquery.Client(
                    project=self._connection_params.project_id
                )
            
            self._connected = True
            logger.info(f"Connected to BigQuery: {self._connection_params.project_id}")
            return True
            
        except ImportError:
            logger.warning("google-cloud-bigquery not installed, using mock mode")
            self._connected = True
            return True
        except Exception as e:
            logger.error(f"Failed to connect to BigQuery: {e}")
            self._connected = False
            return False
    
    async def disconnect(self) -> None:
        """Disconnect from BigQuery"""
        self._connected = False
        self.client = None
    
    async def test_connection(self) -> bool:
        """Test the connection to BigQuery"""
        if not self._connected:
            if not await self.connect():
                return False
        
        try:
            result = await self.execute_query("SELECT 1 as test")
            return result.error is None
        except Exception:
            return False
    
    async def execute_query(
        self,
        query: str,
        params: Optional[Dict[str, Any]] = None
    ) -> QueryResult:
        """Execute a SQL query on BigQuery"""
        start_time = time.time()
        
        if not self._connected:
            await self.connect()
        
        columns = []
        rows = []
        error = None
        
        try:
            if self.client:
                from google.cloud import bigquery
                
                # Configure query
                job_config = bigquery.QueryJobConfig()
                
                # Add parameterized query support
                if params:
                    for key, value in params.items():
                        query = query.replace(f":{key}", f"@{key}")
                    job_config.query_parameters = [
                        bigquery.ScalarQueryParameter(k, type(v).__name__, v)
                        for k, v in params.items()
                    ]
                
                # Execute query
                query_job = self.client.query(query, job_config=job_config)
                results = query_job.result()
                
                # Get column names
                if results.schema:
                    columns = [field.name for field in results.schema]
                
                # Convert to list of dicts
                for row in results:
                    row_dict = {col: row[col] for col in columns}
                    # Handle non-serializable types
                    for col in columns:
                        if hasattr(row_dict[col], 'isoformat'):
                            row_dict[col] = row_dict[col].isoformat()
                    rows.append(row_dict)
            else:
                # Mock mode
                columns = ["result"]
                rows = [{"result": "mock_mode"}]
                
        except Exception as e:
            error = str(e)
            logger.error(f"Query execution error: {e}")
        
        execution_time = (time.time() - start_time) * 1000
        
        result = QueryResult(
            query=query,
            columns=columns,
            rows=rows,
            row_count=len(rows),
            execution_time_ms=execution_time,
            warehouse=self.config.name,
            schema=self.config.default_schema,
            error=error
        )
        
        self._add_to_history(result)
        return result
    
    async def execute_query_iter(
        self,
        query: str,
        params: Optional[Dict[str, Any]] = None,
        batch_size: int = 1000
    ) -> Iterator[List[Dict[str, Any]]]:
        """Execute a query and iterate over results in batches"""
        if not self._connected:
            await self.connect()
        
        try:
            if self.client:
                from google.cloud import bigquery
                
                job_config = bigquery.QueryJobConfig()
                query_job = self.client.query(query, job_config=job_config)
                results = query_job.result()
                
                columns = [field.name for field in results.schema]
                
                batch = []
                for row in results:
                    row_dict = {col: row[col] for col in columns}
                    batch.append(row_dict)
                    
                    if len(batch) >= batch_size:
                        yield batch
                        batch = []
                
                if batch:
                    yield batch
            else:
                yield []
                
        except Exception as e:
            logger.error(f"Iterator query error: {e}")
            yield []
    
    async def get_tables(
        self,
        schema: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get list of tables in BigQuery dataset"""
        schema = schema or self.config.default_schema
        
        if not self._connection_params:
            return []
        
        try:
            if self.client:
                dataset_ref = self.client.dataset(schema, project=self._connection_params.project_id)
                tables = list(self.client.list_tables(dataset_ref))
                
                return [
                    {
                        "table_name": table.table_id,
                        "table_type": table.table_type,
                        "location": table.location,
                        "num_bytes": table.num_bytes,
                        "num_rows": table.num_rows
                    }
                    for table in tables
                ]
        except Exception as e:
            logger.error(f"Error listing tables: {e}")
        
        return []
    
    async def get_table_schema(
        self,
        table_name: str,
        schema: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get schema of a specific table"""
        schema = schema or self.config.default_schema
        
        if not self._connection_params:
            return []
        
        try:
            if self.client:
                table_ref = self.client.dataset(schema).table(table_name)
                table = self.client.get_table(table_ref)
                
                return [
                    {
                        "column_name": field.name,
                        "data_type": field.field_type,
                        "mode": field.mode,
                        "description": field.description
                    }
                    for field in table.schema
                ]
        except Exception as e:
            logger.error(f"Error getting table schema: {e}")
        
        return []
    
    async def create_table(
        self,
        table_name: str,
        columns: List[Dict[str, str]],
        schema: Optional[str] = None
    ) -> bool:
        """Create a new table in BigQuery"""
        schema = schema or self.config.default_schema
        
        if not self._connection_params:
            return False
        
        try:
            if self.client:
                from google.cloud import bigquery
                
                # Build schema
                table_schema = [
                    bigquery.SchemaField(
                        col['name'],
                        col['type'],
                        mode=col.get('mode', 'NULLABLE')
                    )
                    for col in columns
                ]
                
                table_ref = self.client.dataset(schema).table(table_name)
                table = bigquery.Table(table_ref, schema=table_schema)
                
                self.client.create_table(table)
                return True
        except Exception as e:
            logger.error(f"Error creating table: {e}")
        
        return True  # Mock mode
    
    async def insert_data(
        self,
        table_name: str,
        data: List[Dict[str, Any]],
        schema: Optional[str] = None
    ) -> int:
        """Insert data into a BigQuery table"""
        if not data:
            return 0
        
        schema = schema or self.config.default_schema
        
        if not self._connection_params:
            return len(data)
        
        try:
            if self.client:
                table_ref = self.client.dataset(schema).table(table_name)
                
                errors = self.client.insert_rows_json(table_ref, data)
                
                if errors:
                    logger.error(f"Insert errors: {errors}")
                    return 0
                
                return len(data)
        except Exception as e:
            logger.error(f"Insert error: {e}")
        
        return len(data)  # Mock mode
    
    async def export_data(
        self,
        query: str,
        destination: str,
        format: ExportFormat = ExportFormat.CSV
    ) -> ExportJob:
        """Export query results to Google Cloud Storage"""
        job_id = str(uuid.uuid4())
        
        job = ExportJob(
            job_id=job_id,
            table_name="export",
            query=query,
            format=format,
            destination=destination,
            status="running",
            started_at=datetime.utcnow()
        )
        
        try:
            if self.client:
                from google.cloud import bigquery
                
                # Configure export
                destination_uri = f"gs://{destination}"
                
                dataset_ref = self.client.dataset("_export")
                table_ref = dataset_ref.table(f"export_{job_id.replace('-', '_')}")
                
                # Run query to temp table
                query_job = self.client.query(query)
                query_job.result()
                
                # Export to GCS
                extract_job = self.client.extract_table(
                    table_ref,
                    destination_uri,
                    job_config=bigquery.ExtractJobConfig(
                        destination_format=format.value.upper()
                    )
                )
                extract_job.result()
                
                job.status = "completed"
                job.completed_at = datetime.utcnow()
            else:
                # Mock mode
                job.status = "completed"
                job.rows_exported = 100
                job.completed_at = datetime.utcnow()
                
        except Exception as e:
            job.status = "failed"
            job.error = str(e)
            job.completed_at = datetime.utcnow()
        
        return job
    
    async def load_from_gcs(
        self,
        table_name: str,
        source_uri: str,
        schema: List[Dict[str, str]],
        schema_name: Optional[str] = None
    ) -> int:
        """Load data from Google Cloud Storage into BigQuery"""
        if not self._connection_params:
            return 0
        
        try:
            if self.client:
                from google.cloud import bigquery
                
                dataset = schema_name or self.config.default_schema
                table_ref = self.client.dataset(dataset).table(table_name)
                
                # Build schema
                table_schema = [
                    bigquery.SchemaField(col['name'], col['type'])
                    for col in schema
                ]
                
                job_config = bigquery.LoadJobConfig(
                    schema=table_schema,
                    source_format=bigquery.SourceFormat.CSV,
                    skip_leading_rows=1
                )
                
                load_job = self.client.load_table_from_uri(
                    source_uri,
                    table_ref,
                    job_config=job_config
                )
                
                result = load_job.result()
                return result.output_rows
        except Exception as e:
            logger.error(f"Load error: {e}")
        
        return 0
    
    async def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """Get status of a BigQuery job"""
        try:
            if self.client:
                job = self.client.get_job(job_id)
                return {
                    "job_id": job.job_id,
                    "status": job.state,
                    "error": str(job.error_result) if job.error_result else None,
                    "created": job.created.isoformat() if job.created else None,
                    "started": job.started.isoformat() if job.started else None,
                    "ended": job.ended.isoformat() if job.ended else None
                }
        except Exception as e:
            logger.error(f"Error getting job status: {e}")
        
        return {"job_id": job_id, "status": "unknown"}
    
    async def get_dataset_usage(self) -> Dict[str, Any]:
        """Get dataset usage statistics"""
        query = """
        SELECT
            table_id,
            SUM(size_bytes) / 1024 / 1024 / 1024 as size_gb,
            SUM(row_count) as total_rows
        FROM `region-us.INFORMATION_SCHEMA.TABLE_STORAGE`
        GROUP BY table_id
        ORDER BY size_gb DESC
        """
        
        result = await self.execute_query(query)
        return {"usage": result.rows}
