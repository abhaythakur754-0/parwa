"""
Week 60 - Builder 2: Deployment Manager Module
Deployment management, environment handling, and validation
"""

import time
import hashlib
import threading
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


class DeploymentStatus(Enum):
    """Deployment status"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class EnvironmentType(Enum):
    """Environment types"""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


@dataclass
class Deployment:
    """Deployment record"""
    id: str
    environment: str
    version: str
    status: DeploymentStatus = DeploymentStatus.PENDING
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    rollback_version: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Environment:
    """Environment configuration"""
    name: str
    env_type: EnvironmentType
    config: Dict[str, Any] = field(default_factory=dict)
    secrets: List[str] = field(default_factory=list)
    endpoints: Dict[str, str] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)


class DeploymentManager:
    """
    Deployment manager for deployments, rollbacks, and status tracking
    """

    def __init__(self):
        self.deployments: Dict[str, Deployment] = {}
        self.environments: Dict[str, Environment] = {}
        self.current_versions: Dict[str, str] = {}
        self.lock = threading.Lock()

    def create_deployment(self, environment: str, version: str,
                          metadata: Dict[str, Any] = None) -> Deployment:
        """Create a new deployment"""
        deploy_id = hashlib.md5(
            f"{environment}:{version}:{time.time()}".encode()
        ).hexdigest()[:12]

        deployment = Deployment(
            id=deploy_id,
            environment=environment,
            version=version,
            rollback_version=self.current_versions.get(environment),
            metadata=metadata or {}
        )

        with self.lock:
            self.deployments[deploy_id] = deployment

        return deployment

    def start_deployment(self, deploy_id: str) -> bool:
        """Start a deployment"""
        deployment = self.deployments.get(deploy_id)
        if not deployment:
            return False

        with self.lock:
            deployment.status = DeploymentStatus.IN_PROGRESS
            deployment.started_at = time.time()

        return True

    def complete_deployment(self, deploy_id: str) -> bool:
        """Mark deployment as completed"""
        deployment = self.deployments.get(deploy_id)
        if not deployment:
            return False

        with self.lock:
            deployment.status = DeploymentStatus.COMPLETED
            deployment.completed_at = time.time()
            self.current_versions[deployment.environment] = deployment.version

        return True

    def fail_deployment(self, deploy_id: str, reason: str = "") -> bool:
        """Mark deployment as failed"""
        deployment = self.deployments.get(deploy_id)
        if not deployment:
            return False

        with self.lock:
            deployment.status = DeploymentStatus.FAILED
            deployment.completed_at = time.time()
            if reason:
                deployment.metadata["failure_reason"] = reason

        return True

    def rollback(self, deploy_id: str) -> Optional[Deployment]:
        """Rollback a deployment"""
        deployment = self.deployments.get(deploy_id)
        if not deployment or not deployment.rollback_version:
            return None

        # Create rollback deployment
        rollback = self.create_deployment(
            environment=deployment.environment,
            version=deployment.rollback_version,
            metadata={"rollback_of": deploy_id}
        )

        with self.lock:
            deployment.status = DeploymentStatus.ROLLED_BACK
            self.current_versions[deployment.environment] = deployment.rollback_version

        return rollback

    def get_deployment(self, deploy_id: str) -> Optional[Deployment]:
        """Get deployment by ID"""
        return self.deployments.get(deploy_id)

    def get_current_version(self, environment: str) -> Optional[str]:
        """Get current version for environment"""
        return self.current_versions.get(environment)

    def list_deployments(self, environment: str = None) -> List[Deployment]:
        """List deployments, optionally filtered by environment"""
        deployments = list(self.deployments.values())
        if environment:
            deployments = [d for d in deployments if d.environment == environment]
        return sorted(deployments, key=lambda d: d.started_at or 0, reverse=True)


class EnvironmentManager:
    """
    Environment manager for configurations and secrets
    """

    def __init__(self):
        self.environments: Dict[str, Environment] = {}
        self.configs: Dict[str, Dict[str, Any]] = {}
        self.lock = threading.Lock()

    def create_environment(self, name: str, env_type: EnvironmentType,
                           config: Dict[str, Any] = None) -> Environment:
        """Create an environment"""
        env = Environment(
            name=name,
            env_type=env_type,
            config=config or {}
        )

        with self.lock:
            self.environments[name] = env
            self.configs[name] = config or {}

        return env

    def get_environment(self, name: str) -> Optional[Environment]:
        """Get environment by name"""
        return self.environments.get(name)

    def update_config(self, env_name: str, key: str, value: Any) -> bool:
        """Update environment configuration"""
        if env_name not in self.environments:
            return False

        with self.lock:
            self.environments[env_name].config[key] = value
            self.configs[env_name][key] = value

        return True

    def get_config(self, env_name: str, key: str = None) -> Any:
        """Get configuration value(s)"""
        config = self.configs.get(env_name, {})
        if key:
            return config.get(key)
        return config

    def add_secret_ref(self, env_name: str, secret_name: str) -> bool:
        """Add secret reference to environment"""
        env = self.environments.get(env_name)
        if not env:
            return False

        with self.lock:
            if secret_name not in env.secrets:
                env.secrets.append(secret_name)

        return True

    def add_endpoint(self, env_name: str, service: str,
                     endpoint: str) -> bool:
        """Add service endpoint to environment"""
        env = self.environments.get(env_name)
        if not env:
            return False

        with self.lock:
            env.endpoints[service] = endpoint

        return True

    def get_endpoint(self, env_name: str, service: str) -> Optional[str]:
        """Get service endpoint"""
        env = self.environments.get(env_name)
        if not env:
            return None
        return env.endpoints.get(service)

    def list_environments(self) -> List[str]:
        """List all environment names"""
        return list(self.environments.keys())

    def delete_environment(self, name: str) -> bool:
        """Delete an environment"""
        with self.lock:
            if name in self.environments:
                del self.environments[name]
                del self.configs[name]
                return True
        return False


class DeploymentValidator:
    """
    Deployment validator for pre-flight and post-deploy checks
    """

    def __init__(self):
        self.checks: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self.results: Dict[str, Dict[str, Any]] = {}
        self.lock = threading.Lock()

    def register_check(self, category: str, name: str,
                       check_func: callable, required: bool = True) -> None:
        """Register a validation check"""
        with self.lock:
            self.checks[category].append({
                "name": name,
                "func": check_func,
                "required": required
            })

    def run_preflight_checks(self, environment: str) -> Dict[str, Any]:
        """Run pre-deployment checks"""
        results = {
            "environment": environment,
            "check_type": "preflight",
            "timestamp": time.time(),
            "passed": True,
            "checks": []
        }

        for check in self.checks.get("preflight", []):
            try:
                passed = check["func"](environment)
                results["checks"].append({
                    "name": check["name"],
                    "passed": passed,
                    "required": check["required"]
                })
                if not passed and check["required"]:
                    results["passed"] = False
            except Exception as e:
                results["checks"].append({
                    "name": check["name"],
                    "passed": False,
                    "error": str(e),
                    "required": check["required"]
                })
                if check["required"]:
                    results["passed"] = False

        with self.lock:
            self.results[f"preflight-{environment}-{int(time.time())}"] = results

        return results

    def run_postdeploy_checks(self, environment: str) -> Dict[str, Any]:
        """Run post-deployment checks"""
        results = {
            "environment": environment,
            "check_type": "postdeploy",
            "timestamp": time.time(),
            "passed": True,
            "checks": []
        }

        for check in self.checks.get("postdeploy", []):
            try:
                passed = check["func"](environment)
                results["checks"].append({
                    "name": check["name"],
                    "passed": passed,
                    "required": check["required"]
                })
                if not passed and check["required"]:
                    results["passed"] = False
            except Exception as e:
                results["checks"].append({
                    "name": check["name"],
                    "passed": False,
                    "error": str(e),
                    "required": check["required"]
                })
                if check["required"]:
                    results["passed"] = False

        with self.lock:
            self.results[f"postdeploy-{environment}-{int(time.time())}"] = results

        return results

    def get_result(self, check_id: str) -> Optional[Dict[str, Any]]:
        """Get validation result"""
        return self.results.get(check_id)

    def clear_checks(self, category: str = None) -> None:
        """Clear registered checks"""
        with self.lock:
            if category:
                self.checks[category] = []
            else:
                self.checks.clear()
