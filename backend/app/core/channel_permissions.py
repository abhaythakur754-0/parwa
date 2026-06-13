"""
PARWA — Shared Channel Permissions

Single source of truth for channel definitions and variant permissions.
Used by ExternalToolBus, ExternalToolExecutor, and any other module
that needs to know which channels are available per variant.

This eliminates the duplicate Channel enum and VARIANT_CHANNEL_PERMISSIONS
that previously existed in both external_tool_bus.py and external_tool_executor.py.
"""

from enum import Enum
from typing import Dict, Set


class Channel(str, Enum):
    """External communication channels."""
    EMAIL = "email"
    CHAT = "chat"
    SMS = "sms"
    VOICE = "voice"
    PUSH = "push"
    WEBHOOK = "webhook"


# Which channels each variant tier can access
VARIANT_CHANNEL_PERMISSIONS: Dict[str, Set[Channel]] = {
    "mini_parwa": {
        Channel.EMAIL,
        Channel.CHAT,
    },
    "parwa": {
        Channel.EMAIL,
        Channel.CHAT,
        Channel.SMS,
        Channel.VOICE,
    },
    "parwa_high": {
        Channel.EMAIL,
        Channel.CHAT,
        Channel.SMS,
        Channel.VOICE,
        Channel.PUSH,
        Channel.WEBHOOK,
    },
}


def is_channel_allowed(variant: str, channel: Channel) -> bool:
    """Check if a variant tier allows this channel."""
    return channel in VARIANT_CHANNEL_PERMISSIONS.get(variant, set())


def get_allowed_channels(variant: str) -> list[str]:
    """Get list of channels allowed for a variant tier."""
    allowed = VARIANT_CHANNEL_PERMISSIONS.get(variant, set())
    return sorted(ch.value for ch in allowed)
