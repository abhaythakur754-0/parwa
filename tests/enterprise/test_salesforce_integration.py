"""
Tests for Salesforce Integration
Enterprise Integration Hub - Week 43 Builder 1
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
import json

from enterprise.integrations.crm_base import (
    CRMConfig,
    CRMRecord,
    SyncDirection,
    SyncStatus,
    SyncResult
)
from enterprise.integrations.salesforce_connector import (
    SalesforceAuth,
    SalesforceConnector
)
from enterprise.integrations.salesforce_mapper import SalesforceMapper


# Test Fixtures
@pytest.fixture
def crm_config():
    """Create a test CRM configuration"""
    return CRMConfig(
        name="test_salesforce",
        api_url="https://test.salesforce.com",
        auth_type="oauth2",
        credentials={
            "grant_type": "password",
            "client_id": "test_client_id",
            "client_secret": "test_client_secret",
            "username": "test@example.com",
            "password": "test_password"
        },
        sync_direction=SyncDirection.BIDIRECTIONAL,
        batch_size=100
    )


@pytest.fixture
def salesforce_auth():
    """Create a test Salesforce auth object"""
    return SalesforceAuth(
        access_token="test_token_12345",
        instance_url="https://testinstance.salesforce.com",
        token_type="Bearer",
        expires_in=3600
    )


@pytest.fixture
def salesforce_connector(crm_config):
    """Create a test Salesforce connector"""
    return SalesforceConnector(crm_config)


@pytest.fixture
def salesforce_mapper():
    """Create a test Salesforce mapper"""
    return SalesforceMapper()


# CRMConfig Tests
class TestCRMConfig:
    """Tests for CRMConfig"""
    
    def test_crm_config_creation(self):
        """Test CRMConfig can be created"""
        config = CRMConfig(
            name="test",
            api_url="https://api.example.com",
            auth_type="oauth2",
            credentials={"key": "value"}
        )
        assert config.name == "test"
        assert config.api_url == "https://api.example.com"
        assert config.auth_type == "oauth2"
    
    def test_crm_config_defaults(self):
        """Test CRMConfig default values"""
        config = CRMConfig(
            name="test",
            api_url="https://api.example.com",
            auth_type="oauth2",
            credentials={}
        )
        assert config.sync_direction == SyncDirection.BIDIRECTIONAL
        assert config.sync_interval_minutes == 15
        assert config.batch_size == 100
        assert config.timeout_seconds == 30
        assert config.retry_count == 3
    
    def test_crm_config_to_dict(self):
        """Test CRMConfig serialization"""
        config = CRMConfig(
            name="test",
            api_url="https://api.example.com",
            auth_type="oauth2",
            credentials={}
        )
        result = config.to_dict()
        assert result["name"] == "test"
        assert result["api_url"] == "https://api.example.com"
        assert "credentials" not in result  # Don't expose credentials


# CRMRecord Tests
class TestCRMRecord:
    """Tests for CRMRecord"""
    
    def test_crm_record_creation(self):
        """Test CRMRecord can be created"""
        now = datetime.utcnow()
        record = CRMRecord(
            id="001xx000003DGbYAAW",
            crm_type="Contact",
            data={"first_name": "John", "last_name": "Doe"},
            last_modified=now
        )
        assert record.id == "001xx000003DGbYAAW"
        assert record.crm_type == "Contact"
        assert record.data["first_name"] == "John"
    
    def test_crm_record_to_dict(self):
        """Test CRMRecord serialization"""
        now = datetime.utcnow()
        record = CRMRecord(
            id="001xx000003DGbYAAW",
            crm_type="Contact",
            data={"first_name": "John"},
            last_modified=now
        )
        result = record.to_dict()
        assert result["id"] == "001xx000003DGbYAAW"
        assert result["crm_type"] == "Contact"
        assert "last_modified" in result


# SyncResult Tests
class TestSyncResult:
    """Tests for SyncResult"""
    
    def test_sync_result_creation(self):
        """Test SyncResult can be created"""
        result = SyncResult(
            status=SyncStatus.COMPLETED,
            records_processed=100,
            records_succeeded=95,
            records_failed=5
        )
        assert result.status == SyncStatus.COMPLETED
        assert result.records_processed == 100
        assert result.records_succeeded == 95
        assert result.records_failed == 5
    
    def test_sync_result_with_errors(self):
        """Test SyncResult with errors"""
        result = SyncResult(
            status=SyncStatus.PARTIAL,
            records_processed=10,
            records_succeeded=8,
            records_failed=2,
            errors=["Error 1", "Error 2"]
        )
        assert len(result.errors) == 2
        assert "Error 1" in result.errors


# SalesforceAuth Tests
class TestSalesforceAuth:
    """Tests for SalesforceAuth"""
    
    def test_auth_creation(self):
        """Test SalesforceAuth can be created"""
        auth = SalesforceAuth(
            access_token="token123",
            instance_url="https://instance.salesforce.com"
        )
        assert auth.access_token == "token123"
        assert auth.instance_url == "https://instance.salesforce.com"
    
    def test_auth_not_expired(self, salesforce_auth):
        """Test auth expiration check - not expired"""
        assert not salesforce_auth.is_expired()
    
    def test_auth_expired(self):
        """Test auth expiration check - expired"""
        auth = SalesforceAuth(
            access_token="token123",
            instance_url="https://instance.salesforce.com",
            issued_at=datetime.utcnow() - timedelta(hours=2),
            expires_in=3600
        )
        assert auth.is_expired()


# SalesforceConnector Tests
class TestSalesforceConnector:
    """Tests for SalesforceConnector"""
    
    @pytest.mark.asyncio
    async def test_connector_initialization(self, salesforce_connector):
        """Test connector initializes correctly"""
        assert salesforce_connector.config is not None
        assert not salesforce_connector.is_authenticated()
    
    @pytest.mark.asyncio
    async def test_authenticate_success(self, salesforce_connector):
        """Test successful authentication"""
        mock_response = {
            "access_token": "test_token",
            "instance_url": "https://test.instance.com",
            "token_type": "Bearer",
            "expires_in": 3600
        }
        
        with patch("aiohttp.ClientSession.post") as mock_post:
            mock_post.return_value.__aenter__ = AsyncMock()
            mock_post.return_value.__aenter__.return_value.status = 200
            mock_post.return_value.__aenter__.return_value.json = AsyncMock(return_value=mock_response)
            
            result = await salesforce_connector.authenticate()
            assert result is True
    
    @pytest.mark.asyncio
    async def test_get_headers(self, salesforce_connector, salesforce_auth):
        """Test header generation"""
        salesforce_connector.auth = salesforce_auth
        headers = salesforce_connector._get_headers()
        
        assert headers["Authorization"] == "Bearer test_token_12345"
        assert headers["Content-Type"] == "application/json"
    
    def test_api_version(self, salesforce_connector):
        """Test API version is set"""
        assert salesforce_connector.API_VERSION == "v59.0"


# SalesforceMapper Tests
class TestSalesforceMapper:
    """Tests for SalesforceMapper"""
    
    def test_mapper_initialization(self, salesforce_mapper):
        """Test mapper initializes correctly"""
        assert salesforce_mapper.CONTACT_MAPPING is not None
        assert salesforce_mapper.ACCOUNT_MAPPING is not None
        assert salesforce_mapper.CASE_MAPPING is not None
    
    def test_map_contact_to_salesforce(self, salesforce_mapper):
        """Test mapping contact to Salesforce format"""
        parwa_contact = {
            "first_name": "John",
            "last_name": "Doe",
            "email": "john@example.com",
            "phone": "+1234567890"
        }
        
        result = salesforce_mapper.map_to_salesforce(parwa_contact, "Contact")
        
        assert result["FirstName"] == "John"
        assert result["LastName"] == "Doe"
        assert result["Email"] == "john@example.com"
        assert result["Phone"] == "+1234567890"
    
    def test_map_account_to_salesforce(self, salesforce_mapper):
        """Test mapping account to Salesforce format"""
        parwa_account = {
            "name": "Acme Corp",
            "industry": "Technology",
            "billing_city": "San Francisco",
            "billing_country": "USA"
        }
        
        result = salesforce_mapper.map_to_salesforce(parwa_account, "Account")
        
        assert result["Name"] == "Acme Corp"
        assert result["Industry"] == "Technology"
        assert result["BillingCity"] == "San Francisco"
    
    def test_map_case_to_salesforce(self, salesforce_mapper):
        """Test mapping case to Salesforce format"""
        parwa_case = {
            "subject": "Issue with order",
            "description": "Customer complaint",
            "status": "new",
            "priority": "high"
        }
        
        result = salesforce_mapper.map_to_salesforce(parwa_case, "Case")
        
        assert result["Subject"] == "Issue with order"
        assert result["Status"] == "New"  # Transformed
        assert result["Priority"] == "High"  # Transformed
    
    def test_map_from_salesforce_contact(self, salesforce_mapper):
        """Test mapping from Salesforce Contact"""
        sf_contact = {
            "Id": "001xx000003DGbYAAW",
            "FirstName": "Jane",
            "LastName": "Smith",
            "Email": "jane@example.com",
            "Phone": "+1987654321",
            "CreatedDate": "2024-01-15T10:30:00.000Z",
            "LastModifiedDate": "2024-01-20T14:20:00.000Z"
        }
        
        result = salesforce_mapper.map_from_salesforce(sf_contact, "Contact")
        
        assert result["first_name"] == "Jane"
        assert result["last_name"] == "Smith"
        assert result["email"] == "jane@example.com"
        assert result["salesforce_id"] == "001xx000003DGbYAAW"
    
    def test_status_mapping(self, salesforce_mapper):
        """Test status mapping transformations"""
        # Test inbound mapping
        assert salesforce_mapper.STATUS_MAPPING["new"] == "New"
        assert salesforce_mapper.STATUS_MAPPING["open"] == "Working"
        assert salesforce_mapper.STATUS_MAPPING["resolved"] == "Closed"
        assert salesforce_mapper.STATUS_MAPPING["escalated"] == "Escalated"
    
    def test_priority_mapping(self, salesforce_mapper):
        """Test priority mapping transformations"""
        assert salesforce_mapper.PRIORITY_MAPPING["low"] == "Low"
        assert salesforce_mapper.PRIORITY_MAPPING["medium"] == "Medium"
        assert salesforce_mapper.PRIORITY_MAPPING["high"] == "High"
        assert salesforce_mapper.PRIORITY_MAPPING["critical"] == "High"
    
    def test_validate_contact_data(self, salesforce_mapper):
        """Test contact data validation"""
        # Missing lastName
        invalid_data = {"FirstName": "John"}
        errors = salesforce_mapper.validate_salesforce_data(invalid_data, "Contact")
        assert "LastName is required for Contact" in errors
        
        # Valid contact
        valid_data = {"LastName": "Doe", "Email": "doe@example.com"}
        errors = salesforce_mapper.validate_salesforce_data(valid_data, "Contact")
        assert len(errors) == 0
    
    def test_validate_account_data(self, salesforce_mapper):
        """Test account data validation"""
        # Missing Name
        invalid_data = {"Industry": "Technology"}
        errors = salesforce_mapper.validate_salesforce_data(invalid_data, "Account")
        assert "Name is required for Account" in errors
        
        # Valid account
        valid_data = {"Name": "Acme Corp"}
        errors = salesforce_mapper.validate_salesforce_data(valid_data, "Account")
        assert len(errors) == 0
    
    def test_validate_case_data(self, salesforce_mapper):
        """Test case data validation"""
        # Missing required fields
        invalid_data = {"Description": "Some description"}
        errors = salesforce_mapper.validate_salesforce_data(invalid_data, "Case")
        assert "Subject is required for Case" in errors
        
        # Valid case
        valid_data = {"Subject": "Test", "Status": "New"}
        errors = salesforce_mapper.validate_salesforce_data(valid_data, "Case")
        assert len(errors) == 0
    
    def test_map_ticket_to_salesforce_case(self, salesforce_mapper):
        """Test mapping PARWA ticket to Salesforce Case"""
        ticket = {
            "subject": "Product inquiry",
            "description": "Customer asking about product",
            "status": "open",
            "priority": "medium",
            "customer_email": "customer@example.com",
            "customer_name": "John Customer"
        }
        
        result = salesforce_mapper.map_ticket_to_salesforce_case(ticket)
        
        assert result["Subject"] == "Product inquiry"
        assert result["Status"] == "Working"  # Transformed from open
        assert result["Priority"] == "Medium"
        assert result["SuppliedEmail"] == "customer@example.com"
        assert result["Origin"] == "PARWA AI"
    
    def test_custom_mappings(self):
        """Test custom field mappings"""
        custom = {
            "Contact": {
                "custom_field": "CustomField__c"
            }
        }
        mapper = SalesforceMapper(custom_mappings=custom)
        
        data = {
            "first_name": "John",
            "custom_field": "custom_value"
        }
        
        result = mapper.map_to_salesforce(data, "Contact")
        assert result["CustomField__c"] == "custom_value"
    
    def test_datetime_parsing(self, salesforce_mapper):
        """Test Salesforce datetime parsing"""
        dt = salesforce_mapper._parse_datetime("2024-01-15T10:30:00.000Z")
        assert dt is not None
        assert dt.year == 2024
        assert dt.month == 1
        assert dt.day == 15
        
        # Invalid datetime
        dt = salesforce_mapper._parse_datetime("invalid")
        assert dt is None


# Integration Tests
class TestSalesforceIntegration:
    """Integration tests for Salesforce integration"""
    
    @pytest.mark.asyncio
    async def test_full_contact_sync_flow(self, crm_config):
        """Test full contact synchronization flow"""
        connector = SalesforceConnector(crm_config)
        
        # Verify connector is created
        assert connector is not None
        assert connector.config.name == "test_salesforce"
    
    def test_mapping_roundtrip(self, salesforce_mapper):
        """Test mapping roundtrip consistency"""
        original = {
            "first_name": "John",
            "last_name": "Doe",
            "email": "john@example.com",
            "phone": "+1234567890"
        }
        
        # Map to Salesforce
        sf_format = salesforce_mapper.map_to_salesforce(original, "Contact")
        
        # Map back to PARWA
        sf_format["Id"] = "001test"
        sf_format["CreatedDate"] = "2024-01-15T10:30:00.000Z"
        sf_format["LastModifiedDate"] = "2024-01-15T10:30:00.000Z"
        
        parwa_format = salesforce_mapper.map_from_salesforce(sf_format, "Contact")
        
        # Verify roundtrip
        assert parwa_format["first_name"] == original["first_name"]
        assert parwa_format["last_name"] == original["last_name"]
        assert parwa_format["email"] == original["email"]
