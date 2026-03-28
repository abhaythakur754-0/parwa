"""
SCIM 2.0 Stub Implementation for Enterprise User Provisioning.

This module provides SCIM (System for Cross-domain Identity Management)
stub functionality for enterprise user provisioning from identity providers.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, EmailStr, Field


class SCIMUser(BaseModel):
    """SCIM User model."""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    external_id: Optional[str] = None
    user_name: str
    name: Dict[str, str] = Field(default_factory=dict)
    display_name: Optional[str] = None
    emails: List[Dict[str, str]] = Field(default_factory=list)
    active: bool = True
    title: Optional[str] = None
    locale: str = "en-US"
    timezone: str = "UTC"
    meta: Dict[str, str] = Field(default_factory=dict)
    
    def to_scim_response(self) -> Dict[str, Any]:
        """Convert to SCIM response format."""
        return {
            "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
            "id": self.id,
            "externalId": self.external_id,
            "userName": self.user_name,
            "name": self.name,
            "displayName": self.display_name,
            "emails": self.emails,
            "active": self.active,
            "title": self.title,
            "locale": self.locale,
            "timezone": self.timezone,
            "meta": {
                "resourceType": "User",
                "created": datetime.now(timezone.utc).isoformat(),
                "lastModified": datetime.now(timezone.utc).isoformat(),
                "location": f"/scim/v2/Users/{self.id}"
            }
        }


class SCIMGroup(BaseModel):
    """SCIM Group model."""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    display_name: str
    members: List[Dict[str, str]] = Field(default_factory=list)
    meta: Dict[str, str] = Field(default_factory=dict)
    
    def to_scim_response(self) -> Dict[str, Any]:
        """Convert to SCIM response format."""
        return {
            "schemas": ["urn:ietf:params:scim:schemas:core:2.0:Group"],
            "id": self.id,
            "displayName": self.display_name,
            "members": self.members,
            "meta": {
                "resourceType": "Group",
                "created": datetime.now(timezone.utc).isoformat(),
                "lastModified": datetime.now(timezone.utc).isoformat(),
                "location": f"/scim/v2/Groups/{self.id}"
            }
        }


class SCIMStub:
    """
    SCIM 2.0 stub for user provisioning.
    
    Provides stub implementation of SCIM endpoints for testing
    enterprise provisioning from identity providers like Okta, Azure AD.
    """
    
    def __init__(self, tenant_id: str):
        """
        Initialize SCIM stub.
        
        Args:
            tenant_id: Tenant identifier for provisioning
        """
        self.tenant_id = tenant_id
        self._users: Dict[str, SCIMUser] = {}
        self._groups: Dict[str, SCIMGroup] = {}
        self._user_name_index: Dict[str, str] = {}
    
    # ==================== User Operations ====================
    
    def create_user(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new SCIM user.
        
        Args:
            user_data: SCIM user data from IdP
            
        Returns:
            Created user in SCIM format
        """
        user = SCIMUser(
            external_id=user_data.get("externalId"),
            user_name=user_data.get("userName", ""),
            name=user_data.get("name", {}),
            display_name=user_data.get("displayName"),
            emails=user_data.get("emails", []),
            active=user_data.get("active", True),
            title=user_data.get("title"),
            locale=user_data.get("locale", "en-US"),
            timezone=user_data.get("timezone", "UTC")
        )
        
        self._users[user.id] = user
        self._user_name_index[user.user_name] = user.id
        
        return user.to_scim_response()
    
    def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a user by ID.
        
        Args:
            user_id: User identifier
            
        Returns:
            User in SCIM format or None
        """
        user = self._users.get(user_id)
        return user.to_scim_response() if user else None
    
    def get_user_by_username(self, user_name: str) -> Optional[Dict[str, Any]]:
        """
        Get a user by username.
        
        Args:
            user_name: Username to search for
            
        Returns:
            User in SCIM format or None
        """
        user_id = self._user_name_index.get(user_name)
        if user_id:
            return self.get_user(user_id)
        return None
    
    def update_user(self, user_id: str, user_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Update a user.
        
        Args:
            user_id: User identifier
            user_data: Updated user data
            
        Returns:
            Updated user in SCIM format or None
        """
        user = self._users.get(user_id)
        if not user:
            return None
        
        # Update fields
        if "externalId" in user_data:
            user.external_id = user_data["externalId"]
        if "name" in user_data:
            user.name.update(user_data["name"])
        if "displayName" in user_data:
            user.display_name = user_data["displayName"]
        if "emails" in user_data:
            user.emails = user_data["emails"]
        if "active" in user_data:
            user.active = user_data["active"]
        if "title" in user_data:
            user.title = user_data["title"]
        if "locale" in user_data:
            user.locale = user_data["locale"]
        if "timezone" in user_data:
            user.timezone = user_data["timezone"]
        
        return user.to_scim_response()
    
    def delete_user(self, user_id: str) -> bool:
        """
        Delete a user (deprovision).
        
        Args:
            user_id: User identifier
            
        Returns:
            True if deleted, False if not found
        """
        user = self._users.get(user_id)
        if not user:
            return False
        
        # Remove from indices
        del self._users[user_id]
        if user.user_name in self._user_name_index:
            del self._user_name_index[user.user_name]
        
        return True
    
    def list_users(
        self,
        start_index: int = 1,
        count: int = 100,
        filter_str: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        List users with pagination.
        
        Args:
            start_index: Starting index (1-based)
            count: Maximum number of results
            filter_str: SCIM filter string (stub - not fully implemented)
            
        Returns:
            SCIM list response
        """
        users = list(self._users.values())
        
        # Apply pagination
        total = len(users)
        paginated = users[start_index - 1:start_index - 1 + count]
        
        return {
            "schemas": ["urn:ietf:params:scim:api:messages:2.0:ListResponse"],
            "totalResults": total,
            "startIndex": start_index,
            "itemsPerPage": len(paginated),
            "Resources": [u.to_scim_response() for u in paginated]
        }
    
    # ==================== Group Operations ====================
    
    def create_group(self, group_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new SCIM group.
        
        Args:
            group_data: SCIM group data from IdP
            
        Returns:
            Created group in SCIM format
        """
        group = SCIMGroup(
            display_name=group_data.get("displayName", ""),
            members=group_data.get("members", [])
        )
        
        self._groups[group.id] = group
        
        return group.to_scim_response()
    
    def get_group(self, group_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a group by ID.
        
        Args:
            group_id: Group identifier
            
        Returns:
            Group in SCIM format or None
        """
        group = self._groups.get(group_id)
        return group.to_scim_response() if group else None
    
    def update_group(self, group_id: str, group_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Update a group.
        
        Args:
            group_id: Group identifier
            group_data: Updated group data
            
        Returns:
            Updated group in SCIM format or None
        """
        group = self._groups.get(group_id)
        if not group:
            return None
        
        if "displayName" in group_data:
            group.display_name = group_data["displayName"]
        if "members" in group_data:
            group.members = group_data["members"]
        
        return group.to_scim_response()
    
    def delete_group(self, group_id: str) -> bool:
        """
        Delete a group.
        
        Args:
            group_id: Group identifier
            
        Returns:
            True if deleted, False if not found
        """
        if group_id in self._groups:
            del self._groups[group_id]
            return True
        return False
    
    def list_groups(
        self,
        start_index: int = 1,
        count: int = 100
    ) -> Dict[str, Any]:
        """
        List groups with pagination.
        
        Args:
            start_index: Starting index (1-based)
            count: Maximum number of results
            
        Returns:
            SCIM list response
        """
        groups = list(self._groups.values())
        
        total = len(groups)
        paginated = groups[start_index - 1:start_index - 1 + count]
        
        return {
            "schemas": ["urn:ietf:params:scim:api:messages:2.0:ListResponse"],
            "totalResults": total,
            "startIndex": start_index,
            "itemsPerPage": len(paginated),
            "Resources": [g.to_scim_response() for g in paginated]
        }
    
    # ==================== Service Provider Config ====================
    
    def get_service_provider_config(self) -> Dict[str, Any]:
        """
        Get SCIM service provider configuration.
        
        Returns:
            ServiceProviderConfig response
        """
        return {
            "schemas": ["urn:ietf:params:scim:schemas:core:2.0:ServiceProviderConfig"],
            "patch": {
                "supported": True
            },
            "bulk": {
                "supported": True,
                "maxOperations": 100,
                "maxPayloadSize": 1048576
            },
            "filter": {
                "supported": True,
                "maxResults": 1000
            },
            "changePassword": {
                "supported": False
            },
            "sort": {
                "supported": True
            },
            "authenticationSchemes": [
                {
                    "name": "OAuth Bearer Token",
                    "description": "Authentication using OAuth Bearer Token",
                    "specUri": "http://www.rfc-editor.org/info/rfc6750",
                    "type": "oauthbearertoken",
                    "primary": True
                }
            ],
            "meta": {
                "location": "/scim/v2/ServiceProviderConfig",
                "resourceType": "ServiceProviderConfig"
            }
        }
    
    def get_resource_types(self) -> Dict[str, Any]:
        """
        Get SCIM resource types.
        
        Returns:
            ResourceTypes response
        """
        return {
            "schemas": ["urn:ietf:params:scim:api:messages:2.0:ListResponse"],
            "totalResults": 2,
            "Resources": [
                {
                    "schemas": ["urn:ietf:params:scim:schemas:core:2.0:ResourceType"],
                    "id": "User",
                    "name": "User",
                    "description": "User Account",
                    "endpoint": "/scim/v2/Users",
                    "schema": "urn:ietf:params:scim:schemas:core:2.0:User",
                    "meta": {
                        "location": "/scim/v2/ResourceTypes/User",
                        "resourceType": "ResourceType"
                    }
                },
                {
                    "schemas": ["urn:ietf:params:scim:schemas:core:2.0:ResourceType"],
                    "id": "Group",
                    "name": "Group",
                    "description": "Group",
                    "endpoint": "/scim/v2/Groups",
                    "schema": "urn:ietf:params:scim:schemas:core:2.0:Group",
                    "meta": {
                        "location": "/scim/v2/ResourceTypes/Group",
                        "resourceType": "ResourceType"
                    }
                }
            ]
        }
    
    def get_schemas(self) -> Dict[str, Any]:
        """
        Get SCIM schemas.
        
        Returns:
            Schemas response
        """
        return {
            "schemas": ["urn:ietf:params:scim:api:messages:2.0:ListResponse"],
            "totalResults": 2,
            "Resources": [
                {
                    "schemas": ["urn:ietf:params:scim:schemas:core:2.0:Schema"],
                    "id": "urn:ietf:params:scim:schemas:core:2.0:User",
                    "name": "User",
                    "description": "User Account",
                    "attributes": [
                        {"name": "userName", "type": "string", "required": True},
                        {"name": "name", "type": "complex", "required": False},
                        {"name": "emails", "type": "complex", "required": False},
                        {"name": "active", "type": "boolean", "required": False}
                    ]
                },
                {
                    "schemas": ["urn:ietf:params:scim:schemas:core:2.0:Schema"],
                    "id": "urn:ietf:params:scim:schemas:core:2.0:Group",
                    "name": "Group",
                    "description": "Group",
                    "attributes": [
                        {"name": "displayName", "type": "string", "required": True},
                        {"name": "members", "type": "complex", "required": False}
                    ]
                }
            ]
        }


def get_scim_stub_for_tenant(tenant_id: str) -> SCIMStub:
    """
    Factory function to get SCIM stub for a tenant.
    
    Args:
        tenant_id: Tenant identifier
        
    Returns:
        SCIMStub instance for the tenant
    """
    return SCIMStub(tenant_id)
