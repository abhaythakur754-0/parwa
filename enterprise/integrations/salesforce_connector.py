"""
Salesforce CRM Connector
Enterprise Integration Hub - Week 43 Builder 1
"""

import base64
import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
import aiohttp
import logging

from .crm_base import (
    BaseCRMConnector,
    CRMConfig,
    CRMRecord,
    SyncDirection,
    SyncResult,
    SyncStatus
)

logger = logging.getLogger(__name__)


@dataclass
class SalesforceAuth:
    """Salesforce OAuth authentication data"""
    access_token: str
    instance_url: str
    token_type: str = "Bearer"
    issued_at: datetime = field(default_factory=datetime.utcnow)
    expires_in: int = 3600
    refresh_token: Optional[str] = None
    signature: Optional[str] = None
    
    def is_expired(self) -> bool:
        """Check if the token is expired"""
        expiry = self.issued_at + timedelta(seconds=self.expires_in - 300)
        return datetime.utcnow() > expiry
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "instance_url": self.instance_url,
            "token_type": self.token_type,
            "issued_at": self.issued_at.isoformat(),
            "expires_in": self.expires_in
        }


class SalesforceConnector(BaseCRMConnector):
    """Salesforce CRM integration connector"""
    
    API_VERSION = "v59.0"
    
    def __init__(self, config: CRMConfig):
        super().__init__(config)
        self.auth: Optional[SalesforceAuth] = None
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.config.timeout_seconds)
            )
        return self._session
    
    async def authenticate(self) -> bool:
        """Authenticate with Salesforce using OAuth 2.0"""
        try:
            session = await self._get_session()
            
            # OAuth token endpoint
            token_url = f"{self.config.api_url}/services/oauth2/token"
            
            # Build auth request
            auth_data = {
                "grant_type": self.config.credentials.get("grant_type", "password"),
                "client_id": self.config.credentials.get("client_id"),
                "client_secret": self.config.credentials.get("client_secret"),
            }
            
            if auth_data["grant_type"] == "password":
                auth_data["username"] = self.config.credentials.get("username")
                auth_data["password"] = self.config.credentials.get("password")
            elif auth_data["grant_type"] == "refresh_token":
                auth_data["refresh_token"] = self.config.credentials.get("refresh_token")
            
            async with session.post(token_url, data=auth_data) as response:
                if response.status == 200:
                    data = await response.json()
                    self.auth = SalesforceAuth(
                        access_token=data["access_token"],
                        instance_url=data["instance_url"],
                        token_type=data.get("token_type", "Bearer"),
                        expires_in=data.get("expires_in", 3600),
                        refresh_token=data.get("refresh_token"),
                        signature=data.get("signature")
                    )
                    self._authenticated = True
                    logger.info("Salesforce authentication successful")
                    return True
                else:
                    error = await response.text()
                    logger.error(f"Salesforce auth failed: {error}")
                    self._authenticated = False
                    return False
                    
        except Exception as e:
            logger.error(f"Salesforce authentication error: {e}")
            self._authenticated = False
            return False
    
    async def refresh_token(self) -> bool:
        """Refresh the access token"""
        if not self.auth or not self.auth.refresh_token:
            return await self.authenticate()
        
        try:
            session = await self._get_session()
            token_url = f"{self.config.api_url}/services/oauth2/token"
            
            refresh_data = {
                "grant_type": "refresh_token",
                "refresh_token": self.auth.refresh_token,
                "client_id": self.config.credentials.get("client_id"),
                "client_secret": self.config.credentials.get("client_secret")
            }
            
            async with session.post(token_url, data=refresh_data) as response:
                if response.status == 200:
                    data = await response.json()
                    self.auth.access_token = data["access_token"]
                    self.auth.expires_in = data.get("expires_in", 3600)
                    self.auth.issued_at = datetime.utcnow()
                    logger.info("Salesforce token refreshed")
                    return True
                return False
                
        except Exception as e:
            logger.error(f"Token refresh error: {e}")
            return False
    
    async def test_connection(self) -> bool:
        """Test the connection to Salesforce"""
        if not self._authenticated:
            if not await self.authenticate():
                return False
        
        try:
            session = await self._get_session()
            url = f"{self.auth.instance_url}/services/data/{self.API_VERSION}/limits"
            headers = self._get_headers()
            
            async with session.get(url, headers=headers) as response:
                return response.status == 200
                
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False
    
    def _get_headers(self) -> Dict[str, str]:
        """Get API request headers"""
        return {
            "Authorization": f"{self.auth.token_type} {self.auth.access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
    
    async def _ensure_auth(self) -> bool:
        """Ensure we have valid authentication"""
        if not self.auth:
            return await self.authenticate()
        if self.auth.is_expired():
            return await self.refresh_token()
        return True
    
    async def _query_soql(self, query: str) -> List[Dict[str, Any]]:
        """Execute a SOQL query"""
        if not await self._ensure_auth():
            raise ConnectionError("Not authenticated with Salesforce")
        
        session = await self._get_session()
        url = f"{self.auth.instance_url}/services/data/{self.API_VERSION}/query"
        headers = self._get_headers()
        params = {"q": query}
        
        async with session.get(url, headers=headers, params=params) as response:
            if response.status == 200:
                data = await response.json()
                return data.get("records", [])
            else:
                error = await response.text()
                raise Exception(f"SOQL query failed: {error}")
    
    async def fetch_contacts(
        self,
        modified_since: Optional[datetime] = None,
        limit: int = 100
    ) -> List[CRMRecord]:
        """Fetch contacts from Salesforce"""
        query = f"SELECT Id, FirstName, LastName, Email, Phone, AccountId, CreatedDate, LastModifiedDate FROM Contact"
        
        if modified_since:
            query += f" WHERE LastModifiedDate > {modified_since.isoformat()}Z"
        
        query += f" ORDER BY LastModifiedDate DESC LIMIT {limit}"
        
        records = await self._query_soql(query)
        
        return [
            CRMRecord(
                id=r["Id"],
                crm_type="Contact",
                data={
                    "first_name": r.get("FirstName"),
                    "last_name": r.get("LastName"),
                    "email": r.get("Email"),
                    "phone": r.get("Phone"),
                    "account_id": r.get("AccountId")
                },
                last_modified=datetime.fromisoformat(r["LastModifiedDate"].replace("Z", "+00:00")),
                created_at=datetime.fromisoformat(r["CreatedDate"].replace("Z", "+00:00"))
            )
            for r in records
        ]
    
    async def fetch_accounts(
        self,
        modified_since: Optional[datetime] = None,
        limit: int = 100
    ) -> List[CRMRecord]:
        """Fetch accounts from Salesforce"""
        query = f"SELECT Id, Name, BillingCity, BillingCountry, Industry, CreatedDate, LastModifiedDate FROM Account"
        
        if modified_since:
            query += f" WHERE LastModifiedDate > {modified_since.isoformat()}Z"
        
        query += f" ORDER BY LastModifiedDate DESC LIMIT {limit}"
        
        records = await self._query_soql(query)
        
        return [
            CRMRecord(
                id=r["Id"],
                crm_type="Account",
                data={
                    "name": r.get("Name"),
                    "billing_city": r.get("BillingCity"),
                    "billing_country": r.get("BillingCountry"),
                    "industry": r.get("Industry")
                },
                last_modified=datetime.fromisoformat(r["LastModifiedDate"].replace("Z", "+00:00")),
                created_at=datetime.fromisoformat(r["CreatedDate"].replace("Z", "+00:00"))
            )
            for r in records
        ]
    
    async def fetch_cases(
        self,
        modified_since: Optional[datetime] = None,
        limit: int = 100
    ) -> List[CRMRecord]:
        """Fetch support cases from Salesforce"""
        query = f"SELECT Id, CaseNumber, Subject, Description, Status, Priority, Origin, ContactId, AccountId, CreatedDate, LastModifiedDate FROM Case"
        
        if modified_since:
            query += f" WHERE LastModifiedDate > {modified_since.isoformat()}Z"
        
        query += f" ORDER BY LastModifiedDate DESC LIMIT {limit}"
        
        records = await self._query_soql(query)
        
        return [
            CRMRecord(
                id=r["Id"],
                crm_type="Case",
                data={
                    "case_number": r.get("CaseNumber"),
                    "subject": r.get("Subject"),
                    "description": r.get("Description"),
                    "status": r.get("Status"),
                    "priority": r.get("Priority"),
                    "origin": r.get("Origin"),
                    "contact_id": r.get("ContactId"),
                    "account_id": r.get("AccountId")
                },
                last_modified=datetime.fromisoformat(r["LastModifiedDate"].replace("Z", "+00:00")),
                created_at=datetime.fromisoformat(r["CreatedDate"].replace("Z", "+00:00"))
            )
            for r in records
        ]
    
    async def _create_record(
        self,
        object_type: str,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a record in Salesforce"""
        if not await self._ensure_auth():
            raise ConnectionError("Not authenticated with Salesforce")
        
        session = await self._get_session()
        url = f"{self.auth.instance_url}/services/data/{self.API_VERSION}/sobjects/{object_type}"
        headers = self._get_headers()
        
        async with session.post(url, headers=headers, json=data) as response:
            if response.status == 201:
                return await response.json()
            else:
                error = await response.text()
                raise Exception(f"Create {object_type} failed: {error}")
    
    async def _update_record(
        self,
        object_type: str,
        record_id: str,
        data: Dict[str, Any]
    ) -> bool:
        """Update a record in Salesforce"""
        if not await self._ensure_auth():
            raise ConnectionError("Not authenticated with Salesforce")
        
        session = await self._get_session()
        url = f"{self.auth.instance_url}/services/data/{self.API_VERSION}/sobjects/{object_type}/{record_id}"
        headers = self._get_headers()
        
        async with session.patch(url, headers=headers, json=data) as response:
            return response.status == 204
    
    async def create_case(self, case_data: Dict[str, Any]) -> CRMRecord:
        """Create a new case in Salesforce"""
        sf_data = {
            "Subject": case_data.get("subject"),
            "Description": case_data.get("description"),
            "Status": case_data.get("status", "New"),
            "Priority": case_data.get("priority", "Medium"),
            "Origin": case_data.get("origin", "PARWA"),
            "ContactId": case_data.get("contact_id"),
            "AccountId": case_data.get("account_id")
        }
        
        result = await self._create_record("Case", sf_data)
        
        return CRMRecord(
            id=result["id"],
            crm_type="Case",
            data=case_data,
            last_modified=datetime.utcnow(),
            created_at=datetime.utcnow()
        )
    
    async def update_case(
        self,
        case_id: str,
        case_data: Dict[str, Any]
    ) -> CRMRecord:
        """Update an existing case in Salesforce"""
        sf_data = {}
        
        if "subject" in case_data:
            sf_data["Subject"] = case_data["subject"]
        if "description" in case_data:
            sf_data["Description"] = case_data["description"]
        if "status" in case_data:
            sf_data["Status"] = case_data["status"]
        if "priority" in case_data:
            sf_data["Priority"] = case_data["priority"]
        
        await self._update_record("Case", case_id, sf_data)
        
        return CRMRecord(
            id=case_id,
            crm_type="Case",
            data=case_data,
            last_modified=datetime.utcnow(),
            created_at=datetime.utcnow()
        )
    
    async def push_contact(self, contact_data: Dict[str, Any]) -> CRMRecord:
        """Push a contact to Salesforce"""
        sf_data = {
            "FirstName": contact_data.get("first_name"),
            "LastName": contact_data.get("last_name"),
            "Email": contact_data.get("email"),
            "Phone": contact_data.get("phone"),
            "AccountId": contact_data.get("account_id")
        }
        
        result = await self._create_record("Contact", sf_data)
        
        return CRMRecord(
            id=result["id"],
            crm_type="Contact",
            data=contact_data,
            last_modified=datetime.utcnow(),
            created_at=datetime.utcnow()
        )
    
    async def push_account(self, account_data: Dict[str, Any]) -> CRMRecord:
        """Push an account to Salesforce"""
        sf_data = {
            "Name": account_data.get("name"),
            "BillingCity": account_data.get("billing_city"),
            "BillingCountry": account_data.get("billing_country"),
            "Industry": account_data.get("industry")
        }
        
        result = await self._create_record("Account", sf_data)
        
        return CRMRecord(
            id=result["id"],
            crm_type="Account",
            data=account_data,
            last_modified=datetime.utcnow(),
            created_at=datetime.utcnow()
        )
    
    async def close(self):
        """Close the HTTP session"""
        if self._session and not self._session.closed:
            await self._session.close()
    
    def __del__(self):
        """Cleanup on deletion"""
        if self._session and not self._session.closed:
            # Can't await in __del__, so just pass
            pass
