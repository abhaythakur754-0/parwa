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

__all__ = [
    "BaseCRMConnector",
    "CRMConfig",
    "CRMRecord",
    "SyncDirection",
    "SyncResult",
    "SyncStatus",
    "SalesforceConnector",
    "SalesforceAuth",
    "SalesforceMapper"
]
