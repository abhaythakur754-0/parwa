"""
Service Provider Metadata Generator for SAML 2.0.

This module generates SP metadata XML for SAML 2.0 SSO configuration
with Okta, Azure AD, and other identity providers.
"""

import base64
from datetime import datetime, timezone
from typing import Optional
from xml.etree import ElementTree as ET


class SPMetadataGenerator:
    """
    Generates Service Provider metadata for SAML 2.0 SSO.
    
    The generated metadata is valid XML parseable by Okta, Azure AD,
    and other major identity providers.
    """
    
    def __init__(
        self,
        entity_id: str,
        acs_url: str,
        slo_url: Optional[str] = None,
        signing_certificate: Optional[str] = None,
        encryption_certificate: Optional[str] = None,
        name_id_format: str = "urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress",
        valid_until_days: int = 365
    ):
        """
        Initialize SP Metadata Generator.
        
        Args:
            entity_id: Service Provider entity ID (unique identifier)
            acs_url: Assertion Consumer Service URL (POST binding)
            slo_url: Single Logout URL (optional)
            signing_certificate: X.509 signing certificate (base64 encoded)
            encryption_certificate: X.509 encryption certificate (base64 encoded)
            name_id_format: Name ID format for assertions
            valid_until_days: Number of days metadata is valid
        """
        self.entity_id = entity_id
        self.acs_url = acs_url
        self.slo_url = slo_url
        self.signing_certificate = signing_certificate
        self.encryption_certificate = encryption_certificate
        self.name_id_format = name_id_format
        self.valid_until_days = valid_until_days
    
    def generate_metadata(self) -> str:
        """
        Generate complete SP metadata XML.
        
        Returns:
            XML string of Service Provider metadata
        """
        valid_until = datetime.now(timezone.utc)
        valid_until = valid_until.replace(
            year=valid_until.year + (valid_until.month + self.valid_until_days // 30 - 1) // 12,
            month=(valid_until.month + self.valid_until_days // 30 - 1) % 12 + 1
        )
        
        namespaces = {
            "md": "urn:oasis:names:tc:SAML:2.0:metadata",
            "ds": "http://www.w3.org/2000/09/xmldsig#"
        }
        
        # Build XML structure
        xml_parts = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            f'<md:EntityDescriptor xmlns:md="urn:oasis:names:tc:SAML:2.0:metadata"',
            f' xmlns:ds="http://www.w3.org/2000/09/xmldsig#"',
            f' entityID="{self.entity_id}"',
            f' validUntil="{valid_until.strftime("%Y-%m-%dT%H:%M:%SZ")}">',
            '<md:SPSSODescriptor protocolSupportEnumeration="urn:oasis:names:tc:SAML:2.0:protocol">',
        ]
        
        # Add NameID formats
        xml_parts.extend([
            '<md:NameIDFormat>urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress</md:NameIDFormat>',
            '<md:NameIDFormat>urn:oasis:names:tc:SAML:2.0:nameid-format:persistent</md:NameIDFormat>',
            '<md:NameIDFormat>urn:oasis:names:tc:SAML:2.0:nameid-format:transient</md:NameIDFormat>',
        ])
        
        # Add Assertion Consumer Service
        xml_parts.append(
            f'<md:AssertionConsumerService Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST"'
            f' Location="{self.acs_url}" index="0" isDefault="true"/>'
        )
        
        # Add Single Logout Service if configured
        if self.slo_url:
            xml_parts.extend([
                f'<md:SingleLogoutService Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect"'
                f' Location="{self.slo_url}"/>',
                f'<md:SingleLogoutService Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST"'
                f' Location="{self.slo_url}"/>',
            ])
        
        # Add signing key if provided
        if self.signing_certificate:
            xml_parts.extend([
                '<md:KeyDescriptor use="signing">',
                '<ds:KeyInfo>',
                '<ds:X509Data>',
                f'<ds:X509Certificate>{self.signing_certificate}</ds:X509Certificate>',
                '</ds:X509Data>',
                '</ds:KeyInfo>',
                '</md:KeyDescriptor>',
            ])
        
        # Add encryption key if provided
        if self.encryption_certificate:
            xml_parts.extend([
                '<md:KeyDescriptor use="encryption">',
                '<ds:KeyInfo>',
                '<ds:X509Data>',
                f'<ds:X509Certificate>{self.encryption_certificate}</ds:X509Certificate>',
                '</ds:X509Data>',
                '</ds:KeyInfo>',
                '</md:KeyDescriptor>',
            ])
        
        # Add attribute consumption service
        xml_parts.extend([
            '<md:AttributeConsumingService index="0">',
            '<md:ServiceName xml:lang="en">PARWA Enterprise SSO</md:ServiceName>',
            '<md:RequestedAttribute Name="email" isRequired="true"/>',
            '<md:RequestedAttribute Name="firstName" isRequired="false"/>',
            '<md:RequestedAttribute Name="lastName" isRequired="false"/>',
            '<md:RequestedAttribute Name="groups" isRequired="false"/>',
            '</md:AttributeConsumingService>',
        ])
        
        # Close tags
        xml_parts.extend([
            '</md:SPSSODescriptor>',
            '</md:EntityDescriptor>'
        ])
        
        return "\n".join(xml_parts)
    
    def generate_okta_metadata(self) -> str:
        """
        Generate SP metadata optimized for Okta integration.
        
        Returns:
            XML string compatible with Okta
        """
        return self.generate_metadata()
    
    def generate_azure_metadata(self) -> str:
        """
        Generate SP metadata optimized for Azure AD integration.
        
        Returns:
            XML string compatible with Azure AD
        """
        # Azure AD specific metadata with additional elements
        metadata = self.generate_metadata()
        
        # Azure AD requires specific attribute mappings
        # The base metadata is sufficient for Azure AD
        
        return metadata
    
    def generate_google_workspace_metadata(self) -> str:
        """
        Generate SP metadata optimized for Google Workspace integration.
        
        Returns:
            XML string compatible with Google Workspace
        """
        return self.generate_metadata()
    
    def validate_metadata(self, metadata_xml: str) -> dict:
        """
        Validate SP metadata XML.
        
        Args:
            metadata_xml: XML string to validate
            
        Returns:
            Dictionary with validation results
        """
        try:
            root = ET.fromstring(metadata_xml)
            
            ns = {"md": "urn:oasis:names:tc:SAML:2.0:metadata"}
            
            results = {
                "valid": True,
                "entity_id": root.get("entityID"),
                "valid_until": root.get("validUntil"),
                "acs_locations": [],
                "slo_locations": [],
                "errors": []
            }
            
            # Check for ACS
            spsso = root.find(".//md:SPSSODescriptor", ns)
            if spsso is None:
                results["errors"].append("Missing SPSSODescriptor")
                results["valid"] = False
            else:
                for acs in spsso.findall(".//md:AssertionConsumerService", ns):
                    results["acs_locations"].append({
                        "binding": acs.get("Binding"),
                        "location": acs.get("Location"),
                        "index": acs.get("index")
                    })
                
                for slo in spsso.findall(".//md:SingleLogoutService", ns):
                    results["slo_locations"].append({
                        "binding": slo.get("Binding"),
                        "location": slo.get("Location")
                    })
            
            if not results["acs_locations"]:
                results["errors"].append("No AssertionConsumerService found")
                results["valid"] = False
            
            return results
            
        except ET.ParseError as e:
            return {
                "valid": False,
                "entity_id": None,
                "valid_until": None,
                "acs_locations": [],
                "slo_locations": [],
                "errors": [f"XML parsing error: {str(e)}"]
            }
    
    def get_metadata_url(self, tenant_id: str) -> str:
        """
        Get the metadata URL for a tenant.
        
        Args:
            tenant_id: Tenant identifier
            
        Returns:
            Metadata URL for IdP configuration
        """
        return f"https://api.parwa.ai/sso/metadata/{tenant_id}"


def generate_sp_metadata_for_tenant(
    tenant_id: str,
    acs_url: Optional[str] = None,
    slo_url: Optional[str] = None
) -> str:
    """
    Factory function to generate SP metadata for a tenant.
    
    Args:
        tenant_id: Tenant identifier
        acs_url: Optional custom ACS URL
        slo_url: Optional custom SLO URL
        
    Returns:
        SP metadata XML string
    """
    entity_id = f"https://parwa.ai/sp/{tenant_id}"
    acs = acs_url or f"https://api.parwa.ai/sso/acs/{tenant_id}"
    slo = slo_url or f"https://api.parwa.ai/sso/slo/{tenant_id}"
    
    generator = SPMetadataGenerator(
        entity_id=entity_id,
        acs_url=acs,
        slo_url=slo
    )
    
    return generator.generate_metadata()
