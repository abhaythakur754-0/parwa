"""
Enterprise Security - Intrusion Prevention
Intrusion prevention system for enterprise
"""
from typing import Dict, Any, List, Optional, Set
from datetime import datetime, timedelta
from pydantic import BaseModel, Field, ConfigDict
from enum import Enum


class BlockReason(str, Enum):
    BRUTE_FORCE = "brute_force"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    MALWARE_SIGNATURE = "malware_signature"
    BLACKLISTED_IP = "blacklisted_ip"
    RATE_LIMIT = "rate_limit"
    MANUAL = "manual"


class BlockAction(BaseModel):
    """Block action record"""
    ip_address: str
    reason: BlockReason
    blocked_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    client_id: Optional[str] = None
    notes: Optional[str] = None

    model_config = ConfigDict()


class IntrusionPrevention:
    """
    Intrusion prevention system for enterprise clients.
    """

    DEFAULT_BLOCK_DURATION = timedelta(hours=24)

    def __init__(self):
        self.blocked_ips: Dict[str, BlockAction] = {}
        self.blacklist: Set[str] = set()
        self.whitelist: Set[str] = set()
        self.rate_limits: Dict[str, List[datetime]] = {}

    def block_ip(
        self,
        ip_address: str,
        reason: BlockReason,
        duration_hours: int = 24,
        client_id: Optional[str] = None,
        notes: Optional[str] = None
    ) -> BlockAction:
        """Block an IP address"""
        action = BlockAction(
            ip_address=ip_address,
            reason=reason,
            expires_at=datetime.utcnow() + timedelta(hours=duration_hours),
            client_id=client_id,
            notes=notes
        )
        self.blocked_ips[ip_address] = action
        return action

    def unblock_ip(self, ip_address: str) -> bool:
        """Unblock an IP address"""
        if ip_address in self.blocked_ips:
            del self.blocked_ips[ip_address]
            return True
        return False

    def is_blocked(self, ip_address: str) -> bool:
        """Check if an IP is blocked"""
        if ip_address in self.whitelist:
            return False

        if ip_address in self.blacklist:
            return True

        if ip_address in self.blocked_ips:
            block = self.blocked_ips[ip_address]
            if block.expires_at and datetime.utcnow() > block.expires_at:
                del self.blocked_ips[ip_address]
                return False
            return True

        return False

    def add_to_blacklist(self, ip_address: str) -> None:
        """Permanently blacklist an IP"""
        self.blacklist.add(ip_address)

    def remove_from_blacklist(self, ip_address: str) -> bool:
        """Remove IP from blacklist"""
        if ip_address in self.blacklist:
            self.blacklist.remove(ip_address)
            return True
        return False

    def add_to_whitelist(self, ip_address: str) -> None:
        """Whitelist an IP (never block)"""
        self.whitelist.add(ip_address)

    def remove_from_whitelist(self, ip_address: str) -> bool:
        """Remove IP from whitelist"""
        if ip_address in self.whitelist:
            self.whitelist.remove(ip_address)
            return True
        return False

    def check_rate_limit(
        self,
        ip_address: str,
        max_requests: int = 100,
        window_seconds: int = 60
    ) -> bool:
        """Check if IP exceeds rate limit"""
        now = datetime.utcnow()
        window_start = now - timedelta(seconds=window_seconds)

        if ip_address not in self.rate_limits:
            self.rate_limits[ip_address] = []

        # Clean old requests
        self.rate_limits[ip_address] = [
            t for t in self.rate_limits[ip_address]
            if t > window_start
        ]

        # Add current request
        self.rate_limits[ip_address].append(now)

        # Check limit
        return len(self.rate_limits[ip_address]) <= max_requests

    def get_blocked_ips(self) -> List[BlockAction]:
        """Get all currently blocked IPs"""
        now = datetime.utcnow()
        active = []
        for ip, action in self.blocked_ips.items():
            if action.expires_at is None or action.expires_at > now:
                active.append(action)
        return active

    def get_block_reason(self, ip_address: str) -> Optional[BlockReason]:
        """Get block reason for an IP"""
        if ip_address in self.blocked_ips:
            return self.blocked_ips[ip_address].reason
        if ip_address in self.blacklist:
            return BlockReason.BLACKLISTED_IP
        return None
