"""
PARWA MCP Integration Servers.

MCP servers for external integrations: Email, Voice, Chat, Ticketing,
E-commerce, and CRM.

These servers wrap the integration clients and expose them as MCP tools
for the AI agents to use.
"""
from mcp_servers.integrations.email_server import EmailServer
from mcp_servers.integrations.voice_server import VoiceServer
from mcp_servers.integrations.chat_server import ChatServer
from mcp_servers.integrations.ticketing_server import TicketingServer
from mcp_servers.integrations.ecommerce_server import EcommerceServer
from mcp_servers.integrations.crm_server import CRMServer

__all__ = [
    "EmailServer",
    "VoiceServer",
    "ChatServer",
    "TicketingServer",
    "EcommerceServer",
    "CRMServer",
]
