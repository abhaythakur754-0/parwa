"""
PARWA Agent Lightning Deployment Module.

Handles model deployment, versioning, and rollback for Agent Lightning.

Components:
- model_registry: Track model versions and deployments
- deploy_model: Deploy models to production
- rollback: Rollback to previous model versions

Key Features:
- Model version registry
- Immutable version records
- Active model tracking
- Deployment verification
- Safe rollback mechanism
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class DeploymentStatus(str, Enum):
    """Model deployment status."""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    DEPRECATED = "deprecated"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"


class DeploymentType(str, Enum):
    """Type of deployment."""
    INITIAL = "initial"
    UPDATE = "update"
    ROLLBACK = "rollback"
    CANARY = "canary"
    BLUE_GREEN = "blue_green"


def get_deployment_config() -> Dict[str, Any]:
    """
    Get default deployment configuration.

    Returns:
        Dict with deployment config
    """
    return {
        "validation": {
            "accuracy_threshold": 0.90,  # 90% minimum
            "test_suite_required": True,
            "auto_rollback_on_failure": True
        },
        "rollback": {
            "auto_rollback_threshold": 0.85,
            "max_rollback_attempts": 3,
            "preserve_versions": 10
        },
        "deployment": {
            "strategy": "blue_green",
            "health_check_timeout_seconds": 300,
            "traffic_shift_percentage": 10
        }
    }


# Try to import deployment classes if available
try:
    from agent_lightning.deployment.deploy_model import ModelDeployer
    from agent_lightning.deployment.rollback import ModelRollback
    from agent_lightning.deployment.model_registry import ModelRegistry
except ImportError:
    ModelDeployer = None
    ModelRollback = None
    ModelRegistry = None


__all__ = [
    "DeploymentStatus",
    "DeploymentType",
    "get_deployment_config",
    "ModelDeployer",
    "ModelRollback",
    "ModelRegistry",
]
