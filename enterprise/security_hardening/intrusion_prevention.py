"""
Enterprise Security Hardening - Intrusion Prevention
Intrusion prevention system with IP blocking, rules, and actions
"""
from typing import Dict, Any, List, Optional, Set, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import uuid
import threading
from collections import defaultdict


class ActionType(str, Enum):
    """Types of prevention actions"""
    BLOCK = "block"
    RATE_LIMIT = "rate_limit"
    ALERT = "alert"
    LOG = "log"
    CHALLENGE = "challenge"
    REDIRECT = "redirect"
    QUARANTINE = "quarantine"
    TERMINATE = "terminate"


class BlockReason(str, Enum):
    """Reasons for blocking"""
    BRUTE_FORCE = "brute_force"
    DDOS = "ddos"
    SQL_INJECTION = "sql_injection"
    XSS = "xss"
    MALWARE = "malware"
    PHISHING = "phishing"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    BLACKLISTED = "blacklisted"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    MANUAL = "manual"
    POLICY_VIOLATION = "policy_violation"
    AUTOMATED_ATTACK = "automated_attack"


class RulePriority(str, Enum):
    """Rule priority levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IPBlockStatus(str, Enum):
    """IP block status"""
    ACTIVE = "active"
    EXPIRED = "expired"
    REMOVED = "removed"
    TEMPORARY = "temporary"


@dataclass
class IPBlock:
    """IP block record"""
    block_id: str = field(default_factory=lambda: f"block_{uuid.uuid4().hex[:12]}")
    ip_address: str = ""
    reason: BlockReason = BlockReason.SUSPICIOUS_ACTIVITY
    status: IPBlockStatus = IPBlockStatus.ACTIVE
    blocked_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    blocked_by: str = "system"
    source: str = ""
    notes: str = ""
    attempt_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_expired(self) -> bool:
        """Check if block has expired"""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at

    def time_remaining(self) -> Optional[timedelta]:
        """Get time remaining until expiration"""
        if self.expires_at is None:
            return None
        remaining = self.expires_at - datetime.utcnow()
        return remaining if remaining.total_seconds() > 0 else timedelta(0)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "block_id": self.block_id,
            "ip_address": self.ip_address,
            "reason": self.reason.value,
            "status": self.status.value,
            "blocked_at": self.blocked_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "blocked_by": self.blocked_by,
            "source": self.source,
            "notes": self.notes,
            "attempt_count": self.attempt_count
        }


@dataclass
class PreventionRule:
    """Prevention rule definition"""
    rule_id: str = field(default_factory=lambda: f"rule_{uuid.uuid4().hex[:8]}")
    name: str = ""
    description: str = ""
    action: ActionType = ActionType.LOG
    priority: RulePriority = RulePriority.MEDIUM
    conditions: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    created_by: str = "system"
    hit_count: int = 0
    last_hit: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def matches(self, context: Dict[str, Any]) -> bool:
        """Check if context matches rule conditions"""
        if not self.enabled:
            return False
        
        for key, expected in self.conditions.items():
            actual = context.get(key)
            
            if isinstance(expected, dict):
                # Handle operator-based conditions
                if "$eq" in expected and actual != expected["$eq"]:
                    return False
                if "$ne" in expected and actual == expected["$ne"]:
                    return False
                if "$gt" in expected and not (actual and actual > expected["$gt"]):
                    return False
                if "$lt" in expected and not (actual and actual < expected["$lt"]):
                    return False
                if "$in" in expected and actual not in expected["$in"]:
                    return False
                if "$contains" in expected and not (actual and expected["$contains"] in str(actual)):
                    return False
            else:
                # Simple equality check
                if actual != expected:
                    return False
        
        return True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "rule_id": self.rule_id,
            "name": self.name,
            "description": self.description,
            "action": self.action.value,
            "priority": self.priority.value,
            "conditions": self.conditions,
            "enabled": self.enabled,
            "hit_count": self.hit_count,
            "last_hit": self.last_hit.isoformat() if self.last_hit else None
        }


@dataclass
class PreventionLog:
    """Log entry for prevention actions"""
    log_id: str = field(default_factory=lambda: f"log_{uuid.uuid4().hex[:12]}")
    timestamp: datetime = field(default_factory=datetime.utcnow)
    action: ActionType = ActionType.LOG
    source_ip: Optional[str] = None
    user_id: Optional[str] = None
    rule_id: Optional[str] = None
    block_id: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "log_id": self.log_id,
            "timestamp": self.timestamp.isoformat(),
            "action": self.action.value,
            "source_ip": self.source_ip,
            "user_id": self.user_id,
            "rule_id": self.rule_id,
            "block_id": self.block_id,
            "details": self.details
        }


class IntrusionPrevention:
    """
    Intrusion Prevention System with IP blocking,
    rule-based prevention, and comprehensive logging.
    """

    DEFAULT_BLOCK_DURATION_HOURS = 24
    MAX_LOG_ENTRIES = 10000

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._lock = threading.RLock()
        
        # IP management
        self._blocked_ips: Dict[str, IPBlock] = {}
        self._blacklist: Set[str] = set()
        self._whitelist: Set[str] = set()
        
        # Rules
        self._rules: Dict[str, PreventionRule] = {}
        
        # Rate limiting
        self._rate_limits: Dict[str, List[datetime]] = defaultdict(list)
        self._rate_limit_configs: Dict[str, Dict[str, int]] = {}
        
        # Logging and stats
        self._logs: List[PreventionLog] = []
        self._stats = defaultdict(int)
        
        # Action callbacks
        self._action_handlers: Dict[ActionType, List[Callable]] = defaultdict(list)
        
        # Initialize default rules
        self._init_default_rules()
        self._init_default_rate_limits()

    def _init_default_rules(self) -> None:
        """Initialize default prevention rules"""
        default_rules = [
            PreventionRule(
                rule_id="rule_brute_force",
                name="Block Brute Force",
                description="Block IP after multiple failed login attempts",
                action=ActionType.BLOCK,
                priority=RulePriority.HIGH,
                conditions={"failed_attempts": {"$gt": 5}}
            ),
            PreventionRule(
                rule_id="rule_sql_injection",
                name="Block SQL Injection",
                description="Block requests with SQL injection patterns",
                action=ActionType.BLOCK,
                priority=RulePriority.CRITICAL,
                conditions={"threat_type": "sql_injection"}
            ),
            PreventionRule(
                rule_id="rule_xss",
                name="Block XSS",
                description="Block requests with XSS patterns",
                action=ActionType.BLOCK,
                priority=RulePriority.CRITICAL,
                conditions={"threat_type": "xss"}
            ),
            PreventionRule(
                rule_id="rule_ddos",
                name="Rate Limit DDoS",
                description="Rate limit IPs with high request volume",
                action=ActionType.RATE_LIMIT,
                priority=RulePriority.HIGH,
                conditions={"requests_per_minute": {"$gt": 100}}
            ),
            PreventionRule(
                rule_id="rule_suspicious",
                name="Alert Suspicious Activity",
                description="Alert on suspicious activity patterns",
                action=ActionType.ALERT,
                priority=RulePriority.MEDIUM,
                conditions={"suspicious_score": {"$gt": 0.7}}
            )
        ]
        
        for rule in default_rules:
            self._rules[rule.rule_id] = rule

    def _init_default_rate_limits(self) -> None:
        """Initialize default rate limit configurations"""
        self._rate_limit_configs = {
            "global": {"max_requests": 1000, "window_seconds": 60},
            "api": {"max_requests": 100, "window_seconds": 60},
            "auth": {"max_requests": 10, "window_seconds": 60},
            "search": {"max_requests": 50, "window_seconds": 60}
        }

    def block(
        self,
        ip_address: str,
        reason: BlockReason = BlockReason.SUSPICIOUS_ACTIVITY,
        duration_hours: int = None,
        blocked_by: str = "system",
        source: str = "",
        notes: str = "",
        metadata: Optional[Dict[str, Any]] = None
    ) -> IPBlock:
        """
        Block an IP address.
        """
        # Check whitelist first
        if ip_address in self._whitelist:
            self._log_action(
                ActionType.LOG,
                source_ip=ip_address,
                details={"message": "Cannot block whitelisted IP"}
            )
            return None
        
        duration_hours = duration_hours or self.DEFAULT_BLOCK_DURATION_HOURS
        expires_at = datetime.utcnow() + timedelta(hours=duration_hours) if duration_hours > 0 else None
        
        block = IPBlock(
            ip_address=ip_address,
            reason=reason,
            status=IPBlockStatus.ACTIVE,
            expires_at=expires_at,
            blocked_by=blocked_by,
            source=source,
            notes=notes,
            metadata=metadata or {}
        )
        
        with self._lock:
            self._blocked_ips[ip_address] = block
            self._stats["blocks_created"] += 1
        
        self._log_action(
            ActionType.BLOCK,
            source_ip=ip_address,
            block_id=block.block_id,
            details={"reason": reason.value, "duration_hours": duration_hours}
        )
        
        self._execute_handlers(ActionType.BLOCK, {"block": block})
        
        return block

    def unblock(self, ip_address: str, unblocked_by: str = "system") -> bool:
        """
        Unblock an IP address.
        """
        with self._lock:
            if ip_address in self._blocked_ips:
                self._blocked_ips[ip_address].status = IPBlockStatus.REMOVED
                del self._blocked_ips[ip_address]
                self._stats["blocks_removed"] += 1
                
                self._log_action(
                    ActionType.LOG,
                    source_ip=ip_address,
                    details={"action": "unblocked", "unblocked_by": unblocked_by}
                )
                return True
        
        return False

    def allow(self, ip_address: str) -> bool:
        """
        Add IP to whitelist (always allowed).
        """
        with self._lock:
            # Remove from blocked if present
            if ip_address in self._blocked_ips:
                del self._blocked_ips[ip_address]
            
            self._whitelist.add(ip_address)
            self._stats["whitelist_additions"] += 1
        
        self._log_action(
            ActionType.LOG,
            source_ip=ip_address,
            details={"action": "whitelisted"}
        )
        
        return True

    def disallow(self, ip_address: str) -> bool:
        """
        Remove IP from whitelist.
        """
        with self._lock:
            if ip_address in self._whitelist:
                self._whitelist.remove(ip_address)
                self._stats["whitelist_removals"] += 1
                return True
        return False

    def is_blocked(self, ip_address: str) -> bool:
        """Check if an IP is blocked"""
        # Whitelist always takes precedence
        if ip_address in self._whitelist:
            return False
        
        # Check permanent blacklist
        if ip_address in self._blacklist:
            return True
        
        # Check temporary blocks
        with self._lock:
            if ip_address in self._blocked_ips:
                block = self._blocked_ips[ip_address]
                if block.is_expired():
                    block.status = IPBlockStatus.EXPIRED
                    del self._blocked_ips[ip_address]
                    return False
                return True
        
        return False

    def get_block(self, ip_address: str) -> Optional[IPBlock]:
        """Get block record for an IP"""
        with self._lock:
            block = self._blocked_ips.get(ip_address)
            if block and not block.is_expired():
                return block
        return None

    def add_to_blacklist(self, ip_address: str) -> None:
        """Add IP to permanent blacklist"""
        with self._lock:
            self._blacklist.add(ip_address)
            # Remove from whitelist if present
            self._whitelist.discard(ip_address)
            self._stats["blacklist_additions"] += 1
        
        self._log_action(
            ActionType.BLOCK,
            source_ip=ip_address,
            details={"action": "blacklisted"}
        )

    def remove_from_blacklist(self, ip_address: str) -> bool:
        """Remove IP from blacklist"""
        with self._lock:
            if ip_address in self._blacklist:
                self._blacklist.remove(ip_address)
                self._stats["blacklist_removals"] += 1
                return True
        return False

    def add_rule(
        self,
        name: str,
        action: ActionType,
        conditions: Dict[str, Any],
        priority: RulePriority = RulePriority.MEDIUM,
        description: str = "",
        enabled: bool = True
    ) -> PreventionRule:
        """Add a new prevention rule"""
        rule = PreventionRule(
            name=name,
            description=description,
            action=action,
            priority=priority,
            conditions=conditions,
            enabled=enabled,
            created_by="user"
        )
        
        with self._lock:
            self._rules[rule.rule_id] = rule
            self._stats["rules_added"] += 1
        
        return rule

    def remove_rule(self, rule_id: str) -> bool:
        """Remove a prevention rule"""
        with self._lock:
            if rule_id in self._rules:
                del self._rules[rule_id]
                self._stats["rules_removed"] += 1
                return True
        return False

    def enable_rule(self, rule_id: str) -> bool:
        """Enable a rule"""
        with self._lock:
            if rule_id in self._rules:
                self._rules[rule_id].enabled = True
                return True
        return False

    def disable_rule(self, rule_id: str) -> bool:
        """Disable a rule"""
        with self._lock:
            if rule_id in self._rules:
                self._rules[rule_id].enabled = False
                return True
        return False

    def evaluate_rules(self, context: Dict[str, Any]) -> List[PreventionRule]:
        """
        Evaluate context against all rules.
        Returns list of matching rules sorted by priority.
        """
        matching_rules = []
        
        with self._lock:
            for rule in self._rules.values():
                if rule.matches(context):
                    rule.hit_count += 1
                    rule.last_hit = datetime.utcnow()
                    matching_rules.append(rule)
        
        # Sort by priority
        priority_order = {
            RulePriority.CRITICAL: 0,
            RulePriority.HIGH: 1,
            RulePriority.MEDIUM: 2,
            RulePriority.LOW: 3
        }
        
        matching_rules.sort(key=lambda r: priority_order.get(r.priority, 4))
        
        return matching_rules

    def execute_prevention(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluate rules and execute prevention actions.
        Returns execution result.
        """
        matching_rules = self.evaluate_rules(context)
        actions_taken = []
        
        source_ip = context.get("source_ip")
        
        for rule in matching_rules:
            action_result = {
                "rule_id": rule.rule_id,
                "rule_name": rule.name,
                "action": rule.action.value
            }
            
            if rule.action == ActionType.BLOCK:
                if source_ip and not self.is_blocked(source_ip):
                    block = self.block(
                        ip_address=source_ip,
                        reason=BlockReason.POLICY_VIOLATION,
                        source=f"rule:{rule.rule_id}"
                    )
                    if block:
                        action_result["block_id"] = block.block_id
                        self._stats["rule_blocks"] += 1
                        
            elif rule.action == ActionType.RATE_LIMIT:
                if source_ip:
                    self._apply_rate_limit(source_ip, "rule_limit")
                    self._stats["rate_limits_applied"] += 1
                    
            elif rule.action == ActionType.ALERT:
                self._log_action(
                    ActionType.ALERT,
                    source_ip=source_ip,
                    rule_id=rule.rule_id,
                    details={"context": context}
                )
                self._stats["alerts_triggered"] += 1
            
            actions_taken.append(action_result)
            self._execute_handlers(rule.action, {"rule": rule, "context": context})
        
        return {
            "actions_taken": actions_taken,
            "rules_matched": len(matching_rules)
        }

    def _apply_rate_limit(self, ip_address: str, limit_type: str) -> None:
        """Apply rate limit to an IP"""
        config = self._rate_limit_configs.get(limit_type, self._rate_limit_configs["global"])
        now = datetime.utcnow()
        
        with self._lock:
            # Clean old entries
            window_start = now - timedelta(seconds=config["window_seconds"])
            self._rate_limits[ip_address] = [
                t for t in self._rate_limits[ip_address]
                if t > window_start
            ]
            
            # Add current request
            self._rate_limits[ip_address].append(now)

    def check_rate_limit(
        self,
        ip_address: str,
        limit_type: str = "global"
    ) -> Dict[str, Any]:
        """
        Check if IP is within rate limits.
        Returns rate limit status.
        """
        config = self._rate_limit_configs.get(limit_type, self._rate_limit_configs["global"])
        max_requests = config["max_requests"]
        window_seconds = config["window_seconds"]
        
        now = datetime.utcnow()
        window_start = now - timedelta(seconds=window_seconds)
        
        with self._lock:
            # Clean old entries
            self._rate_limits[ip_address] = [
                t for t in self._rate_limits[ip_address]
                if t > window_start
            ]
            
            # Add current request
            self._rate_limits[ip_address].append(now)
            
            current_count = len(self._rate_limits[ip_address])
            allowed = current_count <= max_requests
            
            return {
                "allowed": allowed,
                "current_count": current_count,
                "limit": max_requests,
                "window_seconds": window_seconds,
                "reset_at": (now + timedelta(seconds=window_seconds)).isoformat()
            }

    def set_rate_limit(self, limit_type: str, max_requests: int, window_seconds: int) -> None:
        """Configure a rate limit"""
        with self._lock:
            self._rate_limit_configs[limit_type] = {
                "max_requests": max_requests,
                "window_seconds": window_seconds
            }

    def register_action_handler(self, action_type: ActionType, handler: Callable) -> None:
        """Register a callback for an action type"""
        with self._lock:
            self._action_handlers[action_type].append(handler)

    def _execute_handlers(self, action_type: ActionType, data: Dict[str, Any]) -> None:
        """Execute registered handlers for an action"""
        handlers = self._action_handlers.get(action_type, [])
        for handler in handlers:
            try:
                handler(data)
            except Exception:
                pass  # Don't fail on handler errors

    def _log_action(
        self,
        action: ActionType,
        source_ip: Optional[str] = None,
        user_id: Optional[str] = None,
        rule_id: Optional[str] = None,
        block_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log a prevention action"""
        log_entry = PreventionLog(
            action=action,
            source_ip=source_ip,
            user_id=user_id,
            rule_id=rule_id,
            block_id=block_id,
            details=details or {}
        )
        
        with self._lock:
            self._logs.append(log_entry)
            self._stats["log_entries"] += 1
            
            # Trim logs if too large
            if len(self._logs) > self.MAX_LOG_ENTRIES:
                self._logs = self._logs[-self.MAX_LOG_ENTRIES:]

    def get_blocked_ips(self, include_expired: bool = False) -> List[IPBlock]:
        """Get all blocked IPs"""
        now = datetime.utcnow()
        blocks = []
        
        with self._lock:
            for block in self._blocked_ips.values():
                if include_expired or not block.is_expired():
                    blocks.append(block)
        
        return blocks

    def get_rules(self, enabled_only: bool = False) -> List[PreventionRule]:
        """Get all rules"""
        with self._lock:
            rules = list(self._rules.values())
            if enabled_only:
                rules = [r for r in rules if r.enabled]
        return rules

    def get_rule(self, rule_id: str) -> Optional[PreventionRule]:
        """Get a specific rule"""
        return self._rules.get(rule_id)

    def get_logs(self, limit: int = 100, action_type: Optional[ActionType] = None) -> List[PreventionLog]:
        """Get prevention logs"""
        with self._lock:
            logs = list(self._logs)
            if action_type:
                logs = [l for l in logs if l.action == action_type]
        return logs[-limit:]

    def get_statistics(self) -> Dict[str, Any]:
        """Get prevention statistics"""
        now = datetime.utcnow()
        
        with self._lock:
            active_blocks = len([b for b in self._blocked_ips.values() if not b.is_expired()])
            
            return {
                "total_blocks": len(self._blocked_ips),
                "active_blocks": active_blocks,
                "blacklist_size": len(self._blacklist),
                "whitelist_size": len(self._whitelist),
                "rules_count": len(self._rules),
                "enabled_rules": len([r for r in self._rules.values() if r.enabled]),
                "log_entries": len(self._logs),
                "rate_limited_ips": len(self._rate_limits),
                "stats": dict(self._stats)
            }

    def clear_expired_blocks(self) -> int:
        """Remove expired blocks"""
        removed = 0
        now = datetime.utcnow()
        
        with self._lock:
            to_remove = [
                ip for ip, block in self._blocked_ips.items()
                if block.is_expired()
            ]
            for ip in to_remove:
                self._blocked_ips[ip].status = IPBlockStatus.EXPIRED
                del self._blocked_ips[ip]
                removed += 1
                self._stats["blocks_expired"] += 1
        
        return removed

    def clear_logs(self, before: Optional[datetime] = None) -> int:
        """Clear logs"""
        with self._lock:
            if before is None:
                count = len(self._logs)
                self._logs = []
            else:
                original_count = len(self._logs)
                self._logs = [l for l in self._logs if l.timestamp >= before]
                count = original_count - len(self._logs)
        return count

    def export_blocks(self) -> List[Dict[str, Any]]:
        """Export blocks for backup/reporting"""
        return [b.to_dict() for b in self.get_blocked_ips(include_expired=False)]

    def export_rules(self) -> List[Dict[str, Any]]:
        """Export rules for backup/reporting"""
        return [r.to_dict() for r in self.get_rules()]
