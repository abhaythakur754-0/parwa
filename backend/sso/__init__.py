"""
SSO (Single Sign-On) Module for Enterprise Clients.

This module provides SAML 2.0 SSO integration and SCIM provisioning
for enterprise clients.
"""

from backend.sso.sso_provider import SSOProvider
from backend.sso.sp_metadata import SPMetadataGenerator
from backend.sso.scim_stub import SCIMStub

__all__ = ["SSOProvider", "SPMetadataGenerator", "SCIMStub"]
