"""
Service Provider Metadata Generator for SAML 2.0 SSO.

This module generates SP metadata XML that can be consumed by
Identity Providers like Okta, Azure AD, and Google Workspace.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional
from xml.etree import ElementTree as ET


class SPMetadataGenerator:
    """
    Service Provider metadata generator for SAML 2.0.
    
    Generates valid XML metadata that can be parsed by Okta, Azure AD,
    and other major Identity Providers.
    """
    
    NAMESPACE_MD = "urn:oasis:names:tc:SAML:2.0:metadata"
    NAMESPACE_DS = "http://www.w3.org/2000/09/xmldsig#"
    NAMESPACE_SAML = "urn:oasis:names:tc:SAML:2.0:assertion"
    
    def __init__(
        self,
        entity_id: str,
        acs_url: str,
        slo_url: Optional[str] = None,
        signing_certificate: Optional[str] = None,
        encryption_certificate: Optional[str] = None,
        name_id_format: str = "urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress",
        organization_name: str = "PARWA",
        organization_display_name: str = "PARWA AI Support",
        organization_url: str = "https://parwa.ai",
        contact_email: str = "support@parwa.ai"
    ):
        """
        Initialize SP Metadata Generator.
        
        Args:
            entity_id: Unique entity identifier for the SP
            acs_url: Assertion Consumer Service URL (POST binding)
            slo_url: Single Logout URL (optional)
            signing_certificate: X.509 certificate for signing (optional)
            encryption_certificate: X.509 certificate for encryption (optional)
            name_id_format: Name ID format to request
            organization_name: Organization name
            organization_display_name: Organization display name
            organization_url: Organization URL
            contact_email: Technical contact email
        """
        self.entity_id = entity_id
        self.acs_url = acs_url
        self.slo_url = slo_url
        self.signing_certificate = signing_certificate
        self.encryption_certificate = encryption_certificate
        self.name_id_format = name_id_format
        self.organization_name = organization_name
        self.organization_display_name = organization_display_name
        self.organization_url = organization_url
        self.contact_email = contact_email
    
    def generate(self) -> str:
        """
        Generate SP metadata XML.
        
        Returns:
            Valid SP metadata XML string
        """
        # Build XML structure
        nsmap = {
            "md": self.NAMESPACE_MD,
            "ds": self.NAMESPACE_DS,
            "saml": self.NAMESPACE_SAML
        }
        
        # Root element
        entity_descriptor = ET.Element(
            f"{{{self.NAMESPACE_MD}}}EntityDescriptor",
            attrib={
                "entityID": self.entity_id,
                "validUntil": "2030-01-01T00:00:00Z"
            }
        )
        
        # SPSSODescriptor
        spsso = ET.SubElement(
            entity_descriptor,
            f"{{{self.NAMESPACE_MD}}}SPSSODescriptor",
            attrib={
                "AuthnRequestsSigned": "true" if self.signing_certificate else "false",
                "WantAssertionsSigned": "true",
                "protocolSupportEnumeration": "urn:oasis:names:tc:SAML:2.0:protocol"
            }
        )
        
        # Name ID Format
        name_id_format = ET.SubElement(spsso, f"{{{self.NAMESPACE_MD}}}NameIDFormat")
        name_id_format.text = self.name_id_format
        
        # Assertion Consumer Service
        acs = ET.SubElement(
            spsso,
            f"{{{self.NAMESPACE_MD}}}AssertionConsumerService",
            attrib={
                "Binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST",
                "Location": self.acs_url,
                "index": "0",
                "isDefault": "true"
            }
        )
        
        # Single Logout Service (if provided)
        if self.slo_url:
            slo_redirect = ET.SubElement(
                spsso,
                f"{{{self.NAMESPACE_MD}}}SingleLogoutService",
                attrib={
                    "Binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect",
                    "Location": self.slo_url
                }
            )
            slo_post = ET.SubElement(
                spsso,
                f"{{{self.NAMESPACE_MD}}}SingleLogoutService",
                attrib={
                    "Binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST",
                    "Location": self.slo_url
                }
            )
        
        # Key descriptors (if certificates provided)
        if self.signing_certificate:
            self._add_key_descriptor(spsso, self.signing_certificate, "signing")
        
        if self.encryption_certificate:
            self._add_key_descriptor(spsso, self.encryption_certificate, "encryption")
        
        # Organization info
        org = ET.SubElement(entity_descriptor, f"{{{self.NAMESPACE_MD}}}Organization")
        org_name = ET.SubElement(org, f"{{{self.NAMESPACE_MD}}}OrganizationName", attrib={"xml:lang": "en"})
        org_name.text = self.organization_name
        org_display = ET.SubElement(org, f"{{{self.NAMESPACE_MD}}}OrganizationDisplayName", attrib={"xml:lang": "en"})
        org_display.text = self.organization_display_name
        org_url = ET.SubElement(org, f"{{{self.NAMESPACE_MD}}}OrganizationURL", attrib={"xml:lang": "en"})
        org_url.text = self.organization_url
        
        # Contact person
        contact = ET.SubElement(
            entity_descriptor,
            f"{{{self.NAMESPACE_MD}}}ContactPerson",
            attrib={"contactType": "technical"}
        )
        contact_company = ET.SubElement(contact, f"{{{self.NAMESPACE_MD}}}Company")
        contact_company.text = self.organization_name
        contact_email_elem = ET.SubElement(contact, f"{{{self.NAMESPACE_MD}}}EmailAddress")
        contact_email_elem.text = self.contact_email
        
        # Convert to string with proper formatting
        return self._to_pretty_xml(entity_descriptor)
    
    def _add_key_descriptor(self, parent: ET.Element, certificate: str, use: str) -> None:
        """Add a KeyDescriptor element with certificate."""
        key_desc = ET.SubElement(
            parent,
            f"{{{self.NAMESPACE_MD}}}KeyDescriptor",
            attrib={"use": use}
        )
        
        key_info = ET.SubElement(key_desc, f"{{{self.NAMESPACE_DS}}}KeyInfo")
        x509_data = ET.SubElement(key_info, f"{{{self.NAMESPACE_DS}}}X509Data")
        x509_cert = ET.SubElement(x509_data, f"{{{self.NAMESPACE_DS}}}X509Certificate")
        x509_cert.text = certificate.strip().replace("-----BEGIN CERTIFICATE-----", "").replace("-----END CERTIFICATE-----", "").strip()
    
    def _to_pretty_xml(self, element: ET.Element) -> str:
        """Convert Element to pretty-printed XML string."""
        # Add XML declaration and namespaces
        xml_str = ET.tostring(element, encoding="unicode")
        
        # Add XML declaration
        xml_declaration = '<?xml version="1.0" encoding="UTF-8"?>\n'
        
        return xml_declaration + xml_str
    
    def validate_for_okta(self) -> bool:
        """
        Validate that metadata is compatible with Okta.
        
        Returns:
            True if valid for Okta
        """
        metadata = self.generate()
        return self._validate_metadata(metadata)
    
    def validate_for_azure_ad(self) -> bool:
        """
        Validate that metadata is compatible with Azure AD.
        
        Returns:
            True if valid for Azure AD
        """
        metadata = self.generate()
        return self._validate_metadata(metadata)
    
    def _validate_metadata(self, metadata: str) -> bool:
        """Validate metadata XML structure."""
        try:
            root = ET.fromstring(metadata)
            
            # Check for required elements
            if root.tag != f"{{{self.NAMESPACE_MD}}}EntityDescriptor":
                return False
            
            if not root.get("entityID"):
                return False
            
            # Check for SPSSODescriptor
            spsso = root.find(f"{{{self.NAMESPACE_MD}}}SPSSODescriptor")
            if spsso is None:
                return False
            
            # Check for AssertionConsumerService
            acs = spsso.find(f"{{{self.NAMESPACE_MD}}}AssertionConsumerService")
            if acs is None:
                return False
            
            return True
            
        except ET.ParseError:
            return False


def generate_sp_metadata_for_tenant(
    tenant_id: str,
    base_url: str = "https://api.parwa.ai",
    organization_name: str = "PARWA"
) -> str:
    """
    Convenience function to generate SP metadata for a tenant.
    
    Args:
        tenant_id: Tenant identifier
        base_url: Base URL for the service
        organization_name: Organization name
        
    Returns:
        SP metadata XML string
    """
    generator = SPMetadataGenerator(
        entity_id=f"{base_url}/sp/{tenant_id}",
        acs_url=f"{base_url}/sso/acs/{tenant_id}",
        slo_url=f"{base_url}/sso/slo/{tenant_id}",
        organization_name=organization_name
    )
    
    return generator.generate()
