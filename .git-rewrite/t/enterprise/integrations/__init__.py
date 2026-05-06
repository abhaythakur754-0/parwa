"""
Enterprise Integration Hub
Week 43 - Enterprise Integration Hub
"""

from .crm_base import (
    BaseCRMConnector,
    CRMConfig,
    CRMRecord,
    SyncDirection,
    SyncResult,
    SyncStatus
)
from .salesforce_connector import SalesforceConnector, SalesforceAuth
from .salesforce_mapper import SalesforceMapper
from .erp_base import (
    BaseERPConnector,
    ERPConfig,
    ERPEntity,
    ERPEntityType,
    ERPSyncResult,
    SyncMode
)
from .sap_connector import SAPConnector, SAPAuth
from .data_transformer import DataTransformer, TransformationRule
from .warehouse_base import (
    BaseWarehouseConnector,
    WarehouseConfig,
    WarehouseType,
    QueryResult,
    ExportJob,
    ExportFormat
)
from .snowflake_connector import SnowflakeConnector, SnowflakeConnection
from .bigquery_connector import BigQueryConnector, BigQueryConnection

__all__ = [
    # CRM
    "BaseCRMConnector",
    "CRMConfig",
    "CRMRecord",
    "SyncDirection",
    "SyncResult",
    "SyncStatus",
    "SalesforceConnector",
    "SalesforceAuth",
    "SalesforceMapper",
    # ERP
    "BaseERPConnector",
    "ERPConfig",
    "ERPEntity",
    "ERPEntityType",
    "ERPSyncResult",
    "SyncMode",
    "SAPConnector",
    "SAPAuth",
    "DataTransformer",
    "TransformationRule",
    # Data Warehouse
    "BaseWarehouseConnector",
    "WarehouseConfig",
    "WarehouseType",
    "QueryResult",
    "ExportJob",
    "ExportFormat",
    "SnowflakeConnector",
    "SnowflakeConnection",
    "BigQueryConnector",
    "BigQueryConnection"
]
