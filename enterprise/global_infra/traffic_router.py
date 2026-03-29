# Traffic Router - Week 51 Builder 1
# Intelligent traffic routing

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum
import uuid


class RoutingRuleType(Enum):
    GEOGRAPHIC = "geographic"
    HEADER_BASED = "header_based"
    PATH_BASED = "path_based"
    WEIGHTED = "weighted"
    FAILOVER = "failover"


@dataclass
class RoutingRule:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    rule_type: RoutingRuleType = RoutingRuleType.PATH_BASED
    condition: str = ""
    target_region: str = ""
    weight: int = 100
    priority: int = 0
    enabled: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class RoutingDecision:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    request_id: str = ""
    source_ip: str = ""
    source_region: str = ""
    target_region: str = ""
    matched_rule: str = ""
    latency_ms: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)


class TrafficRouter:
    """Intelligent traffic routing across regions"""

    def __init__(self):
        self._rules: Dict[str, RoutingRule] = {}
        self._decisions: List[RoutingDecision] = []
        self._region_map: Dict[str, str] = {
            "US": "us-east-1",
            "US-WEST": "us-west-1",
            "EU": "eu-west-1",
            "EU-CENTRAL": "eu-central-1",
            "APAC": "ap-southeast-1",
            "APAC-EAST": "ap-northeast-1"
        }
        self._metrics = {
            "total_routed": 0,
            "by_region": {},
            "by_rule": {}
        }

    def add_rule(
        self,
        name: str,
        rule_type: RoutingRuleType,
        condition: str,
        target_region: str,
        weight: int = 100,
        priority: int = 0
    ) -> RoutingRule:
        """Add a routing rule"""
        rule = RoutingRule(
            name=name,
            rule_type=rule_type,
            condition=condition,
            target_region=target_region,
            weight=weight,
            priority=priority
        )
        self._rules[rule.id] = rule
        return rule

    def remove_rule(self, rule_id: str) -> bool:
        """Remove a routing rule"""
        if rule_id in self._rules:
            del self._rules[rule_id]
            return True
        return False

    def route_request(
        self,
        source_ip: str = "",
        headers: Optional[Dict[str, str]] = None,
        path: str = ""
    ) -> Optional[RoutingDecision]:
        """Route a request to appropriate region"""
        source_region = self._get_region_from_ip(source_ip)
        target_region = None
        matched_rule = None

        # Get enabled rules sorted by priority
        rules = sorted(
            [r for r in self._rules.values() if r.enabled],
            key=lambda r: r.priority,
            reverse=True
        )

        for rule in rules:
            if self._matches_rule(rule, source_region, headers or {}, path):
                target_region = rule.target_region
                matched_rule = rule
                break

        # Default to source region if no rule matches
        if not target_region:
            target_region = self._region_map.get(source_region, "us-east-1")

        decision = RoutingDecision(
            source_ip=source_ip,
            source_region=source_region,
            target_region=target_region,
            matched_rule=matched_rule.name if matched_rule else "default"
        )

        self._decisions.append(decision)
        self._metrics["total_routed"] += 1
        self._metrics["by_region"][target_region] = \
            self._metrics["by_region"].get(target_region, 0) + 1

        if matched_rule:
            self._metrics["by_rule"][matched_rule.name] = \
                self._metrics["by_rule"].get(matched_rule.name, 0) + 1

        return decision

    def _get_region_from_ip(self, ip: str) -> str:
        """Determine region from IP address"""
        # Simplified GeoIP lookup
        if not ip:
            return "US"

        # Mock GeoIP based on IP prefixes
        if ip.startswith("10.0.1"):
            return "US"
        elif ip.startswith("10.0.2"):
            return "EU"
        elif ip.startswith("10.0.3"):
            return "APAC"
        return "US"

    def _matches_rule(
        self,
        rule: RoutingRule,
        source_region: str,
        headers: Dict[str, str],
        path: str
    ) -> bool:
        """Check if request matches a rule"""
        if rule.rule_type == RoutingRuleType.GEOGRAPHIC:
            return source_region == rule.condition
        elif rule.rule_type == RoutingRuleType.HEADER_BASED:
            key, value = rule.condition.split(":", 1) if ":" in rule.condition else ("", "")
            return headers.get(key, "") == value
        elif rule.rule_type == RoutingRuleType.PATH_BASED:
            return path.startswith(rule.condition)
        elif rule.rule_type == RoutingRuleType.WEIGHTED:
            import random
            return random.randint(0, 100) < rule.weight
        return False

    def enable_rule(self, rule_id: str) -> bool:
        """Enable a routing rule"""
        rule = self._rules.get(rule_id)
        if not rule:
            return False
        rule.enabled = True
        return True

    def disable_rule(self, rule_id: str) -> bool:
        """Disable a routing rule"""
        rule = self._rules.get(rule_id)
        if not rule:
            return False
        rule.enabled = False
        return True

    def get_rule(self, rule_id: str) -> Optional[RoutingRule]:
        """Get rule by ID"""
        return self._rules.get(rule_id)

    def get_rules_by_type(self, rule_type: RoutingRuleType) -> List[RoutingRule]:
        """Get all rules of a type"""
        return [r for r in self._rules.values() if r.rule_type == rule_type]

    def get_decisions(
        self,
        region: Optional[str] = None,
        limit: int = 100
    ) -> List[RoutingDecision]:
        """Get routing decisions"""
        decisions = self._decisions
        if region:
            decisions = [d for d in decisions if d.target_region == region]
        return decisions[-limit:]

    def set_region_mapping(self, region_code: str, region_name: str) -> None:
        """Set region code to name mapping"""
        self._region_map[region_code] = region_name

    def get_region_mapping(self) -> Dict[str, str]:
        """Get region mappings"""
        return self._region_map.copy()

    def get_metrics(self) -> Dict[str, Any]:
        """Get router metrics"""
        return self._metrics.copy()

    def clear_decisions(self) -> int:
        """Clear routing decisions"""
        count = len(self._decisions)
        self._decisions.clear()
        return count
