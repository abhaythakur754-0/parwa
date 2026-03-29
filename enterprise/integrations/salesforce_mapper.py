"""
Salesforce Data Mapper
Enterprise Integration Hub - Week 43 Builder 1
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class FieldMapping:
    """Field mapping configuration"""
    source_field: str
    target_field: str
    transform: Optional[str] = None
    required: bool = False
    default: Optional[Any] = None


class SalesforceMapper:
    """Map data between PARWA and Salesforce formats"""
    
    # Standard field mappings for Contact
    CONTACT_MAPPING = {
        # PARWA -> Salesforce
        "first_name": "FirstName",
        "last_name": "LastName",
        "email": "Email",
        "phone": "Phone",
        "mobile": "MobilePhone",
        "company": "AccountId",
        "title": "Title",
        "department": "Department",
        "address_street": "MailingStreet",
        "address_city": "MailingCity",
        "address_state": "MailingState",
        "address_postal": "MailingPostalCode",
        "address_country": "MailingCountry",
        "lead_source": "LeadSource",
        "description": "Description"
    }
    
    # Standard field mappings for Account
    ACCOUNT_MAPPING = {
        # PARWA -> Salesforce
        "name": "Name",
        "billing_street": "BillingStreet",
        "billing_city": "BillingCity",
        "billing_state": "BillingState",
        "billing_postal": "BillingPostalCode",
        "billing_country": "BillingCountry",
        "shipping_street": "ShippingStreet",
        "shipping_city": "ShippingCity",
        "shipping_state": "ShippingState",
        "shipping_postal": "ShippingPostalCode",
        "shipping_country": "ShippingCountry",
        "phone": "Phone",
        "website": "Website",
        "industry": "Industry",
        "employee_count": "NumberOfEmployees",
        "description": "Description",
        "type": "Type"
    }
    
    # Standard field mappings for Case
    CASE_MAPPING = {
        # PARWA -> Salesforce
        "subject": "Subject",
        "description": "Description",
        "status": "Status",
        "priority": "Priority",
        "origin": "Origin",
        "contact_id": "ContactId",
        "account_id": "AccountId",
        "type": "Type",
        "reason": "Reason",
        "product": "Product__c",
        "category": "Category__c",
        "resolution": "Resolution__c",
        "closed_date": "ClosedDate",
        "owner_id": "OwnerId"
    }
    
    # Status mappings between PARWA and Salesforce
    STATUS_MAPPING = {
        # PARWA -> Salesforce
        "new": "New",
        "open": "Working",
        "in_progress": "Working",
        "pending": "On Hold",
        "waiting_customer": "On Hold",
        "escalated": "Escalated",
        "resolved": "Closed",
        "closed": "Closed"
    }
    
    # Priority mappings
    PRIORITY_MAPPING = {
        # PARWA -> Salesforce
        "low": "Low",
        "medium": "Medium",
        "normal": "Medium",
        "high": "High",
        "urgent": "High",
        "critical": "High"
    }
    
    def __init__(self, custom_mappings: Optional[Dict[str, Dict[str, str]]] = None):
        """
        Initialize mapper with optional custom mappings.
        
        Args:
            custom_mappings: Custom field mappings per object type
        """
        self.custom_mappings = custom_mappings or {}
    
    def map_to_salesforce(
        self,
        data: Dict[str, Any],
        object_type: str
    ) -> Dict[str, Any]:
        """
        Map PARWA data to Salesforce format.
        
        Args:
            data: PARWA data dictionary
            object_type: Type of Salesforce object (Contact, Account, Case)
            
        Returns:
            Salesforce-formatted data dictionary
        """
        mapping = self._get_mapping(object_type)
        result = {}
        
        for source_field, target_field in mapping.items():
            if source_field in data:
                value = data[source_field]
                
                # Apply transformations
                value = self._transform_value(value, source_field, object_type)
                
                if value is not None:
                    result[target_field] = value
        
        # Apply custom mappings
        custom = self.custom_mappings.get(object_type, {})
        for source, target in custom.items():
            if source in data:
                result[target] = data[source]
        
        return result
    
    def map_from_salesforce(
        self,
        data: Dict[str, Any],
        object_type: str
    ) -> Dict[str, Any]:
        """
        Map Salesforce data to PARWA format.
        
        Args:
            data: Salesforce data dictionary
            object_type: Type of Salesforce object (Contact, Account, Case)
            
        Returns:
            PARWA-formatted data dictionary
        """
        mapping = self._get_mapping(object_type)
        result = {}
        
        # Reverse the mapping
        reverse_mapping = {v: k for k, v in mapping.items()}
        
        for source_field, target_field in reverse_mapping.items():
            if source_field in data:
                value = data[source_field]
                
                # Apply reverse transformations
                value = self._reverse_transform_value(value, target_field, object_type)
                
                if value is not None:
                    result[target_field] = value
        
        # Handle Salesforce system fields
        if "Id" in data:
            result["salesforce_id"] = data["Id"]
        if "CreatedDate" in data:
            result["created_at"] = self._parse_datetime(data["CreatedDate"])
        if "LastModifiedDate" in data:
            result["updated_at"] = self._parse_datetime(data["LastModifiedDate"])
        
        return result
    
    def _get_mapping(self, object_type: str) -> Dict[str, str]:
        """Get field mapping for object type"""
        mappings = {
            "Contact": self.CONTACT_MAPPING,
            "Account": self.ACCOUNT_MAPPING,
            "Case": self.CASE_MAPPING
        }
        return mappings.get(object_type, {})
    
    def _transform_value(
        self,
        value: Any,
        field_name: str,
        object_type: str
    ) -> Any:
        """Apply field-specific transformations"""
        
        # Status transformation for Case
        if object_type == "Case" and field_name == "status":
            return self.STATUS_MAPPING.get(value.lower(), value)
        
        # Priority transformation for Case
        if object_type == "Case" and field_name == "priority":
            return self.PRIORITY_MAPPING.get(value.lower(), value)
        
        # String trimming
        if isinstance(value, str):
            return value.strip() if value.strip() else None
        
        return value
    
    def _reverse_transform_value(
        self,
        value: Any,
        field_name: str,
        object_type: str
    ) -> Any:
        """Apply reverse field transformations"""
        
        # Reverse status transformation
        if object_type == "Case" and field_name == "status":
            reverse_status = {v: k for k, v in self.STATUS_MAPPING.items()}
            return reverse_status.get(value, value.lower())
        
        # Reverse priority transformation
        if object_type == "Case" and field_name == "priority":
            reverse_priority = {v: k for k, v in self.PRIORITY_MAPPING.items()}
            return reverse_priority.get(value, value.lower())
        
        return value
    
    def _parse_datetime(self, value: str) -> Optional[datetime]:
        """Parse Salesforce datetime string"""
        if not value:
            return None
        
        try:
            # Salesforce format: 2024-01-15T10:30:00.000Z
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None
    
    def map_contact_to_parwa(self, sf_contact: Dict[str, Any]) -> Dict[str, Any]:
        """Map Salesforce Contact to PARWA format"""
        result = self.map_from_salesforce(sf_contact, "Contact")
        
        # Additional PARWA-specific fields
        result["display_name"] = f"{sf_contact.get('FirstName', '')} {sf_contact.get('LastName', '')}".strip()
        
        return result
    
    def map_case_to_parwa(self, sf_case: Dict[str, Any]) -> Dict[str, Any]:
        """Map Salesforce Case to PARWA format"""
        result = self.map_from_salesforce(sf_case, "Case")
        
        # Map case number
        if "CaseNumber" in sf_case:
            result["case_number"] = sf_case["CaseNumber"]
        
        # Calculate SLA status
        result["sla_status"] = self._calculate_sla_status(sf_case)
        
        return result
    
    def _calculate_sla_status(self, sf_case: Dict[str, Any]) -> str:
        """Calculate SLA status from Salesforce case"""
        status = sf_case.get("Status", "New")
        
        if status in ("Closed", "Resolved"):
            return "met"
        
        # Check if escalated
        if status == "Escalated":
            return "breached"
        
        # Would need actual SLA data to calculate properly
        return "pending"
    
    def map_ticket_to_salesforce_case(
        self,
        ticket: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Map PARWA ticket to Salesforce Case"""
        mapping = {
            "subject": "Subject",
            "description": "Description",
            "status": "Status",
            "priority": "Priority",
            "customer_email": "SuppliedEmail",
            "customer_name": "SuppliedName",
            "customer_phone": "SuppliedPhone",
            "contact_id": "ContactId",
            "account_id": "AccountId",
            "category": "Type"
        }
        
        result = {}
        for source, target in mapping.items():
            if source in ticket:
                value = ticket[source]
                
                # Status transformation
                if source == "status":
                    value = self.STATUS_MAPPING.get(str(value).lower(), "New")
                # Priority transformation
                elif source == "priority":
                    value = self.PRIORITY_MAPPING.get(str(value).lower(), "Medium")
                
                result[target] = value
        
        # Set origin
        result["Origin"] = "PARWA AI"
        
        return result
    
    def validate_salesforce_data(
        self,
        data: Dict[str, Any],
        object_type: str
    ) -> List[str]:
        """Validate Salesforce data before submission"""
        errors = []
        
        if object_type == "Contact":
            if not data.get("LastName"):
                errors.append("LastName is required for Contact")
            if not data.get("Email"):
                errors.append("Email is recommended for Contact")
        
        elif object_type == "Account":
            if not data.get("Name"):
                errors.append("Name is required for Account")
        
        elif object_type == "Case":
            if not data.get("Subject"):
                errors.append("Subject is required for Case")
            if not data.get("Status"):
                errors.append("Status is required for Case")
        
        return errors
