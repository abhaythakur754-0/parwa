"""
IP Allowlist Module for Enterprise Security.

This module provides IP-based access control for enterprise tenants,
allowing administrators to restrict access to specific IP addresses
or CIDR ranges.
"""

import ipaddress
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, Union
from functools import lru_cache

from pydantic import BaseModel, Field


class IPAllowlistConfig(BaseModel):
    """Configuration for IP allowlist."""
    
    tenant_id: str
    enabled: bool = False
    allowed_ips: List[str] = Field(default_factory=list)
    allowed_cidrs: List[str] = Field(default_factory=list)
    bypass_tokens: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    def is_ip_allowed(self, ip_address: str) -> bool:
        """
        Check if an IP address is allowed.
        
        Args:
            ip_address: IP address to check
            
        Returns:
            True if allowed, False otherwise
        """
        if not self.enabled:
            return True
        
        # Check direct IP match
        if ip_address in self.allowed_ips:
            return True
        
        # Check CIDR ranges
        try:
            ip = ipaddress.ip_address(ip_address)
            for cidr in self.allowed_cidrs:
                try:
                    network = ipaddress.ip_network(cidr, strict=False)
                    if ip in network:
                        return True
                except ValueError:
                    continue
        except ValueError:
            return False
        
        return False
    
    def is_bypass_token_valid(self, token: str) -> bool:
        """
        Check if a bypass token is valid.
        
        Args:
            token: Bypass token to check
            
        Returns:
            True if valid, False otherwise
        """
        return token in self.bypass_tokens


class IPAllowlistService:
    """
    Service for managing IP allowlists.
    
    Provides IP-based access control for enterprise tenants.
    """
    
    def __init__(self):
        """Initialize IP allowlist service."""
        self._configs: Dict[str, IPAllowlistConfig] = {}
        self._access_log: Dict[str, List[Dict]] = {}
    
    def create_config(
        self,
        tenant_id: str,
        allowed_ips: Optional[List[str]] = None,
        allowed_cidrs: Optional[List[str]] = None,
        enabled: bool = True
    ) -> IPAllowlistConfig:
        """
        Create IP allowlist configuration for a tenant.
        
        Args:
            tenant_id: Tenant identifier
            allowed_ips: List of allowed IP addresses
            allowed_cidrs: List of allowed CIDR ranges
            enabled: Whether the allowlist is enabled
            
        Returns:
            Created IPAllowlistConfig
        """
        config = IPAllowlistConfig(
            tenant_id=tenant_id,
            enabled=enabled,
            allowed_ips=allowed_ips or [],
            allowed_cidrs=allowed_cidrs or []
        )
        
        self._configs[tenant_id] = config
        return config
    
    def get_config(self, tenant_id: str) -> Optional[IPAllowlistConfig]:
        """
        Get IP allowlist configuration for a tenant.
        
        Args:
            tenant_id: Tenant identifier
            
        Returns:
            IPAllowlistConfig or None
        """
        return self._configs.get(tenant_id)
    
    def update_config(
        self,
        tenant_id: str,
        allowed_ips: Optional[List[str]] = None,
        allowed_cidrs: Optional[List[str]] = None,
        enabled: Optional[bool] = None
    ) -> Optional[IPAllowlistConfig]:
        """
        Update IP allowlist configuration.
        
        Args:
            tenant_id: Tenant identifier
            allowed_ips: New list of allowed IPs
            allowed_cidrs: New list of allowed CIDRs
            enabled: New enabled status
            
        Returns:
            Updated IPAllowlistConfig or None
        """
        config = self._configs.get(tenant_id)
        if not config:
            return None
        
        if allowed_ips is not None:
            config.allowed_ips = allowed_ips
        if allowed_cidrs is not None:
            config.allowed_cidrs = allowed_cidrs
        if enabled is not None:
            config.enabled = enabled
        
        config.updated_at = datetime.now(timezone.utc)
        
        return config
    
    def add_allowed_ip(self, tenant_id: str, ip_address: str) -> bool:
        """
        Add an IP address to the allowlist.
        
        Args:
            tenant_id: Tenant identifier
            ip_address: IP address to add
            
        Returns:
            True if added, False if already exists or invalid
        """
        config = self._configs.get(tenant_id)
        if not config:
            return False
        
        # Validate IP
        try:
            ipaddress.ip_address(ip_address)
        except ValueError:
            return False
        
        if ip_address not in config.allowed_ips:
            config.allowed_ips.append(ip_address)
            config.updated_at = datetime.now(timezone.utc)
        
        return True
    
    def remove_allowed_ip(self, tenant_id: str, ip_address: str) -> bool:
        """
        Remove an IP address from the allowlist.
        
        Args:
            tenant_id: Tenant identifier
            ip_address: IP address to remove
            
        Returns:
            True if removed, False if not found
        """
        config = self._configs.get(tenant_id)
        if not config:
            return False
        
        if ip_address in config.allowed_ips:
            config.allowed_ips.remove(ip_address)
            config.updated_at = datetime.now(timezone.utc)
            return True
        
        return False
    
    def add_allowed_cidr(self, tenant_id: str, cidr: str) -> bool:
        """
        Add a CIDR range to the allowlist.
        
        Args:
            tenant_id: Tenant identifier
            cidr: CIDR range to add
            
        Returns:
            True if added, False if invalid
        """
        config = self._configs.get(tenant_id)
        if not config:
            return False
        
        # Validate CIDR
        try:
            ipaddress.ip_network(cidr, strict=False)
        except ValueError:
            return False
        
        if cidr not in config.allowed_cidrs:
            config.allowed_cidrs.append(cidr)
            config.updated_at = datetime.now(timezone.utc)
        
        return True
    
    def add_bypass_token(self, tenant_id: str, token: str) -> bool:
        """
        Add a bypass token for temporary access.
        
        Args:
            tenant_id: Tenant identifier
            token: Bypass token
            
        Returns:
            True if added
        """
        config = self._configs.get(tenant_id)
        if not config:
            return False
        
        if token not in config.bypass_tokens:
            config.bypass_tokens.append(token)
            config.updated_at = datetime.now(timezone.utc)
        
        return True
    
    def remove_bypass_token(self, tenant_id: str, token: str) -> bool:
        """
        Remove a bypass token.
        
        Args:
            tenant_id: Tenant identifier
            token: Bypass token to remove
            
        Returns:
            True if removed
        """
        config = self._configs.get(tenant_id)
        if not config:
            return False
        
        if token in config.bypass_tokens:
            config.bypass_tokens.remove(token)
            config.updated_at = datetime.now(timezone.utc)
            return True
        
        return False
    
    def check_access(
        self,
        tenant_id: str,
        ip_address: str,
        bypass_token: Optional[str] = None
    ) -> Dict[str, any]:
        """
        Check if an IP address is allowed access.
        
        Args:
            tenant_id: Tenant identifier
            ip_address: IP address to check
            bypass_token: Optional bypass token
            
        Returns:
            Dictionary with access result
        """
        config = self._configs.get(tenant_id)
        
        result = {
            "allowed": True,
            "reason": "no_restrictions",
            "tenant_id": tenant_id,
            "ip_address": ip_address,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        if not config:
            return result
        
        if not config.enabled:
            result["reason"] = "allowlist_disabled"
            return result
        
        # Check bypass token first
        if bypass_token and config.is_bypass_token_valid(bypass_token):
            result["allowed"] = True
            result["reason"] = "bypass_token_valid"
            return result
        
        # Check IP allowlist
        if config.is_ip_allowed(ip_address):
            result["allowed"] = True
            result["reason"] = "ip_in_allowlist"
        else:
            result["allowed"] = False
            result["reason"] = "ip_not_in_allowlist"
        
        # Log access attempt
        self._log_access(tenant_id, ip_address, result["allowed"])
        
        return result
    
    def _log_access(self, tenant_id: str, ip_address: str, allowed: bool) -> None:
        """Log access attempt."""
        if tenant_id not in self._access_log:
            self._access_log[tenant_id] = []
        
        self._access_log[tenant_id].append({
            "ip_address": ip_address,
            "allowed": allowed,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
        # Keep only last 1000 entries
        if len(self._access_log[tenant_id]) > 1000:
            self._access_log[tenant_id] = self._access_log[tenant_id][-1000:]
    
    def get_access_log(
        self,
        tenant_id: str,
        limit: int = 100
    ) -> List[Dict]:
        """
        Get access log for a tenant.
        
        Args:
            tenant_id: Tenant identifier
            limit: Maximum number of entries
            
        Returns:
            List of access log entries
        """
        log = self._access_log.get(tenant_id, [])
        return log[-limit:]


# Global service instance
_ip_allowlist_service: Optional[IPAllowlistService] = None


def get_ip_allowlist_service() -> IPAllowlistService:
    """Get the IP allowlist service instance."""
    global _ip_allowlist_service
    if _ip_allowlist_service is None:
        _ip_allowlist_service = IPAllowlistService()
    return _ip_allowlist_service
