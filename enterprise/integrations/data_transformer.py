"""
Data Transformer for ERP Integration
Enterprise Integration Hub - Week 43 Builder 2
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class TransformationRule:
    """Rule for data transformation"""
    source_field: str
    target_field: str
    transform_type: str = "direct"  # direct, map, format, compute
    transform_config: Optional[Dict[str, Any]] = None
    required: bool = False
    default: Optional[Any] = None


class DataTransformer:
    """Transform data between PARWA and ERP formats"""
    
    # Customer field mappings (PARWA -> SAP)
    CUSTOMER_SAP_MAPPING = {
        "customer_id": "BusinessPartner",
        "name": "OrganizationBPName1",
        "full_name": "BusinessPartnerFullName",
        "search_term": "SearchTerm1",
        "category": "BusinessPartnerCategory",
        "type": "BusinessPartnerType",
        "created_by": "CreatedByUser",
        "street": "to_BusinessPartnerAddress/streetName",
        "city": "to_BusinessPartnerAddress/cityName",
        "country": "to_BusinessPartnerAddress/country",
        "postal_code": "to_BusinessPartnerAddress/postalCode",
        "phone": "to_BusinessPartnerAddress/phoneNumber"
    }
    
    # Order field mappings (PARWA -> SAP)
    ORDER_SAP_MAPPING = {
        "order_id": "SalesOrder",
        "order_type": "SalesOrderType",
        "sales_org": "SalesOrganization",
        "distribution_channel": "DistributionChannel",
        "division": "OrganizationDivision",
        "customer_id": "SoldToParty",
        "total_amount": "TotalNetAmount",
        "currency": "TransactionCurrency",
        "order_date": "SalesOrderDate",
        "po_number": "PurchaseOrderByCustomer"
    }
    
    # Invoice field mappings (PARWA -> SAP)
    INVOICE_SAP_MAPPING = {
        "invoice_id": "BillingDocument",
        "invoice_type": "BillingDocumentType",
        "sales_org": "SalesOrganization",
        "distribution_channel": "DistributionChannel",
        "customer_id": "SoldToParty",
        "total_amount": "TotalNetAmount",
        "currency": "TransactionCurrency",
        "invoice_date": "BillingDocumentDate"
    }
    
    # Customer category mapping
    CATEGORY_MAPPING = {
        "person": "1",
        "organization": "2",
        "group": "3",
        "1": "person",
        "2": "organization",
        "3": "group"
    }
    
    # Order type mapping
    ORDER_TYPE_MAPPING = {
        "standard": "OR",
        "rush": "RO",
        "return": "RE",
        "credit_memo": "G2",
        "debit_memo": "L2",
        "OR": "standard",
        "RO": "rush",
        "RE": "return",
        "G2": "credit_memo",
        "L2": "debit_memo"
    }
    
    def __init__(self, custom_rules: Optional[Dict[str, List[TransformationRule]]] = None):
        """
        Initialize transformer with optional custom rules.
        
        Args:
            custom_rules: Custom transformation rules per entity type
        """
        self.custom_rules = custom_rules or {}
    
    def transform_to_erp(
        self,
        data: Dict[str, Any],
        entity_type: str,
        target_system: str = "SAP"
    ) -> Dict[str, Any]:
        """
        Transform PARWA data to ERP format.
        
        Args:
            data: PARWA data dictionary
            entity_type: Type of entity (customer, order, invoice)
            target_system: Target ERP system (SAP, Oracle, etc.)
            
        Returns:
            ERP-formatted data dictionary
        """
        mapping = self._get_mapping(entity_type, target_system)
        result = {}
        
        for source_field, target_field in mapping.items():
            if source_field in data:
                value = data[source_field]
                
                # Apply transformations
                value = self._transform_field(value, source_field, entity_type)
                
                # Handle nested fields (e.g., to_BusinessPartnerAddress/streetName)
                if "/" in target_field:
                    self._set_nested_value(result, target_field, value)
                elif value is not None:
                    result[target_field] = value
        
        # Apply custom rules
        custom = self.custom_rules.get(entity_type, [])
        for rule in custom:
            if rule.source_field in data:
                value = self._apply_rule(data[rule.source_field], rule)
                if value is not None:
                    result[rule.target_field] = value
        
        return result
    
    def transform_from_erp(
        self,
        data: Dict[str, Any],
        entity_type: str,
        source_system: str = "SAP"
    ) -> Dict[str, Any]:
        """
        Transform ERP data to PARWA format.
        
        Args:
            data: ERP data dictionary
            entity_type: Type of entity (customer, order, invoice)
            source_system: Source ERP system (SAP, Oracle, etc.)
            
        Returns:
            PARWA-formatted data dictionary
        """
        mapping = self._get_mapping(entity_type, source_system)
        result = {}
        
        # Reverse the mapping
        reverse_mapping = {v.split("/")[0]: k for k, v in mapping.items()}
        
        for source_field, target_field in reverse_mapping.items():
            if source_field in data:
                value = data[source_field]
                
                # Apply reverse transformations
                value = self._reverse_transform_field(value, target_field, entity_type)
                
                if value is not None:
                    result[target_field] = value
        
        # Handle nested fields from SAP
        for key, value in data.items():
            if isinstance(value, dict):
                for nested_key, nested_value in value.items():
                    flat_key = f"{key}_{nested_key}".lower()
                    if nested_value is not None:
                        result[flat_key] = nested_value
        
        return result
    
    def _get_mapping(
        self,
        entity_type: str,
        system: str
    ) -> Dict[str, str]:
        """Get field mapping for entity type and system"""
        mappings = {
            "customer": self.CUSTOMER_SAP_MAPPING,
            "order": self.ORDER_SAP_MAPPING,
            "invoice": self.INVOICE_SAP_MAPPING
        }
        return mappings.get(entity_type, {})
    
    def _transform_field(
        self,
        value: Any,
        field_name: str,
        entity_type: str
    ) -> Any:
        """Apply field-specific transformations"""
        
        # Category transformation
        if entity_type == "customer" and field_name == "category":
            return self.CATEGORY_MAPPING.get(str(value).lower(), str(value))
        
        # Order type transformation
        if entity_type == "order" and field_name == "order_type":
            return self.ORDER_TYPE_MAPPING.get(str(value).lower(), str(value))
        
        # Amount to string for SAP
        if field_name in ("total_amount", "net_amount"):
            return str(Decimal(str(value)).quantize(Decimal("0.01")))
        
        # Date formatting
        if field_name in ("order_date", "invoice_date", "created_at"):
            if isinstance(value, datetime):
                return value.strftime("%Y-%m-%d")
        
        # String trimming
        if isinstance(value, str):
            return value.strip() if value.strip() else None
        
        return value
    
    def _reverse_transform_field(
        self,
        value: Any,
        field_name: str,
        entity_type: str
    ) -> Any:
        """Apply reverse field transformations"""
        
        # Category reverse transformation
        if entity_type == "customer" and field_name == "category":
            return self.CATEGORY_MAPPING.get(str(value), str(value).lower())
        
        # Order type reverse transformation
        if entity_type == "order" and field_name == "order_type":
            return self.ORDER_TYPE_MAPPING.get(str(value), str(value).lower())
        
        # String to decimal
        if field_name in ("total_amount", "net_amount"):
            try:
                return float(Decimal(str(value)))
            except:
                return 0.0
        
        # SAP date parsing
        if field_name in ("order_date", "invoice_date"):
            if value and isinstance(value, str):
                try:
                    return datetime.strptime(value, "%Y-%m-%d")
                except ValueError:
                    pass
        
        return value
    
    def _set_nested_value(
        self,
        data: Dict[str, Any],
        path: str,
        value: Any
    ) -> None:
        """Set a value in a nested dictionary using path notation"""
        parts = path.split("/")
        current = data
        
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]
        
        current[parts[-1]] = value
    
    def _apply_rule(
        self,
        value: Any,
        rule: TransformationRule
    ) -> Any:
        """Apply a transformation rule"""
        if rule.transform_type == "direct":
            return value
        elif rule.transform_type == "map":
            mapping = rule.transform_config or {}
            return mapping.get(value, value)
        elif rule.transform_type == "format":
            fmt = rule.transform_config.get("format", "{}")
            return fmt.format(value)
        elif rule.transform_type == "compute":
            # Apply computation (e.g., multiply by factor)
            config = rule.transform_config or {}
            if config.get("operation") == "multiply":
                factor = config.get("factor", 1)
                return value * factor
        return value
    
    def validate_erp_data(
        self,
        data: Dict[str, Any],
        entity_type: str,
        system: str = "SAP"
    ) -> List[str]:
        """Validate ERP data before submission"""
        errors = []
        
        if entity_type == "customer":
            if not data.get("OrganizationBPName1") and not data.get("BusinessPartnerFullName"):
                errors.append("Customer name is required")
            if not data.get("BusinessPartnerCategory"):
                errors.append("BusinessPartnerCategory is required")
        
        elif entity_type == "order":
            if not data.get("SoldToParty"):
                errors.append("Customer ID (SoldToParty) is required")
            if not data.get("SalesOrderType"):
                errors.append("SalesOrderType is required")
        
        elif entity_type == "invoice":
            if not data.get("SoldToParty"):
                errors.append("Customer ID (SoldToParty) is required")
        
        return errors
    
    def transform_order_items(
        self,
        items: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Transform order line items to SAP format"""
        sap_items = []
        
        for item in items:
            sap_item = {
                "Material": item.get("material") or item.get("product_id"),
                "RequestedQuantity": str(item.get("quantity", 1)),
                "RequestedQuantityUnit": item.get("unit", "EA"),
                "SalesUnit": item.get("sales_unit", "EA")
            }
            
            # Add optional fields
            if item.get("description"):
                sap_item["ItemDescription"] = item.get("description")
            if item.get("plant"):
                sap_item["Plant"] = item.get("plant")
            if item.get("storage_location"):
                sap_item["StorageLocation"] = item.get("storage_location")
            
            sap_items.append(sap_item)
        
        return sap_items
    
    def create_deep_order(
        self,
        order_data: Dict[str, Any],
        items: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Create a deep order structure with items for SAP"""
        result = self.transform_to_erp(order_data, "order")
        
        # Add items
        result["to_Item"] = {
            "results": self.transform_order_items(items)
        }
        
        return result
    
    def flatten_sap_response(
        self,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Flatten nested SAP OData response"""
        result = {}
        
        for key, value in data.items():
            if key.startswith("__"):
                continue  # Skip metadata
            
            if isinstance(value, dict):
                if "results" in value:
                    # This is a nested collection
                    result[key] = [
                        self.flatten_sap_response(item)
                        for item in value["results"]
                    ]
                else:
                    # Flatten nested object
                    for nested_key, nested_value in value.items():
                        if not nested_key.startswith("__"):
                            flat_key = f"{key}_{nested_key}"
                            result[flat_key] = nested_value
            elif key == "d":
                # Top-level data wrapper
                return self.flatten_sap_response(value)
            else:
                result[key] = value
        
        return result
