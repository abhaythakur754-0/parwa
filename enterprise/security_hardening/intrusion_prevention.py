"""Intrusion Prevention Module - Week 54, Builder 2"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional
import logging
import threading

logger = logging.getLogger(__name__)


class ActionType(Enum):
    BLOCK = "block"
    RATE_LIMIT = "rate_limit"
    ALERT = "alert"
    LOG = "log"


@dataclass
class BlockEntry:
    ip: str
    reason: str
    blocked_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None

    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at


@dataclass
class PreventionRule:
    name: str
    condition: str
    action: ActionType
    duration_seconds: int = 3600
    enabled: bool = True


@dataclass
class PreventionStats:
    total_blocks: int = 0
    total_alerts: int = 0
    total_rate_limited: int = 0

    def to_dict(self) -> Dict[str, int]:
        return {
            "total_blocks": self.total_blocks,
            "total_alerts": self.total_alerts,
            "total_rate_limited": self.total_rate_limited,
        }


class IntrusionPrevention:
    def __init__(self):
        self.blocked_ips: Dict[str, BlockEntry] = {}
        self.rules: List[PreventionRule] = []
        self.stats = PreventionStats()
        self._lock = threading.Lock()
        self._load_default_rules()

    def _load_default_rules(self):
        self.rules = [
            PreventionRule("block_sql_injection", "sql_injection", ActionType.BLOCK),
            PreventionRule("block_xss", "xss", ActionType.BLOCK),
            PreventionRule("rate_limit_brute_force", "brute_force", ActionType.RATE_LIMIT),
        ]

    def block(self, ip: str, reason: str, duration_seconds: int = 3600) -> None:
        with self._lock:
            expires = datetime.utcnow() + timedelta(seconds=duration_seconds)
            self.blocked_ips[ip] = BlockEntry(ip=ip, reason=reason, expires_at=expires)
            self.stats.total_blocks += 1
            logger.warning(f"Blocked IP {ip}: {reason}")

    def unblock(self, ip: str) -> bool:
        with self._lock:
            if ip in self.blocked_ips:
                del self.blocked_ips[ip]
                return True
            return False

    def is_blocked(self, ip: str) -> bool:
        with self._lock:
            entry = self.blocked_ips.get(ip)
            if entry is None:
                return False
            if entry.is_expired:
                del self.blocked_ips[ip]
                return False
            return True

    def add_rule(self, rule: PreventionRule) -> None:
        with self._lock:
            self.rules.append(rule)

    def remove_rule(self, name: str) -> bool:
        with self._lock:
            for i, r in enumerate(self.rules):
                if r.name == name:
                    del self.rules[i]
                    return True
            return False

    def evaluate(self, ip: str, threat_type: str) -> Optional[ActionType]:
        if self.is_blocked(ip):
            return ActionType.BLOCK

        for rule in self.rules:
            if not rule.enabled:
                continue
            if rule.condition == threat_type:
                if rule.action == ActionType.BLOCK:
                    self.block(ip, f"Rule: {rule.name}", rule.duration_seconds)
                elif rule.action == ActionType.ALERT:
                    self.stats.total_alerts += 1
                elif rule.action == ActionType.RATE_LIMIT:
                    self.stats.total_rate_limited += 1
                return rule.action
        return None

    def get_blocked_ips(self) -> List[BlockEntry]:
        with self._lock:
            return [e for e in self.blocked_ips.values() if not e.is_expired]

    def get_stats(self) -> PreventionStats:
        return self.stats

    def clear_expired(self) -> int:
        with self._lock:
            expired = [ip for ip, e in self.blocked_ips.items() if e.is_expired]
            for ip in expired:
                del self.blocked_ips[ip]
            return len(expired)
