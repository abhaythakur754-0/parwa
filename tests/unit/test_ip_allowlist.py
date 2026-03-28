"""
Unit Tests for IP Allowlist Module.

Tests for IP-based access control including:
- IP address validation
- CIDR range matching
- Bypass token support
- Access logging
"""

import pytest
from datetime import datetime, timezone

from backend.security.ip_allowlist import (
    IPAllowlistConfig,
    IPAllowlistService,
    get_ip_allowlist_service
)


class TestIPAllowlistConfig:
    """Tests for IPAllowlistConfig."""
    
    def test_config_creation(self):
        """Test creating an IP allowlist config."""
        config = IPAllowlistConfig(
            tenant_id="tenant-123",
            enabled=True,
            allowed_ips=["192.168.1.1", "10.0.0.1"]
        )
        
        assert config.tenant_id == "tenant-123"
        assert config.enabled is True
        assert len(config.allowed_ips) == 2
    
    def test_is_ip_allowed_direct_match(self):
        """Test IP allowed with direct match - CRITICAL TEST."""
        config = IPAllowlistConfig(
            tenant_id="tenant-123",
            enabled=True,
            allowed_ips=["192.168.1.1", "10.0.0.1"]
        )
        
        # Allowed IP
        assert config.is_ip_allowed("192.168.1.1") is True
        assert config.is_ip_allowed("10.0.0.1") is True
        
        # Non-allowed IP
        assert config.is_ip_allowed("192.168.1.2") is False
    
    def test_is_ip_allowed_cidr(self):
        """Test IP allowed with CIDR range."""
        config = IPAllowlistConfig(
            tenant_id="tenant-123",
            enabled=True,
            allowed_cidrs=["192.168.1.0/24", "10.0.0.0/8"]
        )
        
        # IPs in CIDR range
        assert config.is_ip_allowed("192.168.1.100") is True
        assert config.is_ip_allowed("192.168.1.255") is True
        assert config.is_ip_allowed("10.5.5.5") is True
        
        # IP outside CIDR range
        assert config.is_ip_allowed("192.168.2.1") is False
        assert config.is_ip_allowed("172.16.0.1") is False
    
    def test_disabled_allowlist(self):
        """Test that disabled allowlist allows all IPs."""
        config = IPAllowlistConfig(
            tenant_id="tenant-123",
            enabled=False,
            allowed_ips=["192.168.1.1"]
        )
        
        # All IPs should be allowed when disabled
        assert config.is_ip_allowed("192.168.1.1") is True
        assert config.is_ip_allowed("8.8.8.8") is True
        assert config.is_ip_allowed("1.2.3.4") is True
    
    def test_bypass_token(self):
        """Test bypass token validation."""
        config = IPAllowlistConfig(
            tenant_id="tenant-123",
            enabled=True,
            allowed_ips=["192.168.1.1"],
            bypass_tokens=["secret-token-123"]
        )
        
        assert config.is_bypass_token_valid("secret-token-123") is True
        assert config.is_bypass_token_valid("invalid-token") is False
    
    def test_invalid_ip_address(self):
        """Test handling of invalid IP addresses."""
        config = IPAllowlistConfig(
            tenant_id="tenant-123",
            enabled=True,
            allowed_ips=["192.168.1.1"]
        )
        
        assert config.is_ip_allowed("invalid-ip") is False
        assert config.is_ip_allowed("256.256.256.256") is False


class TestIPAllowlistService:
    """Tests for IPAllowlistService."""
    
    def test_create_config(self):
        """Test creating allowlist config for tenant."""
        service = IPAllowlistService()
        
        config = service.create_config(
            tenant_id="tenant-123",
            allowed_ips=["192.168.1.1"],
            enabled=True
        )
        
        assert config is not None
        assert config.tenant_id == "tenant-123"
        assert "192.168.1.1" in config.allowed_ips
    
    def test_check_access_allowed(self):
        """Test access check for allowed IP."""
        service = IPAllowlistService()
        service.create_config(
            tenant_id="tenant-123",
            allowed_ips=["192.168.1.1"],
            enabled=True
        )
        
        result = service.check_access("tenant-123", "192.168.1.1")
        
        assert result["allowed"] is True
        assert result["reason"] == "ip_in_allowlist"
    
    def test_check_access_blocked(self):
        """Test access check for non-allowed IP - CRITICAL TEST."""
        service = IPAllowlistService()
        service.create_config(
            tenant_id="tenant-123",
            allowed_ips=["192.168.1.1"],
            enabled=True
        )
        
        result = service.check_access("tenant-123", "8.8.8.8")
        
        # Non-whitelisted IP should be blocked
        assert result["allowed"] is False
        assert result["reason"] == "ip_not_in_allowlist"
    
    def test_check_access_bypass_token(self):
        """Test access with bypass token."""
        service = IPAllowlistService()
        service.create_config(
            tenant_id="tenant-123",
            allowed_ips=["192.168.1.1"],
            enabled=True
        )
        service.add_bypass_token("tenant-123", "secret-token")
        
        # Non-allowed IP with valid bypass token
        result = service.check_access("tenant-123", "8.8.8.8", "secret-token")
        
        assert result["allowed"] is True
        assert result["reason"] == "bypass_token_valid"
    
    def test_add_remove_ip(self):
        """Test adding and removing IPs."""
        service = IPAllowlistService()
        service.create_config(tenant_id="tenant-123")
        
        # Add IP
        assert service.add_allowed_ip("tenant-123", "10.0.0.1") is True
        config = service.get_config("tenant-123")
        assert "10.0.0.1" in config.allowed_ips
        
        # Remove IP
        assert service.remove_allowed_ip("tenant-123", "10.0.0.1") is True
        config = service.get_config("tenant-123")
        assert "10.0.0.1" not in config.allowed_ips
    
    def test_add_cidr(self):
        """Test adding CIDR ranges."""
        service = IPAllowlistService()
        service.create_config(tenant_id="tenant-123")
        
        # Add valid CIDR
        assert service.add_allowed_cidr("tenant-123", "10.0.0.0/24") is True
        
        # Add invalid CIDR
        assert service.add_allowed_cidr("tenant-123", "invalid-cidr") is False
    
    def test_access_logging(self):
        """Test access logging."""
        service = IPAllowlistService()
        service.create_config(
            tenant_id="tenant-123",
            allowed_ips=["192.168.1.1"],
            enabled=True
        )
        
        # Make some access attempts
        service.check_access("tenant-123", "192.168.1.1")
        service.check_access("tenant-123", "8.8.8.8")
        
        log = service.get_access_log("tenant-123")
        
        assert len(log) == 2
        assert log[0]["allowed"] is True
        assert log[1]["allowed"] is False
    
    def test_get_ip_allowlist_service(self):
        """Test factory function."""
        service = get_ip_allowlist_service()
        
        assert service is not None
        assert isinstance(service, IPAllowlistService)


class TestIPv6Support:
    """Tests for IPv6 support."""
    
    def test_ipv6_direct_match(self):
        """Test IPv6 address matching."""
        config = IPAllowlistConfig(
            tenant_id="tenant-123",
            enabled=True,
            allowed_ips=["::1", "2001:db8::1"]
        )
        
        assert config.is_ip_allowed("::1") is True
        assert config.is_ip_allowed("2001:db8::1") is True
        assert config.is_ip_allowed("2001:db8::2") is False
    
    def test_ipv6_cidr(self):
        """Test IPv6 CIDR range matching."""
        config = IPAllowlistConfig(
            tenant_id="tenant-123",
            enabled=True,
            allowed_cidrs=["2001:db8::/32"]
        )
        
        assert config.is_ip_allowed("2001:db8::1") is True
        assert config.is_ip_allowed("2001:db8:ffff::1") is True
        assert config.is_ip_allowed("2001:db9::1") is False
