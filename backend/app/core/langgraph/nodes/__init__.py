"""
PARWA LangGraph Agent Nodes

This package contains the individual agent node implementations.
Each node is a function: (state: ParwaGraphState) -> dict
that reads from state, processes, and returns a partial state update.

Nodes (Phase 2):
  01_pii_redaction    — PII entity detection and redaction
  02_empathy_engine   — Sentiment analysis and urgency detection
  03_router_agent     — Intent classification and agent routing
  04_base_domain_agent — Base class for domain agents
  05_faq_agent        — FAQ domain agent
  06_refund_agent     — Refund domain agent
  07_technical_agent  — Technical support domain agent
  08_billing_agent    — Billing domain agent
  09_complaint_agent  — Complaint handling domain agent
  10_escalation_agent — Escalation domain agent
  11_maker_validator  — K-solution validator (ALL tiers)
  12_control_system   — Approval/interrupt decision system
  13_dspy_optimizer   — DSPy prompt optimization
  14_guardrails       — Safety and compliance checks
  15_channel_delivery — Channel dispatch routing
  16_state_update     — Persistence, audit, metrics
  17_email_agent      — Email channel delivery
  18_sms_agent        — SMS channel delivery
  19_voice_agent      — Voice channel delivery (Pro + High only)
"""

# Explicit re-exports for static analysis visibility.
# These modules are loaded lazily by graph.py's _get_node_function(),
# but re-exporting here helps tools (Graphify, IDEs, mypy) see the edges.

from app.core.langgraph.nodes.01_pii_redaction import pii_redaction_node  # noqa: F401
from app.core.langgraph.nodes.02_empathy_engine import empathy_engine_node  # noqa: F401
from app.core.langgraph.nodes.03_router_agent import router_agent_node  # noqa: F401
from app.core.langgraph.nodes.04_base_domain_agent import BaseDomainAgent  # noqa: F401
from app.core.langgraph.nodes.05_faq_agent import faq_agent_node  # noqa: F401
from app.core.langgraph.nodes.06_refund_agent import refund_agent_node  # noqa: F401
from app.core.langgraph.nodes.07_technical_agent import technical_agent_node  # noqa: F401
from app.core.langgraph.nodes.08_billing_agent import billing_agent_node  # noqa: F401
from app.core.langgraph.nodes.09_complaint_agent import complaint_agent_node  # noqa: F401
from app.core.langgraph.nodes.10_escalation_agent import escalation_agent_node  # noqa: F401
from app.core.langgraph.nodes.11_maker_validator import maker_validator_node  # noqa: F401
from app.core.langgraph.nodes.12_control_system import control_system_node  # noqa: F401
from app.core.langgraph.nodes.13_dspy_optimizer import dspy_optimizer_node  # noqa: F401
from app.core.langgraph.nodes.14_guardrails import guardrails_node  # noqa: F401
from app.core.langgraph.nodes.15_channel_delivery import channel_delivery_node  # noqa: F401
from app.core.langgraph.nodes.16_state_update import state_update_node  # noqa: F401
from app.core.langgraph.nodes.17_email_agent import email_agent_node  # noqa: F401
from app.core.langgraph.nodes.18_sms_agent import sms_agent_node  # noqa: F401
from app.core.langgraph.nodes.19_voice_agent import voice_agent_node  # noqa: F401
