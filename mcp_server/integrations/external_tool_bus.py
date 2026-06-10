"""
PARWA MCP — External Tool Bus (Thin Wrapper)

Delegates to the canonical ExternalToolBus in backend/app/core/external_tool_bus.py.
Re-exports everything for backward compatibility with existing MCP server imports.

All actual integration logic lives in ONE place now.
"""

import sys
import os

# Add backend to path so we can import the canonical module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

from app.core.external_tool_bus import (
    ExternalToolBus,
    ToolResult,
    ProviderConfig,
    external_tool_bus,
)

# Also re-export Channel and VARIANT_CHANNEL_PERMISSIONS for MCP server consumers
from app.core.channel_permissions import Channel, VARIANT_CHANNEL_PERMISSIONS

# Re-export for backward compatibility
__all__ = [
    "ExternalToolBus",
    "ToolResult",
    "ProviderConfig",
    "Channel",
    "VARIANT_CHANNEL_PERMISSIONS",
    "external_tool_bus",
]
