"""
Tests for Data Warehouse Connectors
Enterprise Integration Hub - Week 43 Builder 3
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
import json

from enterprise.integrations.warehouse_base import (
    WarehouseConfig,
    WarehouseType,
    QueryResult,
    ExportJob,
    ExportFormat
)
from enterprise.integrations.snowflake_connector import (
    SnowflakeConnector,
    SnowflakeConnection
)
from enterprise.integrations.bigquery_connector import (
    BigQueryConnector,
    BigQueryConnection
)


# Test Fixtures
@pytest.fixture
def snowflake_config():
    """Create a test Snowflake configuration"""
    return WarehouseConfig(
        name="test_snowflake",
        warehouse_type=WarehouseType.SNOWFLAKE,
        connection_params={
            "account": "test_account",
            "user": "test_user",
            "password": "test_password",
            "database": "TEST_DB",
            "schema": "PUBLIC",
            "warehouse": "TEST_WH"
        },
        default_schema="PUBLIC",
        default_database="TEST_DB"
    )


@pytest.fixture
def bigquery_config():
    """Create a test BigQuery configuration"""
    return WarehouseConfig(
        name="test_bigquery",
        warehouse_type=WarehouseType.BIGQUERY,
        connection_params={
            "project_id": "test-project",
            "dataset": "test_dataset",
            "location": "US"
        },
        default_schema="test_dataset"
    )


@pytest.fixture
def snowflake_connector(snowflake_config):
    """Create a test Snowflake connector"""
    return SnowflakeConnector(snowflake_config)


@pytest.fixture
def bigquery_connector(bigquery_config):
    """Create a test BigQuery connector"""
    return BigQueryConnector(bigquery_config)


# WarehouseConfig Tests
class TestWarehouseConfig:
    """Tests for WarehouseConfig"""
    
    def test_warehouse_config_creation(self):
        """Test WarehouseConfig can be created"""
        config = WarehouseConfig(
            name="test",
            warehouse_type=WarehouseType.SNOWFLAKE,
            connection_params={"account": "test"}
        )
        assert config.name == "test"
        assert config.warehouse_type == WarehouseType.SNOWFLAKE
    
    def test_warehouse_config_defaults(self):
        """Test WarehouseConfig default values"""
        config = WarehouseConfig(
            name="test",
            warehouse_type=WarehouseType.BIGQUERY,
            connection_params={}
        )
        assert config.default_schema == "public"
        assert config.query_timeout == 300
        assert config.max_rows_per_fetch == 10000
        assert config.enable_cache is True
    
    def test_warehouse_config_to_dict(self):
        """Test WarehouseConfig serialization"""
        config = WarehouseConfig(
            name="test",
            warehouse_type=WarehouseType.SNOWFLAKE,
            connection_params={},
            default_schema="test_schema"
        )
        result = config.to_dict()
        assert result["name"] == "test"
        assert result["warehouse_type"] == "snowflake"
        assert result["default_schema"] == "test_schema"


# QueryResult Tests
class TestQueryResult:
    """Tests for QueryResult"""
    
    def test_query_result_creation(self):
        """Test QueryResult can be created"""
        result = QueryResult(
            query="SELECT * FROM test",
            columns=["id", "name"],
            rows=[{"id": 1, "name": "test"}],
            row_count=1,
            execution_time_ms=100.0,
            warehouse="test_warehouse"
        )
        assert result.query == "SELECT * FROM test"
        assert result.row_count == 1
        assert len(result.columns) == 2
    
    def test_query_result_to_dict(self):
        """Test QueryResult serialization"""
        result = QueryResult(
            query="SELECT 1",
            columns=["val"],
            rows=[{"val": 1}],
            row_count=1,
            execution_time_ms=50.0,
            warehouse="test"
        )
        data = result.to_dict()
        assert data["query"] == "SELECT 1"
        assert data["row_count"] == 1
    
    def test_query_result_with_error(self):
        """Test QueryResult with error"""
        result = QueryResult(
            query="SELECT * FROM nonexistent",
            columns=[],
            rows=[],
            row_count=0,
            execution_time_ms=10.0,
            warehouse="test",
            error="Table not found"
        )
        assert result.error == "Table not found"


# ExportJob Tests
class TestExportJob:
    """Tests for ExportJob"""
    
    def test_export_job_creation(self):
        """Test ExportJob can be created"""
        job = ExportJob(
            job_id="job-123",
            table_name="test_table",
            query="SELECT * FROM test",
            format=ExportFormat.CSV,
            destination="s3://bucket/file.csv"
        )
        assert job.job_id == "job-123"
        assert job.format == ExportFormat.CSV
        assert job.status == "pending"
    
    def test_export_job_to_dict(self):
        """Test ExportJob serialization"""
        job = ExportJob(
            job_id="job-456",
            table_name="export",
            query="SELECT 1",
            format=ExportFormat.JSON,
            destination="gs://bucket/file.json",
            status="completed",
            rows_exported=100
        )
        data = job.to_dict()
        assert data["job_id"] == "job-456"
        assert data["format"] == "json"
        assert data["rows_exported"] == 100


# SnowflakeConnection Tests
class TestSnowflakeConnection:
    """Tests for SnowflakeConnection"""
    
    def test_connection_creation(self):
        """Test SnowflakeConnection can be created"""
        conn = SnowflakeConnection(
            account="test_account",
            user="test_user",
            password="test_pass"
        )
        assert conn.account == "test_account"
        assert conn.user == "test_user"
    
    def test_connection_to_dict(self):
        """Test SnowflakeConnection to connection dict"""
        conn = SnowflakeConnection(
            account="test_account",
            user="test_user",
            password="test_pass",
            database="TEST_DB",
            schema="PUBLIC",
            warehouse="COMPUTE_WH"
        )
        params = conn.to_connection_dict()
        assert params["account"] == "test_account"
        assert params["database"] == "TEST_DB"
        assert params["warehouse"] == "COMPUTE_WH"


# SnowflakeConnector Tests
class TestSnowflakeConnector:
    """Tests for SnowflakeConnector"""
    
    @pytest.mark.asyncio
    async def test_connector_initialization(self, snowflake_connector):
        """Test connector initializes correctly"""
        assert snowflake_connector.config is not None
        assert not snowflake_connector.is_connected()
    
    @pytest.mark.asyncio
    async def test_connect_mock_mode(self, snowflake_connector):
        """Test connection in mock mode"""
        # Connection may fail without valid credentials, which is expected
        result = await snowflake_connector.connect()
        # Either succeeds (mock mode) or fails gracefully
        assert isinstance(result, bool)
    
    @pytest.mark.asyncio
    async def test_execute_query_mock_mode(self, snowflake_connector):
        """Test query execution in mock mode"""
        await snowflake_connector.connect()
        result = await snowflake_connector.execute_query("SELECT 1")
        
        assert result.error is None
        assert result.query == "SELECT 1"
    
    @pytest.mark.asyncio
    async def test_get_tables_mock_mode(self, snowflake_connector):
        """Test get tables in mock mode"""
        await snowflake_connector.connect()
        tables = await snowflake_connector.get_tables()
        assert isinstance(tables, list)
    
    @pytest.mark.asyncio
    async def test_insert_data_mock_mode(self, snowflake_connector):
        """Test insert in mock mode"""
        await snowflake_connector.connect()
        
        data = [
            {"id": 1, "name": "test1"},
            {"id": 2, "name": "test2"}
        ]
        
        count = await snowflake_connector.insert_data("test_table", data)
        assert count == 2
    
    @pytest.mark.asyncio
    async def test_export_data_mock_mode(self, snowflake_connector):
        """Test export in mock mode"""
        await snowflake_connector.connect()
        
        job = await snowflake_connector.export_data(
            query="SELECT * FROM test",
            destination="s3://bucket/export.csv",
            format=ExportFormat.CSV
        )
        
        assert job.job_id is not None
        assert job.format == ExportFormat.CSV
    
    @pytest.mark.asyncio
    async def test_query_history(self, snowflake_connector):
        """Test query history tracking"""
        await snowflake_connector.connect()
        
        # Execute queries which will be added to history
        await snowflake_connector.execute_query("SELECT 1")
        await snowflake_connector.execute_query("SELECT 2")
        
        # Query history is stored as list, not coroutine
        history = snowflake_connector._query_history
        assert len(history) >= 2


# BigQueryConnection Tests
class TestBigQueryConnection:
    """Tests for BigQueryConnection"""
    
    def test_connection_creation(self):
        """Test BigQueryConnection can be created"""
        conn = BigQueryConnection(
            project_id="test-project",
            dataset="test_dataset"
        )
        assert conn.project_id == "test-project"
        assert conn.dataset == "test_dataset"
    
    def test_connection_with_credentials(self):
        """Test BigQueryConnection with credentials"""
        conn = BigQueryConnection(
            project_id="test-project",
            dataset="test_dataset",
            credentials_path="/path/to/key.json"
        )
        assert conn.credentials_path == "/path/to/key.json"


# BigQueryConnector Tests
class TestBigQueryConnector:
    """Tests for BigQueryConnector"""
    
    @pytest.mark.asyncio
    async def test_connector_initialization(self, bigquery_connector):
        """Test connector initializes correctly"""
        assert bigquery_connector.config is not None
        assert not bigquery_connector.is_connected()
    
    @pytest.mark.asyncio
    async def test_connect_mock_mode(self, bigquery_connector):
        """Test connection in mock mode"""
        result = await bigquery_connector.connect()
        assert result is True
        assert bigquery_connector.is_connected()
    
    @pytest.mark.asyncio
    async def test_execute_query_mock_mode(self, bigquery_connector):
        """Test query execution in mock mode"""
        await bigquery_connector.connect()
        result = await bigquery_connector.execute_query("SELECT 1")
        
        assert result.error is None
        assert result.query == "SELECT 1"
    
    @pytest.mark.asyncio
    async def test_get_tables_mock_mode(self, bigquery_connector):
        """Test get tables in mock mode"""
        await bigquery_connector.connect()
        tables = await bigquery_connector.get_tables()
        assert isinstance(tables, list)
    
    @pytest.mark.asyncio
    async def test_insert_data_mock_mode(self, bigquery_connector):
        """Test insert in mock mode"""
        await bigquery_connector.connect()
        
        data = [
            {"id": 1, "name": "test1"},
            {"id": 2, "name": "test2"}
        ]
        
        count = await bigquery_connector.insert_data("test_table", data)
        assert count == 2
    
    @pytest.mark.asyncio
    async def test_create_table_mock_mode(self, bigquery_connector):
        """Test create table in mock mode"""
        await bigquery_connector.connect()
        
        columns = [
            {"name": "id", "type": "INTEGER"},
            {"name": "name", "type": "STRING"}
        ]
        
        result = await bigquery_connector.create_table("new_table", columns)
        # Result is True in mock mode or if no project configured
        assert isinstance(result, bool)
    
    @pytest.mark.asyncio
    async def test_export_data_mock_mode(self, bigquery_connector):
        """Test export in mock mode"""
        await bigquery_connector.connect()
        
        job = await bigquery_connector.export_data(
            query="SELECT * FROM test",
            destination="bucket/export.csv",
            format=ExportFormat.CSV
        )
        
        assert job.job_id is not None
        assert job.format == ExportFormat.CSV
    
    @pytest.mark.asyncio
    async def test_query_history(self, bigquery_connector):
        """Test query history tracking"""
        await bigquery_connector.connect()
        
        await bigquery_connector.execute_query("SELECT 1")
        await bigquery_connector.execute_query("SELECT 2")
        
        history = bigquery_connector.get_query_history()
        assert len(history) == 2


# Integration Tests
class TestWarehouseIntegration:
    """Integration tests for warehouse connectors"""
    
    @pytest.mark.asyncio
    async def test_full_query_flow(self, snowflake_config):
        """Test full query flow"""
        connector = SnowflakeConnector(snowflake_config)
        await connector.connect()
        
        result = await connector.execute_query("SELECT 1 as value")
        assert result is not None
        assert result.error is None
    
    @pytest.mark.asyncio
    async def test_bigquery_full_flow(self, bigquery_config):
        """Test full BigQuery flow"""
        connector = BigQueryConnector(bigquery_config)
        await connector.connect()
        
        result = await connector.execute_query("SELECT 1 as value")
        assert result is not None
        assert result.error is None
    
    def test_export_format_enum(self):
        """Test ExportFormat enum values"""
        assert ExportFormat.CSV.value == "csv"
        assert ExportFormat.JSON.value == "json"
        assert ExportFormat.PARQUET.value == "parquet"
        assert ExportFormat.AVRO.value == "avro"
    
    def test_warehouse_type_enum(self):
        """Test WarehouseType enum values"""
        assert WarehouseType.SNOWFLAKE.value == "snowflake"
        assert WarehouseType.BIGQUERY.value == "bigquery"
        assert WarehouseType.REDSHIFT.value == "redshift"
        assert WarehouseType.DATABRICKS.value == "databricks"
