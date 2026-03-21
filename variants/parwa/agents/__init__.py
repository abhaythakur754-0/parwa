"""
PARWA Junior Agents Module.

This module contains all agent implementations for the PARWA Junior variant.
Each agent inherits from the corresponding base agent and implements
PARWA Junior-specific behavior.

Agents:
- ParwaFAQAgent: FAQ handling with medium tier support
- ParwaEmailAgent: Email processing with intent extraction
- ParwaChatAgent: Chat handling with conversation context
- ParwaSMSAgent: SMS processing and response
- ParwaVoiceAgent: Voice/call handling with 5 concurrent calls
- ParwaTicketAgent: Support ticket management
- ParwaEscalationAgent: Human handoff and escalation
- ParwaRefundAgent: Refund processing with APPROVE/REVIEW/DENY reasoning
- ParwaLearningAgent: Learning and feedback collection (creates negative_reward)
- ParwaSafetyAgent: Safety checks and content validation

PARWA Junior agents differ from Mini agents in:
- Support for medium AI tier
- Higher concurrent call limits (5 vs 2)
- Additional channels (voice, video)
- Higher refund limits ($500 vs $50)
- Lower escalation threshold (60% vs 70%)
- APPROVE/REVIEW/DENY recommendations with reasoning
- Learning capabilities with negative_reward records
"""
from variants.parwa.agents.faq_agent import ParwaFAQAgent
from variants.parwa.agents.email_agent import ParwaEmailAgent
from variants.parwa.agents.chat_agent import ParwaChatAgent
from variants.parwa.agents.sms_agent import ParwaSMSAgent
from variants.parwa.agents.voice_agent import ParwaVoiceAgent
from variants.parwa.agents.ticket_agent import ParwaTicketAgent
from variants.parwa.agents.escalation_agent import ParwaEscalationAgent
from variants.parwa.agents.refund_agent import ParwaRefundAgent
from variants.parwa.agents.learning_agent import ParwaLearningAgent
from variants.parwa.agents.safety_agent import ParwaSafetyAgent

__all__ = [
    "ParwaFAQAgent",
    "ParwaEmailAgent",
    "ParwaChatAgent",
    "ParwaSMSAgent",
    "ParwaVoiceAgent",
    "ParwaTicketAgent",
    "ParwaEscalationAgent",
    "ParwaRefundAgent",
    "ParwaLearningAgent",
    "ParwaSafetyAgent",
]
