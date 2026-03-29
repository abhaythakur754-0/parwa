"""
Enterprise Onboarding - Configuration Generator
Generates client configurations for enterprise deployments
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
import json
import yaml


class ClientConfig(BaseModel):
    """Generated client configuration"""
    client_id: str
    client_name: str
    variant: str
    region: str
    industry: str
    features: Dict[str, bool] = Field(default_factory=dict)
    limits: Dict[str, int] = Field(default_factory=dict)
    integrations: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict()


class ConfigGenerator:
    """
    Generates client configurations for enterprise deployments.
    Supports JSON and YAML output formats.
    """

    DEFAULT_LIMITS = {
        "max_concurrent_users": 1000,
        "max_api_calls_per_day": 100000,
        "max_storage_gb": 100,
        "retention_days": 90
    }

    def __init__(self):
        self.configs: Dict[str, ClientConfig] = {}

    def generate_config(
        self,
        client_id: str,
        client_name: str,
        variant: str,
        region: str,
        industry: str,
        features: Optional[Dict[str, bool]] = None,
        limits: Optional[Dict[str, int]] = None
    ) -> ClientConfig:
        """Generate a new client configuration"""
        config = ClientConfig(
            client_id=client_id,
            client_name=client_name,
            variant=variant,
            region=region,
            industry=industry,
            features=features or self._get_default_features(variant),
            limits={**self.DEFAULT_LIMITS, **(limits or {})}
        )
        self.configs[client_id] = config
        return config

    def _get_default_features(self, variant: str) -> Dict[str, bool]:
        """Get default features for variant"""
        base_features = {
            "analytics": True,
            "webhooks": True,
            "api_access": True,
            "sso": False,
            "custom_branding": False
        }

        if variant == "parwa_high":
            base_features["sso"] = True
            base_features["custom_branding"] = True

        return base_features

    def export_json(self, client_id: str) -> Optional[str]:
        """Export config as JSON"""
        if client_id in self.configs:
            return self.configs[client_id].model_dump_json()
        return None

    def export_yaml(self, client_id: str) -> Optional[str]:
        """Export config as YAML"""
        if client_id in self.configs:
            return yaml.dump(self.configs[client_id].model_dump())
        return None

    def get_config(self, client_id: str) -> Optional[ClientConfig]:
        """Get config by client ID"""
        return self.configs.get(client_id)

    def update_config(self, client_id: str, updates: Dict[str, Any]) -> Optional[ClientConfig]:
        """Update existing config"""
        if client_id in self.configs:
            config = self.configs[client_id]
            for key, value in updates.items():
                if hasattr(config, key):
                    setattr(config, key, value)
            return config
        return None
