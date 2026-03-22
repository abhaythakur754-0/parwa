"""
PARWA Base Agents Package.

Abstract base classes for all PARWA agent types. These provide
the foundation for Mini PARWA, standard PARWA, and PARWA High variants.

All agents inherit from BaseAgent and implement their specific
process() method for handling different input types.

CRITICAL: This is the foundation for ALL agents in Week 9.
All variant agents must inherit from these base classes.
"""
from variants.base_agents.base_agent import (
    BaseAgent,
    AgentResponse,
    AgentState,
    AgentConfig,
)
from variants.base_agents.base_faq_agent import BaseFAQAgent
from variants.base_agents.base_email_agent import BaseEmailAgent
from variants.base_agents.base_chat_agent import BaseChatAgent
from variants.base_agents.base_sms_agent import BaseSMSAgent
from variants.base_agents.base_voice_agent import BaseVoiceAgent
from variants.base_agents.base_ticket_agent import BaseTicketAgent
from variants.base_agents.base_escalation_agent import BaseEscalationAgent

__all__ = [
    # Core
    "BaseAgent",
    "AgentResponse",
    "AgentState",
    "AgentConfig",
    # Base Agent Types
    "BaseFAQAgent",
    "BaseEmailAgent",
    "BaseChatAgent",
    "BaseSMSAgent",
    "BaseVoiceAgent",
    "BaseTicketAgent",
    "BaseEscalationAgent",
]
