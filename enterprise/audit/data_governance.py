# Data Governance - Week 49 Builder 3
# Data governance policies and management

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum
import uuid


class DataClassification(Enum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"
    TOP_SECRET = "top_secret"


class DataCategory(Enum):
    PII = "pii"
    PHI = "phi"
    FINANCIAL = "financial"
    OPERATIONAL = "operational"
    ANALYTICS = "analytics"
    SYSTEM = "system"


class GovernanceStatus(Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"


@dataclass
class DataAsset:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str = ""
    name: str = ""
    classification: DataClassification = DataClassification.INTERNAL
    category: DataCategory = DataCategory.OPERATIONAL
    owner: str = ""
    stewards: List[str] = field(default_factory=list)
    location: str = ""
    retention_period_days: int = 365
    compliance_tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class GovernancePolicy:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str = ""
    name: str = ""
    description: str = ""
    classification: DataClassification = DataClassification.INTERNAL
    rules: List[Dict[str, Any]] = field(default_factory=list)
    exceptions: List[str] = field(default_factory=list)
    enabled: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)


class DataGovernance:
    """Manages data governance policies and assets"""

    def __init__(self):
        self._assets: Dict[str, DataAsset] = {}
        self._policies: Dict[str, GovernancePolicy] = {}
        self._metrics = {
            "total_assets": 0,
            "total_policies": 0,
            "by_classification": {},
            "by_category": {}
        }

    def register_asset(
        self,
        tenant_id: str,
        name: str,
        classification: DataClassification,
        category: DataCategory,
        owner: str = "",
        location: str = ""
    ) -> DataAsset:
        """Register a new data asset"""
        asset = DataAsset(
            tenant_id=tenant_id,
            name=name,
            classification=classification,
            category=category,
            owner=owner,
            location=location
        )

        self._assets[asset.id] = asset
        self._metrics["total_assets"] += 1

        cls_key = classification.value
        self._metrics["by_classification"][cls_key] = self._metrics["by_classification"].get(cls_key, 0) + 1

        cat_key = category.value
        self._metrics["by_category"][cat_key] = self._metrics["by_category"].get(cat_key, 0) + 1

        return asset

    def create_policy(
        self,
        tenant_id: str,
        name: str,
        classification: DataClassification,
        rules: Optional[List[Dict[str, Any]]] = None
    ) -> GovernancePolicy:
        """Create a governance policy"""
        policy = GovernancePolicy(
            tenant_id=tenant_id,
            name=name,
            classification=classification,
            rules=rules or []
        )
        self._policies[policy.id] = policy
        self._metrics["total_policies"] += 1
        return policy

    def get_asset(self, asset_id: str) -> Optional[DataAsset]:
        """Get an asset by ID"""
        return self._assets.get(asset_id)

    def get_policy(self, policy_id: str) -> Optional[GovernancePolicy]:
        """Get a policy by ID"""
        return self._policies.get(policy_id)

    def get_assets_by_classification(
        self,
        tenant_id: str,
        classification: DataClassification
    ) -> List[DataAsset]:
        """Get assets by classification"""
        return [
            a for a in self._assets.values()
            if a.tenant_id == tenant_id
            and a.classification == classification
        ]

    def get_assets_by_category(
        self,
        tenant_id: str,
        category: DataCategory
    ) -> List[DataAsset]:
        """Get assets by category"""
        return [
            a for a in self._assets.values()
            if a.tenant_id == tenant_id
            and a.category == category
        ]

    def update_asset_classification(
        self,
        asset_id: str,
        classification: DataClassification
    ) -> Optional[DataAsset]:
        """Update asset classification"""
        asset = self._assets.get(asset_id)
        if not asset:
            return None

        old_cls = asset.classification
        asset.classification = classification
        asset.updated_at = datetime.utcnow()

        # Update metrics
        old_key = old_cls.value
        new_key = classification.value
        if old_key in self._metrics["by_classification"]:
            self._metrics["by_classification"][old_key] -= 1
        self._metrics["by_classification"][new_key] = self._metrics["by_classification"].get(new_key, 0) + 1

        return asset

    def apply_policy_to_asset(
        self,
        policy_id: str,
        asset_id: str
    ) -> bool:
        """Apply a policy to an asset"""
        policy = self._policies.get(policy_id)
        asset = self._assets.get(asset_id)
        if not policy or not asset:
            return False

        # Check if policy classification matches
        if policy.classification != asset.classification:
            return False

        return True

    def get_compliance_report(self, tenant_id: str) -> Dict[str, Any]:
        """Generate governance compliance report"""
        assets = [a for a in self._assets.values() if a.tenant_id == tenant_id]

        return {
            "total_assets": len(assets),
            "by_classification": {
                cls.value: len([a for a in assets if a.classification == cls])
                for cls in DataClassification
            },
            "by_category": {
                cat.value: len([a for a in assets if a.category == cat])
                for cat in DataCategory
            }
        }

    def get_metrics(self) -> Dict[str, Any]:
        """Get governance metrics"""
        return self._metrics.copy()
