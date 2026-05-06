"""
PARWA Variants Package.

This package contains different variants of PARWA agents:
- Base Agents: Abstract base classes for all agent types
- Mini PARWA: Lightweight variant for small businesses
- PARWA: Standard variant for medium businesses
- PARWA High: Enterprise variant with advanced features
- Healthcare: HIPAA-compliant healthcare support
- Logistics: Supply chain and delivery optimization

Each variant has its own configuration, agents, and workflows.
"""
from variants.base_agents import (
    BaseAgent,
    BaseFAQAgent,
    BaseEmailAgent,
    BaseChatAgent,
    BaseSMSAgent,
    BaseVoiceAgent,
    BaseTicketAgent,
    BaseEscalationAgent,
    AgentResponse,
    AgentState,
)

__all__ = [
    # Base Agents
    "BaseAgent",
    "BaseFAQAgent",
    "BaseEmailAgent",
    "BaseChatAgent",
    "BaseSMSAgent",
    "BaseVoiceAgent",
    "BaseTicketAgent",
    "BaseEscalationAgent",
    # Models
    "AgentResponse",
    "AgentState",
]
