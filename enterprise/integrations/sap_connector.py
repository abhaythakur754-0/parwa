"""
SAP ERP Connector
Enterprise Integration Hub - Week 43 Builder 2
"""

import base64
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
import aiohttp
import logging

from .erp_base import (
    BaseERPConnector,
    ERPConfig,
    ERPEntity,
    ERPEntityType,
    ERPSyncResult,
    SyncMode
)

logger = logging.getLogger(__name__)


@dataclass
class SAPAuth:
    """SAP authentication data"""
    csrf_token: str
    session_id: str
    authenticated_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    
    def is_expired(self) -> bool:
        """Check if the session is expired"""
        if not self.expires_at:
            return False
        return datetime.utcnow() > self.expires_at


class SAPConnector(BaseERPConnector):
    """SAP S/4HANA OData API integration connector"""
    
    def __init__(self, config: ERPConfig):
        super().__init__(config)
        self.auth: Optional[SAPAuth] = None
        self._session: Optional[aiohttp.ClientSession] = None
        self._csrf_token: Optional[str] = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session"""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=self.config.timeout_seconds)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session
    
    async def authenticate(self) -> bool:
        """Authenticate with SAP using Basic Auth or OAuth"""
        try:
            session = await self._get_session()
            
            # Build auth header
            if self.config.auth_type == "basic":
                username = self.config.credentials.get("username")
                password = self.config.credentials.get("password")
                credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
                auth_header = f"Basic {credentials}"
            elif self.config.auth_type == "oauth":
                auth_header = f"Bearer {self.config.credentials.get('access_token')}"
            else:
                raise ValueError(f"Unsupported auth type: {self.config.auth_type}")
            
            # Fetch CSRF token
            headers = {
                "Authorization": auth_header,
                "X-CSRF-Token": "Fetch",
                "Accept": "application/json"
            }
            
            # Make request to get CSRF token
            url = f"{self.config.api_url}/sap/opu/odata/sap/API_BUSINESS_PARTNER"
            
            async with session.get(url, headers=headers) as response:
                if response.status in (200, 201):
                    self._csrf_token = response.headers.get("x-csrf-token")
                    
                    self.auth = SAPAuth(
                        csrf_token=self._csrf_token or "",
                        session_id=response.headers.get("set-cookie", ""),
                        expires_at=datetime.utcnow() + timedelta(hours=8)
                    )
                    
                    self._authenticated = True
                    logger.info("SAP authentication successful")
                    return True
                else:
                    error = await response.text()
                    logger.error(f"SAP auth failed: {error}")
                    self._authenticated = False
                    return False
                    
        except Exception as e:
            logger.error(f"SAP authentication error: {e}")
            self._authenticated = False
            return False
    
    async def test_connection(self) -> bool:
        """Test the connection to SAP"""
        if not self._authenticated:
            if not await self.authenticate():
                return False
        
        try:
            session = await self._get_session()
            headers = self._get_headers()
            
            # Test with a simple API call
            url = f"{self.config.api_url}/sap/opu/odata/sap/API_BUSINESS_PARTNER/$count"
            
            async with session.get(url, headers=headers) as response:
                return response.status == 200
                
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False
    
    def _get_headers(self) -> Dict[str, str]:
        """Get API request headers"""
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        
        if self.config.auth_type == "basic":
            username = self.config.credentials.get("username")
            password = self.config.credentials.get("password")
            credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
            headers["Authorization"] = f"Basic {credentials}"
        elif self.config.auth_type == "oauth":
            headers["Authorization"] = f"Bearer {self.config.credentials.get('access_token')}"
        
        if self._csrf_token:
            headers["X-CSRF-Token"] = self._csrf_token
        
        return headers
    
    async def _ensure_auth(self) -> bool:
        """Ensure we have valid authentication"""
        if not self.auth:
            return await self.authenticate()
        if self.auth.is_expired():
            return await self.authenticate()
        return True
    
    async def _fetch_odata(
        self,
        endpoint: str,
        filters: Optional[str] = None,
        select: Optional[str] = None,
        top: int = 100,
        skip: int = 0
    ) -> List[Dict[str, Any]]:
        """Fetch data from SAP OData endpoint"""
        if not await self._ensure_auth():
            raise ConnectionError("Not authenticated with SAP")
        
        session = await self._get_session()
        headers = self._get_headers()
        
        url = f"{self.config.api_url}{endpoint}"
        params = {"$top": top, "$skip": skip}
        
        if filters:
            params["$filter"] = filters
        if select:
            params["$select"] = select
        
        async with session.get(url, headers=headers, params=params) as response:
            if response.status == 200:
                data = await response.json()
                return data.get("d", {}).get("results", [])
            else:
                error = await response.text()
                raise Exception(f"OData fetch failed: {error}")
    
    async def _create_odata(
        self,
        endpoint: str,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create an entity via SAP OData API"""
        if not await self._ensure_auth():
            raise ConnectionError("Not authenticated with SAP")
        
        session = await self._get_session()
        headers = self._get_headers()
        
        url = f"{self.config.api_url}{endpoint}"
        
        async with session.post(url, headers=headers, json=data) as response:
            if response.status in (200, 201):
                return await response.json()
            else:
                error = await response.text()
                raise Exception(f"OData create failed: {error}")
    
    async def _update_odata(
        self,
        endpoint: str,
        entity_id: str,
        data: Dict[str, Any]
    ) -> bool:
        """Update an entity via SAP OData API"""
        if not await self._ensure_auth():
            raise ConnectionError("Not authenticated with SAP")
        
        session = await self._get_session()
        headers = self._get_headers()
        
        # SAP OData uses MERGE or PATCH for updates
        headers["X-HTTP-Method"] = "MERGE"
        
        url = f"{self.config.api_url}{endpoint}('{entity_id}')"
        
        async with session.post(url, headers=headers, json=data) as response:
            return response.status in (200, 204)
    
    async def fetch_customers(
        self,
        modified_since: Optional[datetime] = None,
        limit: int = 100
    ) -> List[ERPEntity]:
        """Fetch customers (Business Partners) from SAP"""
        filters = None
        if modified_since:
            # SAP OData datetime filter format
            dt_str = modified_since.strftime("%Y-%m-%dT%H:%M:%S")
            filters = f"LastChangeDateTime gt datetime'{dt_str}'"
        
        select = "BusinessPartner,BusinessPartnerFullName,OrganizationBPName1,SearchTerm1,BusinessPartnerCategory,BusinessPartnerType,CreatedByUser,CreationDate,LastChangeDate,LastChangeDateTime"
        
        records = await self._fetch_odata(
            "/sap/opu/odata/sap/API_BUSINESS_PARTNER/A_BusinessPartner",
            filters=filters,
            select=select,
            top=limit
        )
        
        return [
            ERPEntity(
                id=r.get("BusinessPartner", ""),
                entity_type=ERPEntityType.CUSTOMER,
                data={
                    "name": r.get("BusinessPartnerFullName") or r.get("OrganizationBPName1"),
                    "search_term": r.get("SearchTerm1"),
                    "category": r.get("BusinessPartnerCategory"),
                    "type": r.get("BusinessPartnerType"),
                    "created_by": r.get("CreatedByUser")
                },
                last_modified=self._parse_sap_datetime(r.get("LastChangeDateTime")),
                version=r.get("BusinessPartner")
            )
            for r in records
        ]
    
    async def fetch_orders(
        self,
        modified_since: Optional[datetime] = None,
        limit: int = 100
    ) -> List[ERPEntity]:
        """Fetch sales orders from SAP"""
        filters = None
        if modified_since:
            dt_str = modified_since.strftime("%Y-%m-%dT%H:%M:%S")
            filters = f"LastChangeDateTime gt datetime'{dt_str}'"
        
        select = "SalesOrder,SalesOrderType,SalesOrganization,DistributionChannel,OrganizationDivision,SoldToParty,TotalNetAmount,TransactionCurrency,SalesOrderDate,LastChangeDateTime"
        
        records = await self._fetch_odata(
            "/sap/opu/odata/sap/API_SALES_ORDER_SRV/A_SalesOrder",
            filters=filters,
            select=select,
            top=limit
        )
        
        return [
            ERPEntity(
                id=r.get("SalesOrder", ""),
                entity_type=ERPEntityType.ORDER,
                data={
                    "order_type": r.get("SalesOrderType"),
                    "sales_organization": r.get("SalesOrganization"),
                    "distribution_channel": r.get("DistributionChannel"),
                    "division": r.get("OrganizationDivision"),
                    "customer_id": r.get("SoldToParty"),
                    "total_amount": float(r.get("TotalNetAmount", 0)),
                    "currency": r.get("TransactionCurrency"),
                    "order_date": r.get("SalesOrderDate")
                },
                last_modified=self._parse_sap_datetime(r.get("LastChangeDateTime"))
            )
            for r in records
        ]
    
    async def fetch_invoices(
        self,
        modified_since: Optional[datetime] = None,
        limit: int = 100
    ) -> List[ERPEntity]:
        """Fetch billing documents (invoices) from SAP"""
        filters = None
        if modified_since:
            dt_str = modified_since.strftime("%Y-%m-%dT%H:%M:%S")
            filters = f"LastChangeDateTime gt datetime'{dt_str}'"
        
        select = "BillingDocument,BillingDocumentType,SalesOrganization,DistributionChannel,SoldToParty,TotalNetAmount,TransactionCurrency,BillingDocumentDate,LastChangeDateTime"
        
        records = await self._fetch_odata(
            "/sap/opu/odata/sap/API_BILLING_DOCUMENT_SRV/A_BillingDocument",
            filters=filters,
            select=select,
            top=limit
        )
        
        return [
            ERPEntity(
                id=r.get("BillingDocument", ""),
                entity_type=ERPEntityType.INVOICE,
                data={
                    "invoice_type": r.get("BillingDocumentType"),
                    "sales_organization": r.get("SalesOrganization"),
                    "distribution_channel": r.get("DistributionChannel"),
                    "customer_id": r.get("SoldToParty"),
                    "total_amount": float(r.get("TotalNetAmount", 0)),
                    "currency": r.get("TransactionCurrency"),
                    "invoice_date": r.get("BillingDocumentDate")
                },
                last_modified=self._parse_sap_datetime(r.get("LastChangeDateTime"))
            )
            for r in records
        ]
    
    async def push_customer(self, customer_data: Dict[str, Any]) -> ERPEntity:
        """Push a customer (Business Partner) to SAP"""
        sap_data = {
            "BusinessPartnerCategory": customer_data.get("category", "2"),  # 2 = Organization
            "OrganizationBPName1": customer_data.get("name"),
            "SearchTerm1": customer_data.get("search_term"),
            "BusinessPartnerType": customer_data.get("bp_type", "bptr2"),  # bptr2 = Customer
        }
        
        result = await self._create_odata(
            "/sap/opu/odata/sap/API_BUSINESS_PARTNER/A_BusinessPartner",
            sap_data
        )
        
        return ERPEntity(
            id=result.get("d", {}).get("BusinessPartner", ""),
            entity_type=ERPEntityType.CUSTOMER,
            data=customer_data,
            last_modified=datetime.utcnow()
        )
    
    async def push_order(self, order_data: Dict[str, Any]) -> ERPEntity:
        """Push a sales order to SAP"""
        sap_data = {
            "SalesOrderType": order_data.get("order_type", "OR"),
            "SalesOrganization": order_data.get("sales_organization", "1000"),
            "DistributionChannel": order_data.get("distribution_channel", "10"),
            "OrganizationDivision": order_data.get("division", "00"),
            "SoldToParty": order_data.get("customer_id"),
            "PurchaseOrderByCustomer": order_data.get("po_number", f"PARWA-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}")
        }
        
        # Add line items if provided
        if "items" in order_data:
            sap_data["to_Item"] = {
                "results": [
                    {
                        "Material": item.get("material"),
                        "RequestedQuantity": item.get("quantity"),
                        "RequestedQuantityUnit": item.get("unit", "EA")
                    }
                    for item in order_data["items"]
                ]
            }
        
        result = await self._create_odata(
            "/sap/opu/odata/sap/API_SALES_ORDER_SRV/A_SalesOrder",
            sap_data
        )
        
        return ERPEntity(
            id=result.get("d", {}).get("SalesOrder", ""),
            entity_type=ERPEntityType.ORDER,
            data=order_data,
            last_modified=datetime.utcnow()
        )
    
    def _parse_sap_datetime(self, value: Optional[str]) -> datetime:
        """Parse SAP datetime string"""
        if not value:
            return datetime.utcnow()
        
        try:
            # SAP OData format: /Date(1705363200000)/
            if value.startswith("/Date("):
                timestamp = int(value[6:-2])
                return datetime.utcfromtimestamp(timestamp / 1000)
            
            # ISO format
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return datetime.utcnow()
    
    async def get_customer_by_id(self, customer_id: str) -> Optional[ERPEntity]:
        """Get a specific customer by ID"""
        if not await self._ensure_auth():
            raise ConnectionError("Not authenticated with SAP")
        
        session = await self._get_session()
        headers = self._get_headers()
        
        url = f"{self.config.api_url}/sap/opu/odata/sap/API_BUSINESS_PARTNER/A_BusinessPartner('{customer_id}')"
        
        async with session.get(url, headers=headers) as response:
            if response.status == 200:
                data = await response.json()
                r = data.get("d", {})
                return ERPEntity(
                    id=r.get("BusinessPartner", ""),
                    entity_type=ERPEntityType.CUSTOMER,
                    data={
                        "name": r.get("BusinessPartnerFullName"),
                        "category": r.get("BusinessPartnerCategory")
                    },
                    last_modified=self._parse_sap_datetime(r.get("LastChangeDateTime"))
                )
            return None
    
    async def close(self):
        """Close the HTTP session"""
        if self._session and not self._session.closed:
            await self._session.close()
