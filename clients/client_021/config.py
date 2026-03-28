"""Client 021 Configuration - GameVerse Entertainment"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import time
import json
from pathlib import Path


@dataclass
class BusinessHours:
    """Business hours configuration"""
    start: time
    end: time
    timezone: str


@dataclass
class EscalationContact:
    """Escalation contact information"""
    email: str
    slack_webhook: Optional[str] = None
    phone: Optional[str] = None


@dataclass
class FeatureFlags:
    """Feature flags for client"""
    shadow_mode: bool = True
    auto_escalation: bool = True
    sentiment_analysis: bool = True
    knowledge_base_search: bool = True
    multi_language: bool = False
    voice_support: bool = False


@dataclass
class SLAConfig:
    """SLA configuration"""
    first_response_hours: int = 2
    resolution_hours: int = 24
    escalation_hours: int = 1


@dataclass
class IntegrationConfig:
    """Third-party integrations"""
    discord: bool = True
    stripe: bool = True
    zendesk: bool = True
    email: bool = True


@dataclass
class VariantLimits:
    """Variant-specific limits for PARWA Junior"""
    refund_limit: float = 100.0
    escalation_threshold: float = 0.45
    concurrent_calls: int = 5
    session_timeout_minutes: int = 30


@dataclass
class GamingConfig:
    """Gaming/Entertainment specific configuration"""
    enabled: bool = True
    game_catalog: List[str] = field(default_factory=list)
    in_game_support: bool = True
    dlc_support: bool = True
    multiplayer_support: bool = True
    seasonal_events: bool = True


@dataclass
class ClientConfig:
    """Main client configuration"""
    client_id: str
    client_name: str
    industry: str
    variant: str
    timezone: str
    business_hours: BusinessHours
    escalation_contacts: EscalationContact
    paddle_account_id: Optional[str]
    feature_flags: FeatureFlags
    sla: SLAConfig
    integrations: IntegrationConfig = field(default_factory=IntegrationConfig)
    variant_limits: VariantLimits = field(default_factory=VariantLimits)
    gaming: GamingConfig = field(default_factory=GamingConfig)
    metadata: Dict[str, Any] = field(default_factory=dict)


def get_client_config() -> ClientConfig:
    """Load and return client 021 configuration.

    Client 021 is a Gaming & Entertainment company using PARWA Junior variant.
    Game purchase support, in-game issues, DLC management.
    24/7 support for global gamers.

    Returns:
        ClientConfig: The client configuration object
    """
    return ClientConfig(
        client_id="client_021",
        client_name="GameVerse Entertainment",
        industry="gaming_entertainment",
        variant="parwa_junior",
        timezone="UTC",  # Global 24/7
        business_hours=BusinessHours(
            start=time(0, 0),  # 24/7
            end=time(23, 59),
            timezone="UTC"
        ),
        escalation_contacts=EscalationContact(
            email="support@gameverse-entertainment.com",
            slack_webhook="https://hooks.slack.com/services/TXXXXX/BXXXXX/IH021X",
            phone="+1-555-0121"
        ),
        paddle_account_id="acc_gameverse021",
        feature_flags=FeatureFlags(
            shadow_mode=True,
            auto_escalation=True,
            sentiment_analysis=True,
            knowledge_base_search=True,
            multi_language=True,  # Global gamers
            voice_support=True
        ),
        sla=SLAConfig(
            first_response_hours=2,
            resolution_hours=24,
            escalation_hours=1
        ),
        integrations=IntegrationConfig(
            discord=True,
            stripe=True,
            zendesk=True,
            email=True
        ),
        variant_limits=VariantLimits(
            refund_limit=100.0,  # Game purchases
            escalation_threshold=0.45,
            concurrent_calls=5,
            session_timeout_minutes=30
        ),
        gaming=GamingConfig(
            enabled=True,
            game_catalog=[
                "stellar_odyssey",
                "realm_chronicles",
                "pixel_adventures",
                "cosmic_racers",
                "dungeon_legends"
            ],
            in_game_support=True,
            dlc_support=True,
            multiplayer_support=True,
            seasonal_events=True
        ),
        metadata={
            "website": "https://gameverse-entertainment.com",
            "support_email": "support@gameverse-entertainment.com",
            "community_discord": "https://discord.gg/gameverse",
            "founded": 2018,
            "employees": 150,
            "active_players": 5000000,
            "description": "Leading gaming entertainment company with multiplayer and single-player titles",
            "platforms": [
                "pc",
                "playstation",
                "xbox",
                "nintendo_switch",
                "mobile"
            ],
            "monthly_tickets": 2500,
            "support_languages": ["en", "es", "fr", "de", "ja", "zh"],
            "special_features": {
                "in_game_ticket_creation": True,
                "game_account_recovery": True,
                "dlc_refund_handling": True,
                "multiplayer_match_issues": True,
                "seasonal_event_support": True
            },
            "compliance": {
                "coppa": True,
                "gdpr": True,
                "esrb_ratings": True
            }
        }
    )


def load_config_from_file(filepath: str) -> ClientConfig:
    """Load config from JSON file."""
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {filepath}")
    with open(path) as f:
        data = json.load(f)
    return ClientConfig(**data)
