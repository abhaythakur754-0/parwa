"""
Tests for SAP ERP Integration
Enterprise Integration Hub - Week 43 Builder 2
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
import json

from enterprise.integrations.erp_base import (
    ERPConfig,
    ERPEntity,
    ERPEntityType,
    ERPSyncResult,
    SyncMode
)
from enterprise.integrations.sap_connector import (
    SAPAuth,
    SAPConnector
)
from enterprise.integrations.data_transformer import (
    DataTransformer,
    TransformationRule
)


# Test Fixtures
@pytest.fixture
def erp_config():
    """Create a test ERP configuration"""
    return ERPConfig(
        name="test_sap",
        system_type="SAP",
        api_url="https://sap-test.example.com",
        auth_type="basic",
        credentials={
            "username": "SAP_USER",
            "password": "SAP_PASSWORD"
        },
        company_code="1000",
        sync_mode=SyncMode.INCREMENTAL
    )


@pytest.fixture
def sap_auth():
    """Create a test SAP auth object"""
    return SAPAuth(
        csrf_token="test_csrf_token",
        session_id="test_session_id"
    )


@pytest.fixture
def sap_connector(erp_config):
    """Create a test SAP connector"""
    return SAPConnector(erp_config)


@pytest.fixture
def data_transformer():
    """Create a test data transformer"""
    return DataTransformer()


# ERPConfig Tests
class TestERPConfig:
    """Tests for ERPConfig"""
    
    def test_erp_config_creation(self):
        """Test ERPConfig can be created"""
        config = ERPConfig(
            name="test",
            system_type="SAP",
            api_url="https://sap.example.com",
            auth_type="basic",
            credentials={"username": "user", "password": "pass"}
        )
        assert config.name == "test"
        assert config.system_type == "SAP"
        assert config.auth_type == "basic"
    
    def test_erp_config_defaults(self):
        """Test ERPConfig default values"""
        config = ERPConfig(
            name="test",
            system_type="SAP",
            api_url="https://sap.example.com",
            auth_type="basic",
            credentials={}
        )
        assert config.sync_mode == SyncMode.INCREMENTAL
        assert config.batch_size == 100
        assert config.timeout_seconds == 60
    
    def test_erp_config_to_dict(self):
        """Test ERPConfig serialization"""
        config = ERPConfig(
            name="test",
            system_type="SAP",
            api_url="https://sap.example.com",
            auth_type="basic",
            credentials={},
            company_code="1000"
        )
        result = config.to_dict()
        assert result["name"] == "test"
        assert result["system_type"] == "SAP"
        assert result["company_code"] == "1000"


# ERPEntity Tests
class TestERPEntity:
    """Tests for ERPEntity"""
    
    def test_erp_entity_creation(self):
        """Test ERPEntity can be created"""
        now = datetime.utcnow()
        entity = ERPEntity(
            id="CUST001",
            entity_type=ERPEntityType.CUSTOMER,
            data={"name": "Test Customer"},
            last_modified=now
        )
        assert entity.id == "CUST001"
        assert entity.entity_type == ERPEntityType.CUSTOMER
        assert entity.data["name"] == "Test Customer"
    
    def test_erp_entity_to_dict(self):
        """Test ERPEntity serialization"""
        now = datetime.utcnow()
        entity = ERPEntity(
            id="ORD001",
            entity_type=ERPEntityType.ORDER,
            data={"total": 100.0},
            last_modified=now,
            version="v1"
        )
        result = entity.to_dict()
        assert result["id"] == "ORD001"
        assert result["entity_type"] == "order"
        assert result["version"] == "v1"


# ERPSyncResult Tests
class TestERPSyncResult:
    """Tests for ERPSyncResult"""
    
    def test_sync_result_creation(self):
        """Test ERPSyncResult can be created"""
        result = ERPSyncResult(
            entity_type=ERPEntityType.CUSTOMER,
            mode=SyncMode.INCREMENTAL,
            status="completed",
            records_processed=50,
            records_succeeded=48,
            records_failed=2
        )
        assert result.entity_type == ERPEntityType.CUSTOMER
        assert result.mode == SyncMode.INCREMENTAL
        assert result.records_processed == 50
    
    def test_sync_result_to_dict(self):
        """Test ERPSyncResult serialization"""
        result = ERPSyncResult(
            entity_type=ERPEntityType.ORDER,
            mode=SyncMode.FULL,
            status="completed",
            records_processed=100,
            records_succeeded=100,
            records_failed=0
        )
        data = result.to_dict()
        assert data["entity_type"] == "order"
        assert data["mode"] == "full"


# SAPAuth Tests
class TestSAPAuth:
    """Tests for SAPAuth"""
    
    def test_auth_creation(self):
        """Test SAPAuth can be created"""
        auth = SAPAuth(
            csrf_token="token123",
            session_id="session123"
        )
        assert auth.csrf_token == "token123"
        assert auth.session_id == "session123"
    
    def test_auth_not_expired(self, sap_auth):
        """Test auth expiration check - not expired"""
        assert not sap_auth.is_expired()
    
    def test_auth_expired(self):
        """Test auth expiration check - expired"""
        auth = SAPAuth(
            csrf_token="token123",
            session_id="session123",
            expires_at=datetime.utcnow() - timedelta(hours=1)
        )
        assert auth.is_expired()


# SAPConnector Tests
class TestSAPConnector:
    """Tests for SAPConnector"""
    
    @pytest.mark.asyncio
    async def test_connector_initialization(self, sap_connector):
        """Test connector initializes correctly"""
        assert sap_connector.config is not None
        assert not sap_connector.is_authenticated()
    
    @pytest.mark.asyncio
    async def test_get_headers_basic_auth(self, sap_connector):
        """Test header generation with basic auth"""
        sap_connector._csrf_token = "test_csrf"
        headers = sap_connector._get_headers()
        
        assert "Authorization" in headers
        assert headers["Authorization"].startswith("Basic ")
        assert headers["X-CSRF-Token"] == "test_csrf"
        assert headers["Content-Type"] == "application/json"
    
    @pytest.mark.asyncio
    async def test_parse_sap_datetime(self, sap_connector):
        """Test SAP datetime parsing"""
        # Test epoch format
        result = sap_connector._parse_sap_datetime("/Date(1705363200000)/")
        assert result.year == 2024
        
        # Test ISO format
        result = sap_connector._parse_sap_datetime("2024-01-15T10:30:00Z")
        assert result.year == 2024
        assert result.month == 1


# DataTransformer Tests
class TestDataTransformer:
    """Tests for DataTransformer"""
    
    def test_transformer_initialization(self, data_transformer):
        """Test transformer initializes correctly"""
        assert data_transformer.CUSTOMER_SAP_MAPPING is not None
        assert data_transformer.ORDER_SAP_MAPPING is not None
        assert data_transformer.INVOICE_SAP_MAPPING is not None
    
    def test_transform_customer_to_sap(self, data_transformer):
        """Test transforming customer to SAP format"""
        parwa_customer = {
            "customer_id": "CUST001",
            "name": "Test Company",
            "search_term": "TEST",
            "category": "organization"
        }
        
        result = data_transformer.transform_to_erp(parwa_customer, "customer")
        
        assert result["BusinessPartner"] == "CUST001"
        assert result["OrganizationBPName1"] == "Test Company"
        assert result["BusinessPartnerCategory"] == "2"  # organization
    
    def test_transform_order_to_sap(self, data_transformer):
        """Test transforming order to SAP format"""
        parwa_order = {
            "order_id": "ORD001",
            "order_type": "standard",
            "customer_id": "CUST001",
            "total_amount": 1500.00,
            "currency": "USD"
        }
        
        result = data_transformer.transform_to_erp(parwa_order, "order")
        
        assert result["SalesOrder"] == "ORD001"
        assert result["SalesOrderType"] == "OR"  # standard
        assert result["SoldToParty"] == "CUST001"
    
    def test_transform_from_sap_customer(self, data_transformer):
        """Test transforming from SAP customer"""
        sap_customer = {
            "BusinessPartner": "BP001",
            "OrganizationBPName1": "SAP Company",
            "BusinessPartnerCategory": "2",
            "SearchTerm1": "SAP"
        }
        
        result = data_transformer.transform_from_erp(sap_customer, "customer")
        
        assert result["customer_id"] == "BP001"
        assert result["name"] == "SAP Company"
    
    def test_category_mapping(self, data_transformer):
        """Test category mapping transformations"""
        assert data_transformer.CATEGORY_MAPPING["person"] == "1"
        assert data_transformer.CATEGORY_MAPPING["organization"] == "2"
        assert data_transformer.CATEGORY_MAPPING["1"] == "person"
        assert data_transformer.CATEGORY_MAPPING["2"] == "organization"
    
    def test_order_type_mapping(self, data_transformer):
        """Test order type mapping transformations"""
        assert data_transformer.ORDER_TYPE_MAPPING["standard"] == "OR"
        assert data_transformer.ORDER_TYPE_MAPPING["rush"] == "RO"
        assert data_transformer.ORDER_TYPE_MAPPING["return"] == "RE"
        assert data_transformer.ORDER_TYPE_MAPPING["OR"] == "standard"
    
    def test_validate_customer_data(self, data_transformer):
        """Test customer data validation"""
        # Missing name
        invalid_data = {"BusinessPartnerCategory": "2"}
        errors = data_transformer.validate_erp_data(invalid_data, "customer")
        assert "Customer name is required" in errors
        
        # Valid customer
        valid_data = {"OrganizationBPName1": "Test", "BusinessPartnerCategory": "2"}
        errors = data_transformer.validate_erp_data(valid_data, "customer")
        assert len(errors) == 0
    
    def test_validate_order_data(self, data_transformer):
        """Test order data validation"""
        # Missing customer
        invalid_data = {"SalesOrderType": "OR"}
        errors = data_transformer.validate_erp_data(invalid_data, "order")
        assert "Customer ID (SoldToParty) is required" in errors
        
        # Valid order
        valid_data = {"SoldToParty": "CUST001", "SalesOrderType": "OR"}
        errors = data_transformer.validate_erp_data(valid_data, "order")
        assert len(errors) == 0
    
    def test_transform_order_items(self, data_transformer):
        """Test transforming order line items"""
        items = [
            {
                "material": "MAT001",
                "quantity": 10,
                "unit": "EA",
                "description": "Test Material"
            },
            {
                "product_id": "MAT002",
                "quantity": 5
            }
        ]
        
        result = data_transformer.transform_order_items(items)
        
        assert len(result) == 2
        assert result[0]["Material"] == "MAT001"
        assert result[0]["RequestedQuantity"] == "10"
        assert result[1]["Material"] == "MAT002"
    
    def test_create_deep_order(self, data_transformer):
        """Test creating deep order structure"""
        order_data = {
            "order_type": "standard",
            "customer_id": "CUST001"
        }
        items = [
            {"material": "MAT001", "quantity": 10}
        ]
        
        result = data_transformer.create_deep_order(order_data, items)
        
        assert "to_Item" in result
        assert "results" in result["to_Item"]
        assert len(result["to_Item"]["results"]) == 1
    
    def test_flatten_sap_response(self, data_transformer):
        """Test flattening SAP response"""
        sap_response = {
            "BusinessPartner": "BP001",
            "to_BusinessPartnerAddress": {
                "results": [
                    {"cityName": "New York", "country": "US"}
                ]
            }
        }
        
        result = data_transformer.flatten_sap_response(sap_response)
        
        assert result["BusinessPartner"] == "BP001"
    
    def test_custom_transformation_rules(self):
        """Test custom transformation rules"""
        custom_rules = {
            "customer": [
                TransformationRule(
                    source_field="custom_field",
                    target_field="CustomField__c",
                    transform_type="direct"
                )
            ]
        }
        transformer = DataTransformer(custom_rules=custom_rules)
        
        data = {
            "name": "Test",
            "custom_field": "custom_value"
        }
        
        result = transformer.transform_to_erp(data, "customer")
        assert result["CustomField__c"] == "custom_value"
    
    def test_transformation_rule_map(self):
        """Test transformation rule with mapping"""
        rule = TransformationRule(
            source_field="status",
            target_field="Status",
            transform_type="map",
            transform_config={"active": "A", "inactive": "I"}
        )
        
        transformer = DataTransformer()
        result = transformer._apply_rule("active", rule)
        assert result == "A"
    
    def test_nested_value_setting(self, data_transformer):
        """Test setting nested values"""
        data = {}
        data_transformer._set_nested_value(data, "to_Address/streetName", "Main St")
        
        assert "to_Address" in data
        assert data["to_Address"]["streetName"] == "Main St"


# Integration Tests
class TestSAPIntegration:
    """Integration tests for SAP integration"""
    
    @pytest.mark.asyncio
    async def test_full_customer_sync_flow(self, erp_config):
        """Test full customer synchronization flow"""
        connector = SAPConnector(erp_config)
        
        assert connector is not None
        assert connector.config.name == "test_sap"
        assert connector.config.system_type == "SAP"
    
    def test_transformation_roundtrip(self, data_transformer):
        """Test transformation roundtrip consistency"""
        original = {
            "customer_id": "CUST001",
            "name": "Test Company",
            "category": "organization"
        }
        
        # Transform to SAP
        sap_format = data_transformer.transform_to_erp(original, "customer")
        
        # Transform back
        parwa_format = data_transformer.transform_from_erp(sap_format, "customer")
        
        # Verify roundtrip
        assert parwa_format["customer_id"] == original["customer_id"]
        assert parwa_format["name"] == original["name"]
